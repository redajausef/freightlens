"""Run from this project directory. Environment variables override .env values."""

from pathlib import Path

import uvicorn
from dotenv import load_dotenv

if __name__ == "__main__":
    load_dotenv(Path(__file__).parent / ".env", override=False)
    uvicorn.run("freightlens.api:app", host="127.0.0.1", port=8765)
