
import chromadb
from pathlib import Path

from app.services.embedding_service import generate_embeddings

DB_PATH = Path(__file__).resolve().parents[2] / "chroma_db"

client = chromadb.PersistentClient(path=str(DB_PATH))

collection = client.get_or_create_collection(
    name="business_documents_gemini"
)


def store_chunks(
    chunks: list[str],
    document_id: str,
    filename: str,
    business_id: str
):
    if not chunks:
        return 0

    embeddings = generate_embeddings(
        chunks,
        task_type="RETRIEVAL_DOCUMENT"
    )

    ids = [f"{document_id}_{i}" for i in range(len(chunks))]

    metadatas = [
        {
            "business_id": business_id,
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


def search_chunks(
    question: str,
    limit: int = 5,
    document_id: str | None = None,
    business_id: str | None = None
):
    if not document_id and not business_id:
        raise ValueError("Document ID or Business ID is required")

    query_embedding = generate_embeddings(
        [question],
        task_type="RETRIEVAL_QUERY"
    )[0]

    search_options = {
        "query_embeddings": [query_embedding],
        "n_results": limit,
        "include": ["documents", "metadatas", "distances"]
    }

    if document_id and business_id:
        search_options["where"] = {
            "$and": [
                {"document_id": document_id},
                {"business_id": business_id}
            ]
        }
    elif document_id:
        search_options["where"] = {"document_id": document_id}
    else:
        search_options["where"] = {"business_id": business_id}

    return collection.query(**search_options)


def document_exists(
    document_id: str,
    business_id: str | None = None
) -> bool:
    if business_id:
        where = {
            "$and": [
                {"document_id": document_id},
                {"business_id": business_id}
            ]
        }
    else:
        where = {"document_id": document_id}

    result = collection.get(where=where, limit=1)

    return len(result["ids"]) > 0
