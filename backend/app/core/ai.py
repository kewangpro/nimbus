import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional
import os
import logging

from app.core.config import settings

CHAT_MODEL = settings.MLX_CHAT_MODEL
EMAIL_MODEL = settings.MLX_EMAIL_MODEL
EMBEDDING_MODEL = settings.EMBEDDING_MODEL

logger = logging.getLogger(__name__)

_mlx_models = {}
_embedding_model = None
# MLX is not thread-safe; single worker ensures sequential GPU access
_executor = ThreadPoolExecutor(max_workers=1)


def _get_chat_model(model_name: str):
    if model_name not in _mlx_models:
        try:
            from mlx_lm import load
            logger.info(f"Loading chat model: {model_name}")
            model, tokenizer = load(model_name)
            _mlx_models[model_name] = (model, tokenizer)
        except (ImportError, ModuleNotFoundError) as e:
            logger.error(f"MLX model loading failed for {model_name}: {e}")
            print(f"MLX model loading failed: {e}. Note that MLX is Apple Silicon exclusive and cannot run inside a Linux Docker container.")
            raise
    return _mlx_models[model_name]


def _get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer
        logger.info(f"Loading embedding model: {EMBEDDING_MODEL}")
        _embedding_model = SentenceTransformer(EMBEDDING_MODEL, trust_remote_code=True)
    return _embedding_model


def _sync_generate(prompt: str, system_prompt: str, model_name: str) -> str:
    from mlx_lm import generate
    model, tokenizer = _get_chat_model(model_name)

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

    logger.debug(f"Generating completion with prompt: {prompt[:100]}...")
    # Increased max_tokens to 4096 to ensure full JSON for up to 100 tasks
    res = generate(model, tokenizer, prompt=formatted, verbose=False, max_tokens=4096)
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
        logger.error(f"Error generating embedding: {e}")
        return None


async def generate_completion(
    prompt: str, system_prompt: str = "", model_name: Optional[str] = None
) -> Optional[str]:
    try:
        if model_name is None:
            model_name = CHAT_MODEL
        logger.info(f"Starting AI completion generation with model: {model_name}")
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            _executor, _sync_generate, prompt, system_prompt, model_name
        )
        logger.info(f"AI completion generation finished for model: {model_name}")
        return result
    except Exception as e:
        logger.error(f"Error generating completion: {e}")
        return None
