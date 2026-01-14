import ollama
from typing import List, Optional
import os

# Get host from env or default to localhost
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")

# Configure async client
client = ollama.AsyncClient(host=OLLAMA_HOST)

EMBEDDING_MODEL = "nomic-embed-text"
CHAT_MODEL = "gemma3"

async def generate_embedding(text: str) -> Optional[List[float]]:
    try:
        response = await client.embeddings(model=EMBEDDING_MODEL, prompt=text)
        return response["embedding"]
    except Exception as e:
        print(f"Error generating embedding: {e}")
        return None

async def generate_completion(prompt: str, system_prompt: str = "") -> Optional[str]:
    try:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = await client.chat(model=CHAT_MODEL, messages=messages)
        return response["message"]["content"]
    except Exception as e:
        print(f"Error generating completion: {e}")
        return None
