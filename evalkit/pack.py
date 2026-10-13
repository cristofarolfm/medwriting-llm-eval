"""Build one self-contained prompt per task (same text for every model)."""
import pathlib

SYSTEM = """You are a medical writer working in medical affairs. Follow these rules:
1. Use only the information in SOURCES. Do not use background knowledge, even if you believe it is correct.
2. If the SOURCES do not contain the answer, say so explicitly instead of guessing.
3. Copy every number exactly as it appears in the SOURCES, and say which source it came from.
4. Be accurate, fair-balanced and non-promotional. Do not compare products that were not compared in the same trial.
5. Follow the requested format and length."""


def build(task, src_dir: pathlib.Path):
    parts = [SYSTEM, "", "SOURCES", "======="]
    for name in task["sources"]:
        parts += ["", f"--- SOURCE: {name} ---", (src_dir / name).read_text(encoding="utf-8")]
    parts += ["", "TASK", "====", task["prompt"]]
    return "\n".join(parts)
