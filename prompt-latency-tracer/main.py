# main.py
import argparse
import time
from tracer import setup_tracer
from llm_client import run_traced_prompt


BUILTIN_PROMPTS = [
    "What is 2 + 2?",
    "Explain how neural networks work in 3 sentences.",
    "Write a detailed comparison of REST vs GraphQL APIs including pros, cons, and use cases.",
]


def run_prompt(tracer, prompt: str):
    """Run a single prompt, print results, and return the result dict."""
    print(f"\n{'─' * 60}")
    print(f"Prompt: {prompt[:80]}{'...' if len(prompt) > 80 else ''}")
    print(f"{'─' * 60}")

    try:
        result = run_traced_prompt(tracer, prompt)
    except Exception as e:
        print(f"Error       : {e}")
        return None

    lat = result["latency"]
    print(f"Tokens used : {result['tokens']}")
    print(f"Latency     : {lat['total_ms']} ms "
          f"(prep {lat['prep_ms']} / inference {lat['inference_ms']} / post {lat['post_ms']})")
    print(f"Response    : {result['response'][:200]}{'...' if len(result['response']) > 200 else ''}")
    return result


def print_summary(results):
    """Print a latency/token summary table for all prompts in this run."""
    results = [r for r in results if r]
    if not results:
        return
    print(f"\n{'═' * 72}")
    print("Latency summary")
    print(f"{'═' * 72}")
    print(f"{'#':<3}{'total ms':>10}{'inference ms':>14}{'tokens':>9}  prompt")
    print(f"{'-' * 72}")
    total_ms = 0.0
    total_tokens = 0
    for i, r in enumerate(results, 1):
        lat = r["latency"]
        total_ms += lat["total_ms"]
        total_tokens += r["tokens"]
        preview = r["prompt"][:34] + ("…" if len(r["prompt"]) > 34 else "")
        print(f"{i:<3}{lat['total_ms']:>10.1f}{lat['inference_ms']:>14.1f}{r['tokens']:>9}  {preview}")
    print(f"{'-' * 72}")
    n = len(results)
    print(f"{'avg':<3}{total_ms / n:>10.1f}{'':>14}{total_tokens // n:>9}")
    print(f"{'sum':<3}{total_ms:>10.1f}{'':>14}{total_tokens:>9}")


def mode_builtin(tracer):
    """Run the three built-in test prompts with a short gap between each."""
    print("\n[Mode] Running built-in test prompts...\n")
    results = []
    for prompt in BUILTIN_PROMPTS:
        results.append(run_prompt(tracer, prompt))
        time.sleep(2)
    return results


def mode_single(tracer, prompt: str):
    """Run a single user-supplied prompt."""
    print("\n[Mode] Single prompt\n")
    return [run_prompt(tracer, prompt)]


def mode_interactive(tracer):
    """
    Interactive REPL: user types prompts one at a time.
    Type 'exit' or 'quit' or press Ctrl+C to stop.
    """
    print("\n[Mode] Interactive — type your prompt and press Enter.")
    print("       Type 'exit' or 'quit' to stop.\n")

    results = []
    while True:
        try:
            prompt = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting.")
            break

        if not prompt:
            continue
        if prompt.lower() in {"exit", "quit"}:
            print("Exiting.")
            break

        results.append(run_prompt(tracer, prompt))
    return results


def main():
    parser = argparse.ArgumentParser(
        description="Prompt-to-response latency tracer with OpenTelemetry + Dynatrace"
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="Start an interactive prompt loop"
    )
    group.add_argument(
        "--prompt", "-p",
        type=str,
        metavar="TEXT",
        help="Run a single prompt and exit (wrap in quotes)"
    )
    args = parser.parse_args()

    tracer, provider = setup_tracer()

    results = []
    try:
        if args.interactive:
            results = mode_interactive(tracer)
        elif args.prompt:
            results = mode_single(tracer, args.prompt)
        else:
            results = mode_builtin(tracer)
    finally:
        print_summary(results)
        # Flush all pending spans before the process exits
        provider.force_flush()
        print("\nTraces written locally (see ./traces/spans.jsonl). "
              "Run 'python report.py' for an aggregated view.")


if __name__ == "__main__":
    main()
