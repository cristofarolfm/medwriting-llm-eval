import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from evalkit import checks as C  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = "The median OS was 44.6 months (95% CI 32.6, NR); HR 0.69 (0.54, 0.89) in 494 patients; 85.9% responded."


def test_numbers_all_in_source():
    r = C.numbers_in_sources("Median OS 44.6 months, HR 0.69, n = 494.", SRC)
    assert r["passed"], r


def test_numbers_drift_flagged():
    r = C.numbers_in_sources("Median OS 46.4 months.", SRC)
    assert not r["passed"] and "46.4" in r["detail"]


def test_small_integers_and_prompt_numbers_ignored():
    r = C.numbers_in_sources("Two arms, 3 cycles, within 250 words.", SRC, prompt_text="Write 150-250 words")
    assert r["passed"], r


def test_percent_and_comparators_normalized():
    r = C.numbers_in_sources("85.9% and p <0.89", SRC)
    assert r["passed"], r


def test_required_any_partial_score():
    r = C.required_any("This was exploratory.", {"a": [r"exploratory"], "b": [r"0\.82"]})
    assert not r["passed"] and r["score"] == 0.5 and "b" in r["detail"]


def test_forbidden_language():
    r = C.forbidden("A breakthrough with minimal side effects.", [r"\bbreakthrough\b", r"minimal side effects"])
    assert not r["passed"] and "breakthrough" in r["detail"]


def test_reading_level_orders_texts():
    easy = "The drug helped some people. They lived longer without the cancer growing. Some had side effects."
    hard = ("Pembrolizumab administered concomitantly with carboplatin-paclitaxel demonstrated statistically "
            "significant prolongation of investigator-assessed progression-free survival irrespective of mismatch repair status.")
    assert C.fk_grade(easy) < 8 < C.fk_grade(hard)


def test_planted_errors_recall():
    errs = [{"id": "E1", "detect_any": [r"494"]}, {"id": "E2", "detect_any": [r"44\.6"]}]
    r = C.planted_errors('"449 patients" -> 494 patients (Clinical Studies 14.1)', errs)
    assert r["score"] == 0.5 and "E2" in r["detail"]


def test_task_files_valid():
    for p in sorted((ROOT / "tasks").glob("T*.json")):
        t = json.loads(p.read_text(encoding="utf-8"))
        for key in ("id", "type", "sources", "prompt", "auto_checks", "rubric", "status"):
            assert key in t, f"{p.name} missing {key}"
        assert t["id"] == p.stem
        for s in t["sources"]:
            assert (ROOT / "sources" / s).exists(), f"{p.name}: missing source {s}"
        for pats in t["auto_checks"].get("required", {}).values():
            for pat in pats:
                re.compile(pat)
        assert sum(c["points"] for c in t["rubric"]) > 0


def test_provenance_header_ignored():
    out = C.strip_comments("<!-- Model X 5.5, 13 Oct 2026 -->\n\nMedian OS 44.6 months.")
    assert C.numbers_in_sources(out, SRC)["passed"] and C.word_count(out) == 4


def test_forbidden_ignores_negated_use():
    pats = [r"\bsuperior\b"]
    assert C.forbidden("It is not possible to conclude that one regimen is superior.", pats)["passed"]
    assert not C.forbidden("JEMPERLI is superior to pembrolizumab.", pats)["passed"]
