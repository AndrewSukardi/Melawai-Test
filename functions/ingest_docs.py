from io import BytesIO
from transformers import AutoTokenizer
from docling.chunking import HybridChunker
from docling.document_converter import (
    DocumentConverter,
    PdfFormatOption,
)
from docling_core.transforms.chunker.tokenizer.huggingface import HuggingFaceTokenizer
from docling.document_converter import DocumentConverter
from docling.datamodel.base_models import DocumentStream,InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from fastapi import File
from config import Reg,Database,vectorDatabase
from loguru import logger as log

pipeline_options = PdfPipelineOptions()

pipeline_options.layout_options.engine_options.compile_model = False

converter = DocumentConverter(
    format_options={
        InputFormat.PDF: PdfFormatOption(
            pipeline_options=pipeline_options
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

async def chuck_document(file: File):
    
    content = await file.read()
    
    source = DocumentStream(
        name=file.filename or "document.pdf",
        stream=BytesIO(content),
    )

    result = converter.convert(source)

    doc = result.document
    
    return list(chunker.chunk(doc))


async def process_document(file: File):
    
    
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
            })
            text.append(chunk.text)
            
        log.debug("Chunk Result : %s, %s, %s",ids,text,metadatas)
        
        
        await tx.execute(
            """
                UPDATE document
                SET is_parse = 1
                WHERE id = :id;
            """,
            {"id":document_id}
        )
        
        vec_db.add(ids=ids,documents=text,metadatas=metadatas)
        
        return {
            "document_id" : document_id,
            "total_chunk" : len(chunks)
        }
        
        
        