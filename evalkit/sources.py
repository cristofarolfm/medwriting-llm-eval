"""Fetch public-domain source documents and save them as plain Markdown.

- FDA prescribing information via openFDA (drug label endpoint).
- Posted results from ClinicalTrials.gov (API v2).

Every task in tasks/ points to one or more of these files, and the model sees
only those files. Keeping the sources small and fixed is what makes the
outputs comparable across models.
"""
import json
import re
import time
import urllib.parse
import urllib.request
from html import unescape

OPENFDA = "https://api.fda.gov/drug/label.json"
CTGOV = "https://clinicaltrials.gov/api/v2/studies/"


def _get(url, tries=4):
    for i in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(2 ** i)


# ---------------------------------------------------------------- FDA labels

def fetch_label(set_id):
    q = urllib.parse.quote(f'set_id:"{set_id}"')
    return _get(f"{OPENFDA}?search={q}&limit=1")["results"][0]


def _section(text, heading_regex):
    """Return one numbered subsection (e.g. '14.3 Endometrial Carcinoma') up to the next one."""
    m = re.search(heading_regex, text)
    if not m:
        return ""
    nxt = re.search(r"\s\d{1,2}\.\d{1,2} [A-Z]", text[m.end():])
    end = m.end() + nxt.start() if nxt else len(text)
    return text[m.start():end].strip()


def html_table_to_markdown(html):
    """Flatten an SPL/HTML table into a caption plus Markdown rows (cells joined with |)."""
    cap = re.search(r"<caption>(.*?)</caption>", html, re.S)
    rows = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S):
        cells = [re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", c))).strip()
                 for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S)]
        if any(cells):
            rows.append("| " + " | ".join(cells) + " |")
    title = unescape(re.sub(r"<[^>]+>", "", cap.group(1))).strip() if cap else "Table"
    return f"**{title}**\n\n" + "\n".join(rows)


def label_to_markdown(label, title, sections, subsection_filter=None, table_filter=None):
    """sections: list of openFDA field names. subsection_filter: {field: regex} keeps only one subsection.
    table_filter: {field: regex}; tables of that field are kept only if their caption matches."""
    of = label.get("openfda", {})
    out = [f"# {title}",
           "",
           f"Source: FDA prescribing information via openFDA, set_id `{label.get('set_id')}`, "
           f"effective {label.get('effective_time')}. Brand: {', '.join(of.get('brand_name', []))}; "
           f"generic: {', '.join(of.get('generic_name', []))}.",
           ""]
    for field in sections:
        text = " ".join(label.get(field, []))
        if not text:
            continue
        if subsection_filter and field in subsection_filter:
            text = _section(text, subsection_filter[field]) or text
        out += [f"## {field.replace('_', ' ').title()}", "", text, ""]
        for html in label.get(field + "_table", []):
            cap = re.search(r"<caption>(.*?)</caption>", html, re.S)
            caption = cap.group(1) if cap else ""
            if table_filter and field in table_filter and not re.search(table_filter[field], caption):
                continue
            out += [html_table_to_markdown(html), ""]
    return "\n".join(out)


# ------------------------------------------------------- ClinicalTrials.gov

def fetch_study(nct):
    return _get(CTGOV + nct)


def _groups(lst):
    return {g["id"]: g.get("title", g["id"]) for g in lst or []}


def study_results_to_markdown(study, max_outcomes=6):
    p = study["protocolSection"]
    ident = p["identificationModule"]
    rs = study.get("resultsSection", {})
    out = [f"# {ident.get('acronym') or ident['nctId']}: {ident['briefTitle']}",
           "",
           f"Source: ClinicalTrials.gov posted results, {ident['nctId']} "
           f"(https://clinicaltrials.gov/study/{ident['nctId']}).",
           ""]
    design = p.get("designModule", {})
    out += [f"Phase: {', '.join(design.get('phases', []))}. "
            f"Enrollment: {design.get('enrollmentInfo', {}).get('count')}.", ""]

    base = rs.get("baselineCharacteristicsModule", {})
    if base:
        g = _groups(base.get("groups"))
        out += ["## Baseline participants", ""]
        for d in base.get("denoms", []):
            for c in d.get("counts", []):
                out.append(f"- {g.get(c['groupId'], c['groupId'])}: {c['value']} participants")
        out.append("")

    om = rs.get("outcomeMeasuresModule", {}).get("outcomeMeasures", [])
    for o in om[:max_outcomes]:
        g = _groups(o.get("groups"))
        out += [f"## Outcome ({o.get('type', '').lower()}): {o['title']}", "",
                f"Time frame: {o.get('timeFrame', '')}",
                f"Unit: {o.get('unitOfMeasure', '')}; measure: {o.get('paramType', '')}"
                + (f"; dispersion: {o['dispersionType']}" if o.get("dispersionType") else ""), ""]
        if o.get("populationDescription"):
            out += [f"Population: {o['populationDescription']}", ""]
        for cl in o.get("classes", []):
            label = cl.get("title")
            for cat in cl.get("categories", []):
                for m in cat.get("measurements", []):
                    rng = ""
                    if m.get("lowerLimit") or m.get("upperLimit"):
                        rng = f" ({m.get('lowerLimit', 'NA')} to {m.get('upperLimit', 'NA')})"
                    elif m.get("spread"):
                        rng = f" (spread {m['spread']})"
                    row = f"- {g.get(m['groupId'], m['groupId'])}"
                    if label:
                        row += f" [{label}]"
                    if cat.get("title"):
                        row += f" [{cat['title']}]"
                    out.append(f"{row}: {m.get('value')}{rng}")
        for a in o.get("analyses", []):
            bits = [a.get("statisticalMethod", "")]
            if a.get("paramType"):
                bits.append(f"{a['paramType']} {a.get('paramValue', '')}")
            if a.get("ciLowerLimit"):
                bits.append(f"{a.get('ciPctValue', '')}% CI {a['ciLowerLimit']} to {a.get('ciUpperLimit', '')}")
            if a.get("pValue"):
                bits.append(f"p {a['pValue']}")
            out.append("- Analysis: " + "; ".join(b for b in bits if b))
        out.append("")

    ae = rs.get("adverseEventsModule", {})
    if ae:
        out += ["## Adverse events (summary)", ""]
        for e in ae.get("eventGroups", []):
            out.append(f"- {e.get('title')}: serious AEs {e.get('seriousNumAffected')}/{e.get('seriousNumAtRisk')}; "
                       f"other AEs {e.get('otherNumAffected')}/{e.get('otherNumAtRisk')}; "
                       f"deaths {e.get('deathsNumAffected', 'NA')}/{e.get('deathsNumAtRisk', 'NA')}")
        out.append("")
    return "\n".join(out)
