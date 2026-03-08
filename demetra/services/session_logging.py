import uuid
from pathlib import Path

from demetra.settings import LOG_DIR


def get_session_log_path(task_id: str | None = None) -> Path:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    if task_id is None:
        return LOG_DIR / f"tmp-{uuid.uuid4().hex[:8]}.log"
    return LOG_DIR / f"{task_id}.log"


def rename_temp_log(temp_path: Path, task_id: str) -> Path:
    new_path = LOG_DIR / f"{task_id}.log"
    if temp_path.exists():
        temp_path.rename(new_path)
    return new_path


def get_log_path_for_session(session_id: str) -> Path | None:
    log_files = list(LOG_DIR.glob("*.log"))
    for log_file in log_files:
        if session_id in log_file.stem:
            return log_file
    return None


def get_log_path_by_task_id(task_id: str) -> Path | None:
    log_path = LOG_DIR / f"{task_id}.log"
    return log_path if log_path.exists() else None
