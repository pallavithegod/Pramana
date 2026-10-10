"""Load local configuration before storage and route modules are imported."""

from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[4] / ".env.pramana", override=False)
