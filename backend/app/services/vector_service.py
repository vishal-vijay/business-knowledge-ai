
import chromadb
from pathlib import Path

from app.services.embedding_service import generate_embeddings

DB_PATH = Path(__file__).resolve().parents[2] / "chroma_db"

client = chromadb.PersistentClient(
    path=str(DB_PATH)
)

collection = client.get_or_create_collection(
    name="business_documents"
)


def store_chunks(
    chunks: list[str],
    document_id: str,
    filename: str
):
    if not chunks:
        return

    embeddings = generate_embeddings(chunks)

    ids = [
        f"{document_id}_{i}"
        for i in range(len(chunks))
    ]

    metadatas = [
        {
            "document_id": document_id,
            "filename": filename,
            "chunk_index": i
        }
        for i in range(len(chunks))
    ]

    collection.upsert(
        ids=ids,
        documents=chunks,
        embeddings=embeddings,
        metadatas=metadatas
    )

    return len(chunks)



def search_chunks(question: str, limit=5, document_id=None):
    query_embedding = generate_embeddings([question])[0]

    search_options = {
        "query_embeddings": [query_embedding],
        "n_results": limit,
        "include": ["documents", "metadatas", "distances"]
    }

    if document_id:
        search_options["where"] = {
            "document_id": document_id
        }

    return collection.query(**search_options)
