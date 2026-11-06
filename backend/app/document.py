
from fastapi import APIRouter, UploadFile, File, HTTPException
from pathlib import Path
from pypdf import PdfReader
from io import BytesIO
from uuid import uuid4
from pydantic import BaseModel

from app.services.embedding_service import split_text
from app.services.vector_service import store_chunks, search_chunks
from app.services.answer_service import answer_question

router = APIRouter()

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


class SearchRequest(BaseModel):
    question: str


class AskRequest(BaseModel):
    question: str
    document_id: str


@router.post("/upload")
async def upload_document(file: UploadFile = File(...)):

    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are supported"
        )

    content = await file.read()

    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail="File size must be below 10 MB"
        )

    try:
        pdf = PdfReader(BytesIO(content))

        if pdf.is_encrypted:
            raise HTTPException(
                status_code=400,
                detail="Encrypted PDFs are not supported"
            )

        extracted_text = "\n".join(
            page.extract_text() or ""
            for page in pdf.pages
        )

    except HTTPException:
        raise

    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Unable to read this PDF"
        )

    if not extracted_text.strip():
        raise HTTPException(
            status_code=400,
            detail="No readable text found in PDF"
        )

    safe_name = Path(file.filename).name

    file_path = UPLOAD_DIR / safe_name
    file_path.write_bytes(content)

    # Generate unique document ID
    document_id = str(uuid4())

    # Split extracted text into chunks
    chunks = split_text(extracted_text)

    # Generate embeddings and store chunks
    total_chunks = store_chunks(
        chunks=chunks,
        document_id=document_id,
        filename=safe_name
    )

    return {
        "message": "Document uploaded successfully",
        "document_id": document_id,
        "filename": safe_name,
        "pages": len(pdf.pages),
        "characters_extracted": len(extracted_text),
        "chunks_created": total_chunks,
        "text_preview": extracted_text[:500]
    }


@router.post("/search")
def search_document(request: SearchRequest):

    results = search_chunks(request.question)

    documents = results.get("documents") or [[]]
    metadatas = results.get("metadatas") or [[]]
    distances = results.get("distances") or [[]]

    if not documents[0]:
        return {
            "question": request.question,
            "results": []
        }

    return {
        "question": request.question,
        "results": [
            {
                "text": text,
                "source": metadata["filename"],
                "chunk_index": metadata["chunk_index"],
                "distance": distance
            }
            for text, metadata, distance in zip(
                documents[0],
                metadatas[0],
                distances[0]
            )
        ]
    }

@router.post("/ask")
def ask_question(request: AskRequest):

    if not request.question.strip():
        raise HTTPException(
            status_code=400,
            detail="Question cannot be empty"
        )

    if not request.document_id.strip():
        raise HTTPException(
            status_code=400,
            detail="Document ID is required"
        )

    try:
        return answer_question(
            request.question,
            request.document_id
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Unable to generate answer: {str(e)}"
        )
