# llm_client.py
import os
import time
from google import genai
from google.genai import types
from google.genai import errors as genai_errors
from dotenv import load_dotenv
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

import usage

load_dotenv()


def _load_keys():
    """
    Collect Google API keys in priority order. Supports a comma-separated
    GOOGLE_API_KEY and an optional GOOGLE_API_KEY_2 fallback. When the active
    key hits its daily quota (429), we rotate to the next key automatically.
    """
    keys = []
    for raw in (os.getenv("GOOGLE_API_KEY", ""), os.getenv("GOOGLE_API_KEY_2", "")):
        for k in raw.split(","):
            k = k.strip()
            if k and k not in keys:
                keys.append(k)
    return keys


_KEYS = _load_keys()
_key_idx = 0
_clients = {}

# Transient errors are retried on the same key; quota (429) rotates keys first.
_TRANSIENT = {500, 502, 503, 504}
_QUOTA = 429
_MAX_RETRIES = 4


def _client():
    if not _KEYS:
        raise RuntimeError("No Google API key set. Add GOOGLE_API_KEY to .env")
    key = _KEYS[_key_idx]
    if key not in _clients:
        _clients[key] = genai.Client(api_key=key)
    return _clients[key]


def _rotate_key():
    """Advance to the next available key. Returns True if one was available."""
    global _key_idx
    if _key_idx + 1 < len(_KEYS):
        _key_idx += 1
        print(f"  [key] quota hit — switching to Google API key #{_key_idx + 1}/{len(_KEYS)}")
        return True
    return False


def _generate_with_retry(**kwargs):
    delay = 1.0
    attempt = 0
    while True:
        attempt += 1
        key = _KEYS[_key_idx]
        try:
            usage.record_request(key)
            return _client().models.generate_content(**kwargs)
        except genai_errors.APIError as e:
            code = getattr(e, "code", None)
            if code == _QUOTA:
                usage.mark_exhausted(key)
                if _rotate_key():
                    delay, attempt = 1.0, 0  # fresh budget on the new key
                    continue
            if code in (_TRANSIENT | {_QUOTA}) and attempt < _MAX_RETRIES:
                print(f"  [retry] model {code}, attempt {attempt}/{_MAX_RETRIES - 1}; "
                      f"waiting {delay:.0f}s...")
                time.sleep(delay)
                delay *= 2
                continue
            raise


def run_traced_prompt(tracer, prompt: str) -> dict:
    with tracer.start_as_current_span("llm.full_pipeline") as root_span:
        root_span.set_attribute("prompt.text", prompt[:200])
        root_span.set_attribute("model.name", os.getenv("MODEL_NAME"))

        # --- Stage 1: Prompt Preparation ---
        with tracer.start_as_current_span("llm.prompt_preparation") as prep_span:
            start = time.time()

            config = types.GenerateContentConfig(
                system_instruction="You are a helpful assistant."
            )
            prompt_tokens_estimate = len(prompt.split())

            prep_ms = round((time.time() - start) * 1000, 2)
            prep_span.set_attribute("prompt.word_count", prompt_tokens_estimate)
            prep_span.set_attribute("prompt.length_chars", len(prompt))
            prep_span.set_attribute("stage.duration_ms", prep_ms)

        # --- Stage 2: Model Inference ---
        with tracer.start_as_current_span("llm.inference") as infer_span:
            start = time.time()
            try:
                response = _generate_with_retry(
                    model=os.getenv("MODEL_NAME"),
                    contents=prompt,
                    config=config
                )
                duration = round((time.time() - start) * 1000, 2)

                usage = response.usage_metadata
                infer_span.set_attribute("inference.duration_ms", duration)
                infer_span.set_attribute("tokens.prompt", usage.prompt_token_count)
                infer_span.set_attribute("tokens.completion", usage.candidates_token_count)
                infer_span.set_attribute("tokens.total", usage.total_token_count)
                infer_span.set_attribute("model.finish_reason", str(response.candidates[0].finish_reason))
                infer_span.set_status(Status(StatusCode.OK))

            except Exception as e:
                infer_span.set_status(Status(StatusCode.ERROR, str(e)))
                infer_span.record_exception(e)
                raise

        # --- Stage 3: Post Processing ---
        with tracer.start_as_current_span("llm.post_processing") as post_span:
            start = time.time()

            raw_text = response.text
            word_count = len(raw_text.split())
            cleaned = raw_text.strip()

            post_ms = round((time.time() - start) * 1000, 2)
            post_span.set_attribute("response.word_count", word_count)
            post_span.set_attribute("response.length_chars", len(cleaned))
            post_span.set_attribute("stage.duration_ms", post_ms)

        total_tokens = response.usage_metadata.total_token_count
        root_span.set_attribute("pipeline.total_tokens", total_tokens)
        root_span.set_attribute("pipeline.success", True)

        return {
            "prompt": prompt,
            "response": cleaned,
            "tokens": total_tokens,
            "latency": {
                "prep_ms": prep_ms,
                "inference_ms": duration,
                "post_ms": post_ms,
                "total_ms": round(prep_ms + duration + post_ms, 2),
            },
        }
