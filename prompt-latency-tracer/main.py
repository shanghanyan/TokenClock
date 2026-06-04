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

    result = run_traced_prompt(tracer, prompt)

    print(f"Tokens used : {result['tokens']}")
    print(f"Response    : {result['response'][:200]}{'...' if len(result['response']) > 200 else ''}")
    return result


def mode_builtin(tracer):
    """Run the three built-in test prompts with a short gap between each."""
    print("\n[Mode] Running built-in test prompts...\n")
    for prompt in BUILTIN_PROMPTS:
        run_prompt(tracer, prompt)
        time.sleep(2)


def mode_single(tracer, prompt: str):
    """Run a single user-supplied prompt."""
    print("\n[Mode] Single prompt\n")
    run_prompt(tracer, prompt)


def mode_interactive(tracer):
    """
    Interactive REPL: user types prompts one at a time.
    Type 'exit' or 'quit' or press Ctrl+C to stop.
    """
    print("\n[Mode] Interactive — type your prompt and press Enter.")
    print("       Type 'exit' or 'quit' to stop.\n")

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

        run_prompt(tracer, prompt)


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

    try:
        if args.interactive:
            mode_interactive(tracer)
        elif args.prompt:
            mode_single(tracer, args.prompt)
        else:
            mode_builtin(tracer)
    finally:
        # Flush all pending spans before the process exits
        provider.force_flush()
        print("\nAll traces exported to Dynatrace.")


if __name__ == "__main__":
    main()
