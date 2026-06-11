#!/usr/bin/env python3
"""CLI entry point for the TokenClock prompt-optimization agent."""
import argparse
import sys

from tracer import setup_tracer

try:
    from tokenclock_agent.runner import optimize_prompt
except ImportError:
        print("Install agent deps: pip install google-adk", file=sys.stderr)
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Run the TokenClock ADK agent to optimize a prompt for fewer tokens/latency."
    )
    parser.add_argument("prompt", nargs="?", help="Prompt to optimize")
    parser.add_argument("-p", "--prompt-flag", dest="prompt_flag", help="Prompt (alternative to positional)")
    args = parser.parse_args()
    prompt = (args.prompt_flag or args.prompt or "").strip()
    if not prompt:
        parser.error("Provide a prompt as an argument or with -p")

    tracer, provider = setup_tracer()
    print("Running TokenClock agent (Gemini + ADK)…\n")
    result = optimize_prompt(prompt, tracer=tracer, provider=provider)
    if result.error and not result.final_text:
        print(f"Error: {result.error}", file=sys.stderr)
        sys.exit(1)
    print(result.final_text)
    if result.error:
        print(f"\n(warning: {result.error})", file=sys.stderr)


if __name__ == "__main__":
    main()
