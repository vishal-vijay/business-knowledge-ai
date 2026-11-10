
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("all-MiniLM-L6-v2")


def split_text(text: str, chunk_size=150, overlap=30):
    words = text.split()
    chunks = []

    start = 0

    while start < len(words):
        end = start + chunk_size
        chunk = " ".join(words[start:end])

        if chunk.strip():
            chunks.append(chunk)

        start += chunk_size - overlap

    return chunks

def generate_embeddings(texts: list[str]):
    embeddings = model.encode(
        texts,
        normalize_embeddings=True
    )

    return embeddings.tolist()
