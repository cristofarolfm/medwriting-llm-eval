"""Automatic checks. None of them uses an LLM.

Each check returns a dict: {"check": name, "passed": bool, "score": 0..1, "detail": str}.
The checks screen for objective failures (wrong or invented numbers, missing required
content, promotional words, reading level, failure to abstain). Judgment calls stay
with the human rubric in each task file.
"""
import re

NUM = re.compile(r"(?<![\w.])[<>≤≥]?\d+(?:,\d{3})*(?:\.\d+)?%?")


def _norm(n):
    return n.lstrip("<>≤≥").replace(",", "").rstrip("%").rstrip(".")


def numbers(text):
    return {_norm(m.group()) for m in NUM.finditer(text)}


def numbers_in_sources(output, sources_text, prompt_text="", ignore_below=10):
    """Every number in the output must appear in the sources (or the prompt). Small integers are ignored."""
    allowed = numbers(sources_text) | numbers(prompt_text)
    bad = []
    for n in sorted(numbers(output)):
        try:
            if float(n) < ignore_below and "." not in n:
                continue
        except ValueError:
            continue
        if n not in allowed:
            bad.append(n)
    return {"check": "numbers_in_sources", "passed": not bad, "score": 1.0 if not bad else 0.0,
            "detail": "all numbers found in sources" if not bad else "not in sources: " + ", ".join(bad)}


def required_any(output, groups):
    """groups: {label: [regex, ...]}; each group passes if any regex matches (case-insensitive)."""
    missing = [label for label, pats in groups.items()
               if not any(re.search(p, output, re.I | re.S) for p in pats)]
    n = len(groups) or 1
    return {"check": "required_content", "passed": not missing, "score": round(1 - len(missing) / n, 2),
            "detail": "all present" if not missing else "missing: " + "; ".join(missing)}


def forbidden(output, patterns):
    hits = sorted({m.group(0) for p in patterns for m in re.finditer(p, output, re.I)})
    return {"check": "forbidden_language", "passed": not hits, "score": 1.0 if not hits else 0.0,
            "detail": "none" if not hits else "found: " + ", ".join(hits)}


def word_count(text):
    return len(re.findall(r"[A-Za-z0-9][A-Za-z0-9'’\-.%]*", text))


def max_words(output, limit):
    n = word_count(output)
    return {"check": "max_words", "passed": n <= limit, "score": 1.0 if n <= limit else 0.0,
            "detail": f"{n} words (limit {limit})"}


def _syllables(word):
    w = re.sub(r"[^a-z]", "", word.lower())
    if not w:
        return 0
    groups = re.findall(r"[aeiouy]+", w)
    s = len(groups)
    if w.endswith("e") and not w.endswith(("le", "ee")) and s > 1:
        s -= 1
    return max(s, 1)


def fk_grade(text):
    """Flesch-Kincaid grade level (approximate syllable counter)."""
    body = re.sub(r"^#.*$", "", text, flags=re.M)
    sentences = max(len(re.findall(r"[.!?](\s|$)", body)), 1)
    words = re.findall(r"[A-Za-z]+", body)
    if not words:
        return 0.0
    syl = sum(_syllables(w) for w in words)
    return round(0.39 * len(words) / sentences + 11.8 * syl / len(words) - 15.59, 1)


def max_grade(output, limit):
    g = fk_grade(output)
    return {"check": "reading_level", "passed": g <= limit, "score": 1.0 if g <= limit else 0.0,
            "detail": f"Flesch-Kincaid grade {g} (limit {limit})"}


def planted_errors(output, errors):
    """errors: [{"id", "description", "detect_any": [regex]}]; score = share of planted errors flagged."""
    found = [e["id"] for e in errors if any(re.search(p, output, re.I | re.S) for p in e["detect_any"])]
    missed = [e["id"] for e in errors if e["id"] not in found]
    n = len(errors) or 1
    return {"check": "planted_errors", "passed": not missed, "score": round(len(found) / n, 2),
            "detail": f"{len(found)}/{len(errors)} flagged" + (f"; missed: {', '.join(missed)}" if missed else "")}


def run_checks(output, cfg, sources_text, prompt_text):
    """cfg: the task's "auto_checks" dict."""
    res = []
    if cfg.get("numbers_in_sources", True):
        res.append(numbers_in_sources(output, sources_text, prompt_text))
    if cfg.get("required"):
        res.append(required_any(output, cfg["required"]))
    if cfg.get("forbidden"):
        res.append(forbidden(output, cfg["forbidden"]))
    if cfg.get("max_words"):
        res.append(max_words(output, cfg["max_words"]))
    if cfg.get("max_grade"):
        res.append(max_grade(output, cfg["max_grade"]))
    if cfg.get("planted_errors"):
        res.append(planted_errors(output, cfg["planted_errors"]))
    return res
