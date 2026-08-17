from io import BytesIO
import re
from transformers import AutoTokenizer
from docling.document_converter import (
    DocumentConverter,
    PdfFormatOption,
)
from collections import Counter
from pydantic import BaseModel
from docling.document_converter import DocumentConverter
from docling.datamodel.base_models import DocumentStream,InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
from fastapi import UploadFile
from config import Reg,Database,vectorDatabase
from loguru import logger as log
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter


pipeline_options = PdfPipelineOptions()
PAGE_BREAK_TOKEN = "<<<PAGE_BREAK>>>"
PAGE_MARKER = f"\n\n{PAGE_BREAK_TOKEN}\n\n"


pipeline_options.layout_options.engine_options.compile_model = False

converter = DocumentConverter(
    format_options={
        InputFormat.PDF: PdfFormatOption(
            pipeline_options=pipeline_options,
            backend=PyPdfiumDocumentBackend,
        )
    }
)

raw_tokenizer = AutoTokenizer.from_pretrained("BAAI/bge-m3")

token_splitter = RecursiveCharacterTextSplitter.from_huggingface_tokenizer(
    raw_tokenizer,          
    chunk_size=300,
    chunk_overlap=40,
)


class IngestResponse(BaseModel):
    document_id: int
    file_name: str
    total_chunk: int
    

    
def get_headers_to_split_on(markdown_text, max_level=6):
  
    found_levels = set()
    for line in markdown_text.split("\n"):
        match = re.match(r'^(#{1,6})\s+.+', line)
        if match:
            found_levels.add(len(match.group(1)))  # number of # symbols

    headers_to_split_on = [
        ("#" * level, f"h{level}")
        for level in sorted(found_levels)
        if level <= max_level
    ]
    return headers_to_split_on


def compute_page_range(text_segment: str, page_before: int):
    """Count markers inside this segment to get its page span."""
    
    
    body = text_segment.rstrip()
    trailing_count = 0

    while body.endswith(PAGE_BREAK_TOKEN):
        body = body[: -len(PAGE_BREAK_TOKEN)].rstrip()
        trailing_count += 1

    internal_count = body.count(PAGE_BREAK_TOKEN) 

    start_page = page_before
    end_page = page_before + internal_count
    next_page_start = end_page + trailing_count

    return start_page, end_page, next_page_start

def strip_page_markers(text: str) -> str:
    # remove the token plus any surrounding whitespace Docling added around it
    return re.sub(r'\s*' + re.escape(PAGE_BREAK_TOKEN) + r'\s*', '\n\n', text).strip()


def page_label(start_page: int, end_page: int) -> str:
    return str(start_page) if start_page == end_page else f"{start_page}-{end_page}"

async def chuck_document(file: UploadFile):
    
    content = await file.read()
    
    source = DocumentStream(
        name=file.filename or "document.pdf",
        stream=BytesIO(content),
    )
    
      # unlikely to collide with real content


    doc = converter.convert(source).document
    markdown_text = doc.export_to_markdown(page_break_placeholder=PAGE_MARKER)
    
    print(f"Total page markers found: {markdown_text.count(PAGE_MARKER)}")
    print(f"Total pages in doc: {len(doc.pages)}")
    
    
    headers_to_split_on = get_headers_to_split_on(markdown_text)
    
    final_chunks = []
    current_page = 1
    
    if not headers_to_split_on:
        sections = [type("S", (), {"page_content": markdown_text, "metadata": {}})()]
        
    else:
        md_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on,strip_headers=False)
        sections = md_splitter.split_text(markdown_text)

    
    for section in sections:
        start_page, end_page, next_page_start = compute_page_range(section.page_content, current_page)
        current_page = next_page_start  

        clean_text = strip_page_markers(section.page_content)
        sub_chunks = token_splitter.split_text(clean_text)

        if not sub_chunks and section.metadata:
            heading_path = " > ".join(v for v in section.metadata.values() if v)
            final_chunks.append({
                "text": heading_path,
                "metadata": {**section.metadata,
                            "page": page_label(start_page, end_page), "heading_only": True}
            })
            continue

        for sc in sub_chunks:
            final_chunks.append({
                        "text": sc,   # no heading prefix — metadata already has it
                        "metadata": {**section.metadata,
                                    "page": page_label(start_page, end_page)}
                    })
                
    return final_chunks


async def process_document(file: UploadFile):
    
    
    db = Reg.get("db",Database)
    vec_db = Reg.get("vec_db",vectorDatabase)
    
    async with db.transaction() as tx:
        
        document_id = await tx.fetch_val("""
        INSERT INTO document (title)
        VALUES (:title)
        RETURNING id;
        """, {"title": file.filename})
        
        log.info("Document info inserted to Database")
        
        chunks = await chuck_document(file)
        
        metadatas = []
        text = []
        ids = []
        
        
        for i,chunk in enumerate(chunks):
            
            
            ids.append(f"{document_id}-{i}")
            metadatas.append({
                "document_id": document_id,
                "chunk_index": i,
                "file_name": file.filename,
                **chunk["metadata"]
            })
            text.append(chunk['text'])
            
        log.debug(f"Chunk Result: {ids}, {text}, {metadatas}")
        
        
        await tx.execute(
            """
                UPDATE document
                SET is_parse = 1
                WHERE id = :id;
            """,
            {"id":document_id}
        )
        
        vec_db.add(ids=ids,documents=text,metadatas=metadatas)
        
        return IngestResponse(
            document_id= document_id,
            total_chunk= len(chunks),
            file_name = file.filename
        )
        
        
        