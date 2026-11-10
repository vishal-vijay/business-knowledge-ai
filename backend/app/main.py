from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.document import router as document_router
from app.instagram import router as instagram_router


app = FastAPI(
    title="Business Knowledge AI",
    description="Document-based AI assistant",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:4200",
        "https://business-knowledge-ai.vercel.app"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(
    document_router,
    prefix="/documents",
    tags=["Documents"]
)

app.include_router(
    instagram_router,
    prefix="/instagram",
    tags=["Instagram"]
)

@app.get("/")
def home():
    return {
        "message": "Business Knowledge AI is running!"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }
