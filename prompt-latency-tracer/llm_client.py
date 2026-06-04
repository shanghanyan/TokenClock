# llm_client.py
import os
import time
from openai import OpenAI
from dotenv import load_dotenv
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def run_traced_prompt(tracer, prompt: str) -> dict:
    with tracer.start_as_current_span("llm.full_pipeline") as root_span:
        root_span.set_attribute("prompt.text", prompt[:200])
        root_span.set_attribute("model.name", os.getenv("MODEL_NAME"))

        # --- Stage 1: Prompt Preparation ---
        with tracer.start_as_current_span("llm.prompt_preparation") as prep_span:
            start = time.time()

            messages = [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt}
            ]
            prompt_tokens_estimate = len(prompt.split())

            prep_span.set_attribute("prompt.word_count", prompt_tokens_estimate)
            prep_span.set_attribute("prompt.length_chars", len(prompt))
            prep_span.set_attribute("stage.duration_ms", round((time.time() - start) * 1000, 2))

        # --- Stage 2: Model Inference ---
        with tracer.start_as_current_span("llm.inference") as infer_span:
            start = time.time()
            try:
                response = client.chat.completions.create(
                    model=os.getenv("MODEL_NAME"),
                    messages=messages
                )
                duration = round((time.time() - start) * 1000, 2)

                infer_span.set_attribute("inference.duration_ms", duration)
                infer_span.set_attribute("tokens.prompt", response.usage.prompt_tokens)
                infer_span.set_attribute("tokens.completion", response.usage.completion_tokens)
                infer_span.set_attribute("tokens.total", response.usage.total_tokens)
                infer_span.set_attribute("model.finish_reason", response.choices[0].finish_reason)
                infer_span.set_status(Status(StatusCode.OK))

            except Exception as e:
                infer_span.set_status(Status(StatusCode.ERROR, str(e)))
                infer_span.record_exception(e)
                raise

        # --- Stage 3: Post Processing ---
        with tracer.start_as_current_span("llm.post_processing") as post_span:
            start = time.time()

            raw_text = response.choices[0].message.content
            word_count = len(raw_text.split())
            cleaned = raw_text.strip()

            post_span.set_attribute("response.word_count", word_count)
            post_span.set_attribute("response.length_chars", len(cleaned))
            post_span.set_attribute("stage.duration_ms", round((time.time() - start) * 1000, 2))

        root_span.set_attribute("pipeline.total_tokens", response.usage.total_tokens)
        root_span.set_attribute("pipeline.success", True)

        return {
            "prompt": prompt,
            "response": cleaned,
            "tokens": response.usage.total_tokens
        }
