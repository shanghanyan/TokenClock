# llm_client.py
import os
import time
from google import genai
from google.genai import types
from google.genai import errors as genai_errors
from dotenv import load_dotenv
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

load_dotenv()
client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

# Gemini's free tier intermittently returns 503 UNAVAILABLE / 429. Retry those
# a few times with exponential backoff so a transient blip doesn't kill the run.
_RETRYABLE = {429, 500, 502, 503, 504}
_MAX_RETRIES = 4


def _generate_with_retry(**kwargs):
    delay = 1.0
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            return client.models.generate_content(**kwargs)
        except genai_errors.APIError as e:
            code = getattr(e, "code", None)
            if code in _RETRYABLE and attempt < _MAX_RETRIES:
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
