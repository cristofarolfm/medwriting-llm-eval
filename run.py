"""medwriting-llm-eval command line.

  python run.py fetch     # download sources into sources/ (openFDA labels, ClinicalTrials.gov results)
  python run.py pack      # write one prompt per task into packs/ (paste into any model)
  python run.py score     # automatic checks on outputs/<model>/<task_id>.md -> results/auto_scores.csv
  python run.py report    # combine automatic checks and human grades -> results/results.md
"""
import argparse
import csv
import json
import pathlib
from collections import defaultdict

from evalkit import checks as C
from evalkit import pack as P
from evalkit import sources as S

ROOT = pathlib.Path(__file__).parent
SRC, TASKS, PACKS = ROOT / "sources", ROOT / "tasks", ROOT / "packs"
OUTPUTS, GRADES, RESULTS = ROOT / "outputs", ROOT / "grades", ROOT / "results"


def load_tasks():
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(TASKS.glob("T*.json"))]


def cmd_fetch(_):
    cfg = json.loads((SRC / "sources.json").read_text(encoding="utf-8"))
    for lab in cfg["labels"]:
        md = S.label_to_markdown(S.fetch_label(lab["set_id"]), lab["title"], lab["sections"],
                                 lab.get("subsection_filter"), lab.get("table_filter"))
        (SRC / lab["file"]).write_text(md, encoding="utf-8")
        print(f"{lab['file']}: {len(md):,} chars")
    for st in cfg["studies"]:
        md = S.study_results_to_markdown(S.fetch_study(st["nct"]))
        (SRC / st["file"]).write_text(md, encoding="utf-8")
        print(f"{st['file']}: {len(md):,} chars")


def cmd_pack(_):
    PACKS.mkdir(exist_ok=True)
    for t in load_tasks():
        text = P.build(t, SRC)
        (PACKS / f"{t['id']}.md").write_text(text, encoding="utf-8")
        print(f"{t['id']}: {len(text):,} chars")


def cmd_score(_):
    RESULTS.mkdir(exist_ok=True)
    tasks = {t["id"]: t for t in load_tasks()}
    rows = []
    for model_dir in sorted(p for p in OUTPUTS.iterdir() if p.is_dir()):
        for tid, t in tasks.items():
            f = model_dir / f"{tid}.md"
            if not f.exists():
                continue
            out = C.strip_comments(f.read_text(encoding="utf-8"))
            src = "\n".join((SRC / s).read_text(encoding="utf-8") for s in t["sources"])
            for r in C.run_checks(out, t.get("auto_checks", {}), src, t["prompt"]):
                rows.append({"model": model_dir.name, "task": tid, **r})
    with open(RESULTS / "auto_scores.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["model", "task", "check", "passed", "score", "detail"])
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} checks -> results/auto_scores.csv")
    for r in rows:
        if not r["passed"]:
            print(f"  FAIL {r['model']}/{r['task']}: {r['check']} ({r['detail']})")


def cmd_report(_):
    tasks = {t["id"]: t for t in load_tasks()}
    auto = defaultdict(list)
    p = RESULTS / "auto_scores.csv"
    if p.exists():
        for r in csv.DictReader(open(p, encoding="utf-8")):
            auto[(r["model"], r["task"])].append(float(r["score"]))
    human = defaultdict(float)
    g = GRADES / "human_grades.csv"
    if g.exists():
        for r in csv.DictReader(open(g, encoding="utf-8")):
            if r.get("points", "").strip():
                human[(r["model"], r["task"])] += float(r["points"])
    models = sorted({m for m, _ in auto} | {m for m, _ in human})
    lines = ["# Results", "", "Automatic = mean of the automatic checks (0-1). Human = rubric points awarded / maximum.", "",
             "| Task | " + " | ".join(models) + " |", "|---|" + "---|" * len(models)]
    for tid, t in tasks.items():
        maxp = sum(c["points"] for c in t["rubric"])
        cells = []
        for m in models:
            a = auto.get((m, tid))
            a_txt = f"{sum(a) / len(a):.2f}" if a else "–"
            h_txt = f"{human[(m, tid)]:g}/{maxp}" if (m, tid) in human else "–"
            cells.append(f"auto {a_txt} · human {h_txt}")
        lines.append(f"| {tid} | " + " | ".join(cells) + " |")
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "results.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for c in ("fetch", "pack", "score", "report"):
        sub.add_parser(c)
    a = ap.parse_args()
    {"fetch": cmd_fetch, "pack": cmd_pack, "score": cmd_score, "report": cmd_report}[a.cmd](a)


if __name__ == "__main__":
    main()
