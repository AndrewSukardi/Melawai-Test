from io import BytesIO
from transformers import AutoTokenizer
from docling.chunking import HybridChunker
from docling.document_converter import (
    DocumentConverter,
    PdfFormatOption,
)
from collections import Counter
from pydantic import BaseModel
from docling_core.transforms.chunker.tokenizer.huggingface import HuggingFaceTokenizer
from docling.document_converter import DocumentConverter
from docling.datamodel.base_models import DocumentStream,InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling_core.types.doc import ContentLayer
from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
from docling.backend.docling_parse_v4_backend import DoclingParseV4DocumentBackend
from docling_core.types.doc.labels import DocItemLabel
from fastapi import UploadFile
from config import Reg,Database,vectorDatabase
from loguru import logger as log

pipeline_options = PdfPipelineOptions()

pipeline_options.layout_options.engine_options.compile_model = False

converter = DocumentConverter(
    format_options={
        InputFormat.PDF: PdfFormatOption(
            pipeline_options=pipeline_options,
            backend=PyPdfiumDocumentBackend,
        )
    }
)

tokenizer = HuggingFaceTokenizer(
tokenizer=AutoTokenizer.from_pretrained("BAAI/bge-m3"),
max_tokens=512,
)

chunker = HybridChunker(
tokenizer=tokenizer,
merge_peers=True,
)

class IngestResponse(BaseModel):
    document_id: int
    file_name: str
    total_chunk: int
    
class _OrphanChunk:
    __slots__ = ("text", "meta")
    
def _normalize(text: str) -> str:
    return " ".join(text.strip().split())

async def chuck_document(file: UploadFile):
    
    content = await file.read()
    
    source = DocumentStream(
        name=file.filename or "document.pdf",
        stream=BytesIO(content),
    )

    result = converter.convert(source)

    doc = result.document
    
    chunks = list(chunker.chunk(doc))
    
    used_item_refs = set()
    used_heading_texts = set()
    for c in chunks:
        for item in (c.meta.doc_items or []):
            ref = getattr(item, "self_ref", None)
            if ref is not None:
                used_item_refs.add(ref)
        for h in (c.meta.headings or []):
            used_heading_texts.add(_normalize(h))

    orphan_chunks = []
    seen_keys = set()
    
    for item, _ in doc.iterate_items(included_content_layers={ContentLayer.BODY}):
        label = getattr(item, "label", None)
        if label not in (DocItemLabel.SECTION_HEADER, DocItemLabel.TITLE):
            continue
        text = _normalize(item.text or "")
        if not text:
            continue
        ref = getattr(item, "self_ref", None)
        if (ref is not None and ref in used_item_refs) or text in used_heading_texts:
            continue

        page_no = item.prov[0].page_no if item.prov else None
        key = (page_no, text)
        if key in seen_keys:
            continue
        seen_keys.add(key)

        oc = _OrphanChunk()
        oc.text = item.text.strip()
        oc.meta = type("meta", (), {"headings": [], "doc_items": [item]})()
        orphan_chunks.append(oc)
        
    furniture_items = list(
        doc.iterate_items(included_content_layers={ContentLayer.FURNITURE})
    )

    text_counts = Counter()
    for item, _ in furniture_items:
        text = _normalize(getattr(item, "text", "") or "")
        if text:
            text_counts[text] += 1

    MIN_TEXT_LEN = 8  

    for item, _ in furniture_items:
        text_norm = _normalize(item.text or "")
        if not text_norm or len(text_norm) < MIN_TEXT_LEN:
            continue 

        
        if text_counts[text_norm] > 1:
            continue

        if text_norm in used_heading_texts:
            continue

        page_no = item.prov[0].page_no if item.prov else None
        key = (page_no, text_norm)
        if key in seen_keys:
            continue
        seen_keys.add(key)

        oc = _OrphanChunk()
        oc.text = item.text.strip()
        oc.meta = type("meta", (), {"headings": [], "doc_items": [item]})()
        orphan_chunks.append(oc)
    
    
    return chunks + orphan_chunks


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
            
            pages = sorted({
                prov.page_no
                for item in chunk.meta.doc_items
                for prov in item.prov
            })
            
            headings = chunk.meta.headings or []
            
            ids.append(f"{document_id}-{i}")
            metadatas.append({
                "document_id": document_id,
                "chunk_index": i,
                "file_name": file.filename,
                "page_numbers": pages,  
                "page_start": pages[0] if pages else -1,
                "page_end": pages[-1] if pages else -1,
                "headings": " > ".join(headings) if headings else "",
            })
            text.append(chunk.text)
            
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
        
        
        