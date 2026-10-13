# medwriting-llm-eval: can an LLM do medical information work in oncology?

[![tests](https://github.com/cristofarolfm/medwriting-llm-eval/actions/workflows/tests.yml/badge.svg)](https://github.com/cristofarolfm/medwriting-llm-eval/actions/workflows/tests.yml)

> **Status: work in progress.** The tasks, sources and automatic checks are in place. The rubrics are drafts under expert review, and no model results have been published yet.

A small evaluation set of **9 realistic medical writing and medical information tasks** in advanced endometrial cancer. Each task gives the model a fixed set of public-domain sources (FDA prescribing information and ClinicalTrials.gov results) and asks for something a medical writer, medical information specialist or MSL produces at work. Each answer is then scored two ways:

1. **Automatic checks (no LLM):** numbers that do not appear in the sources, missing required content, promotional language, word limits, reading level, failure to abstain, and recall of planted errors.
2. **A human rubric** for the judgment calls the checks cannot make, such as fair balance, correct interpretation of exploratory analyses and refusing cross-trial comparisons.

## The tasks

| ID | Task | What it tests |
|---|---|---|
| T01 | Medical information letter: dostarlimab in MMRp/MSS endometrial cancer | Keeping exploratory subgroup results apart from the significant overall result |
| T02 | Extract the RUBY efficacy table | Exact transcription, including "NR" and "Not tested" |
| T03 | Plain-language summary of NRG-GY018 | Reading level of grade 8 or lower without losing accuracy; saying what is not yet known |
| T04 | Speaker note from two sources on KEYNOTE-868/NRG-GY018 | Noticing that the label and the registry report **different analyses** of the same trial |
| T05 | Fact-check a draft with 5 planted errors | Error recall without false positives |
| T06 | Rewrite a promotional claim with fair balance | Compliance judgment |
| T07 | "Which is better, dostarlimab or pembrolizumab?" | Declining a cross-trial comparison while staying helpful |
| T08 | Questions the sources cannot answer | Abstaining instead of using background knowledge |
| T09 | Lenvatinib plus pembrolizumab after platinum (pMMR) | Recognizing that **Study 309** and **KEYNOTE-775** are one trial; dosing and safety from two labels |

## Sources

All sources are public domain and are regenerated with `python run.py fetch`:

- JEMPERLI (dostarlimab), KEYTRUDA (pembrolizumab) and LENVIMA (lenvatinib) prescribing information via [openFDA](https://open.fda.gov/), endometrial sections only.
- NRG-GY018 (NCT03914612) and DUO-E (NCT04269200) posted results via the [ClinicalTrials.gov API](https://clinicaltrials.gov/data-api/api).

Tables in the labels are converted to Markdown so that every number the model needs is in plain text.

## Run it

```bash
python run.py fetch    # download the sources
python run.py pack     # one self-contained prompt per task in packs/
# paste each pack into a model; save answers as outputs/<model>/<task_id>.md
python run.py score    # automatic checks -> results/auto_scores.csv
# grade the rubric in grades/human_grades.csv (template provided)
python run.py report   # results/results.md
python -m pytest tests
```

No API key is needed: the same pack goes into any chat interface, which keeps the comparison fair across models.

## Design notes

- Every task ships with the reviewer notes that explain the trap in it, so the grading is transparent.
- The automatic checks are deliberately simple. They catch objective failures cheaply, and the human rubric decides whether an answer would be acceptable at work.
- Companion project: [cme-evidence-pipeline](https://github.com/cristofarolfm/cme-evidence-pipeline), a draft-then-verify pipeline for CME needs assessments.

## Author

Designed by Luis F. M. Di Cristofaro, PhD (pharmacist-scientist, oncology). The code was written with Claude Code as a pair programmer.
