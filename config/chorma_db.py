import chromadb
from typing import Any, Optional
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction


from loguru import logger as log

embedding_function = SentenceTransformerEmbeddingFunction(
    model_name="BAAI/bge-m3"
)


class vectorDatabase():

    def __init__(self,path):
        client = chromadb.PersistentClient(path=path)

        self.collection =  client.get_or_create_collection("documents",embedding_function=embedding_function)


    def add(self,ids: list[Any], documents: list[str], metadatas: list[dict]):

        self.collection.add(
            ids = ids,
            documents=documents,
            metadatas=metadatas
        )


    def get(self):
        data = self.collection.get()

        final_data = []
        # Print out IDs, documents, and metadata
        for doc_id, document, metadata in zip(data["ids"], data["documents"], data["metadatas"]):
            final_data.append(
                {
                "id": doc_id,
                "Content": document,
                "Metadata": metadata
                }
            )
            
        return final_data
            
    
    def search(self,query: list[str], limit: int = 5, where_filter: Optional[dict] = None) ->list:

        if not where_filter:
            return self.collection.query(
                query_texts= query,
                n_results=limit
            )

        else:
            return self.collection.query(
                    query_texts= query,
                    where= where_filter,
                    n_results=limit
                )


    def delete(self, ids: Optional[list[Any]] = None ,metadata: Optional[dict] = None):

        if not ids and not metadata:
            return False


        self.collection.delete(
            ids = ids,
            where=metadata
        )

        return True

    
    