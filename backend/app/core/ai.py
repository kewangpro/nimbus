import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional
import os

CHAT_MODEL = os.getenv("MLX_CHAT_MODEL", "mlx-community/gemma-3-4b-it-4bit")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-ai/nomic-embed-text-v1")

_mlx_model = None
_mlx_tokenizer = None
_embedding_model = None
# MLX is not thread-safe; single worker ensures sequential GPU access
_executor = ThreadPoolExecutor(max_workers=1)


def _get_chat_model():
    global _mlx_model, _mlx_tokenizer
    if _mlx_model is None:
        try:
            from mlx_lm import load
            _mlx_model, _mlx_tokenizer = load(CHAT_MODEL)
        except (ImportError, ModuleNotFoundError) as e:
            print(f"MLX model loading failed: {e}. Note that MLX is Apple Silicon exclusive and cannot run inside a Linux Docker container.")
            raise
    return _mlx_model, _mlx_tokenizer


def _get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer
        _embedding_model = SentenceTransformer(EMBEDDING_MODEL, trust_remote_code=True)
    return _embedding_model


def _sync_generate(prompt: str, system_prompt: str) -> str:
    from mlx_lm import generate
    model, tokenizer = _get_chat_model()

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    if hasattr(tokenizer, "apply_chat_template"):
        formatted = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
    else:
        formatted = f"{system_prompt}\n{prompt}" if system_prompt else prompt

    res = generate(model, tokenizer, prompt=formatted, verbose=False, max_tokens=2048)
    try:
        import mlx.core as mx
        mx.metal.clear_cache()
    except Exception:
        pass
    return res


def _sync_embed(text: str) -> List[float]:
    model = _get_embedding_model()
    return model.encode(text, normalize_embeddings=True).tolist()


async def generate_embedding(text: str) -> Optional[List[float]]:
    try:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_executor, _sync_embed, text)
    except Exception as e:
        print(f"Error generating embedding: {e}")
        return None


async def generate_completion(prompt: str, system_prompt: str = "") -> Optional[str]:
    try:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_executor, _sync_generate, prompt, system_prompt)
    except Exception as e:
        print(f"Error generating completion: {e}")
        return None
