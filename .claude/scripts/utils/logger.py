from pathlib import Path
from datetime import datetime

LOG_PATH = Path.cwd() / "claude-3PO" / "logs" / "workflow.log"


def format_message(message: str) -> str:
    date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return f"{date} - {message} - "


def log_message(message: str) -> None:
    if not LOG_PATH.parent.exists():
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not LOG_PATH.exists():
        LOG_PATH.touch()
    try:
        Path.write_text(LOG_PATH, format_message(message) + "\n")
    except Exception as e:
        raise Exception(f"Error logging message: {e}")
