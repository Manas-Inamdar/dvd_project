"""Load config/project.yaml and resolve repository paths."""
from pathlib import Path
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]


def load_config(path: str | Path | None = None) -> dict:
    path = Path(path) if path else REPO_ROOT / "config" / "project.yaml"
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def model_path(cfg: dict) -> Path:
    return REPO_ROOT / cfg["assignment"]["model_file"]
