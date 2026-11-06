
from fastapi import FastAPI
from app.document import router as document_router
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Business Knowledge AI",
    description="Document-based AI assistant",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(
    document_router,
    prefix="/documents",
    tags=["Documents"]
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
