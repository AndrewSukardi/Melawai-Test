from fastapi import FastAPI, File, UploadFile
from fastapi.requests import Request
from fastapi.responses import PlainTextResponse
from typing import Annotated,Optional,Any
from pydantic import BaseModel  
from contextlib import asynccontextmanager
from config import Database,vectorDatabase,Reg
from loguru import logger as log
from functions import process_document



@asynccontextmanager
async def lifespan(app: FastAPI):

    _db = Database('data/app.db')
    Reg['db'] = _db
    log.info("Database Connected")

    await _db.execute("""
        CREATE TABLE IF NOT EXISTS document (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            is_parse BOOLEAN DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """)

    _vec_db = vectorDatabase('data/chroma_db')
    Reg['vec_db'] = _vec_db
    log.info("Vector Database Connected")


    yield

    await _db.close()


app = FastAPI(lifespan=lifespan,title="AI RAG for Melawai Test",swagger_ui_parameters={
                "defaultModelsExpandDepth": -1,
                "displayRequestDuration": True,
                "tryItOutEnabled": True,
            },
)

class ChatApiModel(BaseModel):
    msg: str
    
class IngestResponse(BaseModel):
    document_id: int
    total_chunk: int

class VecDataDeleteRequest(BaseModel):
    ids: Optional[list[Any]] = None
    metadata: Optional[dict] = None

@app.get('/',status_code=200)
async def root():
    return PlainTextResponse("API Melawai Test Ready")

@app.post('/ingest',status_code=201,response_model=IngestResponse)
async def ingest(
    file :  Annotated[UploadFile, File()]
):

    res = await process_document(file)
    
    return IngestResponse(document_id=res['document_id'], total_chunk=res['total_chunk'])

@app.post('/chat',status_code=200, response_model=ChatApiModel)
async def chat(
    data: ChatApiModel
):

    return 


@app.get("/vec_data")
async def get_vec():
    
    vec_db = Reg.get("vec_db",vectorDatabase)
    
    return vec_db.get()


@app.delete("/vec_data",status_code=204)
async def delete_vec(
    data : VecDataDeleteRequest
):
    
    vec_db = Reg.get("vec_db",vectorDatabase)
    
    vec_db.delete(data.ids,data.metadata)
    
    return