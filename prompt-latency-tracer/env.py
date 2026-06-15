"""Load environment variables from prompt-latency-tracer/.env."""
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")
