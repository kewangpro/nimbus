import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional, Union
import os
import logging

from app.core.config import settings

CHAT_MODEL = settings.MLX_CHAT_MODEL
FAST_MODEL = settings.MLX_FAST_MODEL
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
    if model_name is None:
        model_name = CHAT_MODEL
    try:
        logger.info(f"Starting AI completion generation with model: {model_name}")
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            _executor, _sync_generate, prompt, system_prompt, model_name
        )
        logger.info(f"AI completion generation finished for model: {model_name}")
        return result
    except Exception as e:
        logger.error(f"Error generating completion with {model_name}: {e}")
        if model_name != FAST_MODEL and FAST_MODEL:
            logger.info(f"Attempting fallback generation with fast model: {FAST_MODEL}")
            try:
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    _executor, _sync_generate, prompt, system_prompt, FAST_MODEL
                )
                logger.info(f"AI completion generation finished for fallback model: {FAST_MODEL}")
                return result
            except Exception as fe:
                logger.error(f"Error generating completion with fallback model {FAST_MODEL}: {fe}")
        return None


def parse_json_robust(text: str) -> Optional[Union[dict, list]]:
    if not text or not text.strip():
        return None

    import json
    import re
    import ast
    from typing import Union

    # Pre-clean
    clean_text = text.strip()
    # Remove markdown code blocks if present (more robustly)
    clean_text = re.sub(r'```(?:json)?\s*(.*?)\s*```', r'\1', clean_text, flags=re.DOTALL | re.IGNORECASE)
    clean_text = re.sub(r'^```(?:json)?\s*', '', clean_text, flags=re.MULTILINE | re.IGNORECASE)
    clean_text = re.sub(r'\s*```$', '', clean_text, flags=re.MULTILINE)
    
    # Remove trailing comments (e.g., # or //) that break JSON
    clean_text = re.sub(r'[ \t]+[#//].*$', '', clean_text, flags=re.MULTILINE)
    clean_text = clean_text.strip()

    # Try full parse first (either as object or array)
    try:
        return json.loads(clean_text)
    except Exception:
        pass

    # Try ast.literal_eval for single-quoted "JSON"
    try:
        eval_text = clean_text.replace('null', 'None').replace('true', 'True').replace('false', 'False')
        parsed = ast.literal_eval(eval_text)
        if isinstance(parsed, (dict, list)):
            return parsed
    except Exception:
        pass

    # Brace-matching recovery for JSON object {...} or array [...]
    try:
        recovered_objects = []
        potential_jsons = re.findall(r'(\{.*\}|\[.*\])', clean_text, re.DOTALL)
        
        for candidate in potential_jsons:
            try:
                start_brace = candidate.find('{')
                end_brace = candidate.rfind('}')
                if start_brace != -1 and end_brace != -1:
                    obj_text = candidate[start_brace:end_brace+1]
                    # Clean comments again within the object text
                    obj_text = re.sub(r'\s*[#//].*$', '', obj_text, flags=re.MULTILINE)
                    obj = json.loads(obj_text)
                    if isinstance(obj, dict):
                        recovered_objects.append(obj)
                    elif isinstance(obj, list):
                        recovered_objects.extend([o for o in obj if isinstance(o, dict)])
            except Exception:
                continue

        if recovered_objects:
            if len(recovered_objects) == 1 and not clean_text.strip().startswith('['):
                return recovered_objects[0]
            return recovered_objects

        # Last ditch effort: simple brace matching for multiple objects
        last_end_idx = 0
        for match in re.finditer(r'\{', clean_text):
            start_idx = match.start()
            if start_idx < last_end_idx:
                continue
            depth = 0
            for i in range(start_idx, len(clean_text)):
                if clean_text[i] == '{':
                    depth += 1
                elif clean_text[i] == '}':
                    depth -= 1
                    if depth == 0:
                        candidate = clean_text[start_idx:i+1]
                        try:
                            obj = json.loads(candidate)
                            if isinstance(obj, dict):
                                recovered_objects.append(obj)
                                last_end_idx = i + 1
                        except Exception:
                            pass
                        break
        
        if recovered_objects:
            if len(recovered_objects) == 1 and not clean_text.strip().startswith('['):
                return recovered_objects[0]
            return recovered_objects
    except Exception:
        pass

    return None

