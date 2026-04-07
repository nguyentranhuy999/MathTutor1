"""Shared input file locations for debug scripts and src modules."""
from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INPUT_DIR = PROJECT_ROOT / "input"
PROBLEM_INPUT_PATH = INPUT_DIR / "problem.txt"
ANSWER_INPUT_PATH = INPUT_DIR / "answer.txt"


def read_text(path: Path, label: str) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Thieu {label}: {path}")

    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError(f"{label} dang rong: {path}")
    return text


def read_problem_text() -> str:
    return read_text(PROBLEM_INPUT_PATH, "de bai")


def read_answer_text() -> str:
    return read_text(ANSWER_INPUT_PATH, "bai lam hoc sinh")
