"""X5_doc_label analysis: is the X2 gain (and the removal of the front-position weakness) from the user task or from the
{"document": ...} wrapper? Compares the same EN documents under three inputs (no API calls):

    A  01_baseline   state = document string
    B  X5_doc_label  state = {"document": document}
    C  X2_user_task  state = {"user_task": task, "document": document}

    python experiments/analyze_X5_doc_label.py
"""
import json
import os
import re
import sys

import numpy as np
import pandas as pd
from scipy.stats import binomtest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import jevlab as J  # noqa: E402

OUT = os.path.join(J.RESULTS, "X5_doc_label")
EN = os.path.join(J.DATA, "en", "dataset_en_1000.jsonl")
# Overt attack markers (post hoc, same pattern as the report's front-position analysis).
MARKER = re.compile(r"ignore (?:all |your )?(?:previous|prior)|disregard (?:prior|previous)|system override|important!|"
                    r"attention:|system_message|<information>", re.I)
COND = {"A_doc_only": "01_baseline", "B_doc_label": "X5_doc_label", "C_task": "X2_user_task"}


def load(qid):
    en = pd.DataFrame(J.load_jsonl(EN))
    en = en[["uid", "label_int", "source", "text", "injected_instruction"]]
    for name, exp in COND.items():
        df = pd.read_csv(os.path.join(J.RESULTS, exp, f"{qid}_predictions.csv"))
        key = "uid" if name == "A_doc_only" else "base_uid"
        en = en.merge(df[[key, "p"]].rename(columns={key: "uid", "p": name}), on="uid")
    inj = en["injected_instruction"]
    has = [isinstance(s, str) and s in t for s, t in zip(inj, en["text"])]
    en["first_line"] = [h and t.index(s) <= 2 for h, s, t in zip(has, inj, en["text"])]
    en["marker"] = [isinstance(s, str) and bool(MARKER.search(s)) for s in inj]
    return en


def rates(df):
    row = {"n": len(df)}
    for c in COND:
        row[c] = 100 * (df[c] >= J.THRESHOLD).mean()
    return row


def mcnemar(df, a, b):
    """Exact McNemar on the 0.5 decision: (only a detects, only b detects, p)."""
    x, y = df[a] >= J.THRESHOLD, df[b] >= J.THRESHOLD
    n01, n10 = int((x & ~y).sum()), int((~x & y).sum())
    p = binomtest(n10, n01 + n10, 0.5).pvalue if n01 + n10 else 1.0
    return n01, n10, p


def main():
    os.makedirs(os.path.join(OUT, "tables"), exist_ok=True)
    rows = []
    for qid in ("Q2", "QL"):
        en = load(qid)
        inj, ben = en[en.label_int == 1], en[en.label_int == 0]
        groups = {
            "all injections (TPR)": inj,
            "benign (FPR)": ben,
            "injections, no marker, first line": inj[~inj.marker & inj.first_line],
            "injections, no marker, not first line": inj[~inj.marker & ~inj.first_line],
            "injections, with marker": inj[inj.marker],
            "BIPIA injections, first line": inj[(inj.source == "BIPIA") & inj.first_line],
            "BIPIA injections, not first line": inj[(inj.source == "BIPIA") & ~inj.first_line],
        }
        for g, df in groups.items():
            r = {"question": qid, "group": g, **rates(df)}
            for a, b in (("A_doc_only", "B_doc_label"), ("B_doc_label", "C_task")):
                n01, n10, p = mcnemar(df, a, b)
                r[f"{a}->{b} (lost/gained, McNemar p)"] = f"{n01}/{n10}, p={p:.3g}"
            rows.append(r)
    tab = pd.DataFrame(rows)
    tab.to_csv(os.path.join(OUT, "tables", "conditions_by_group.csv"), index=False, encoding="utf-8-sig")
    pd.set_option("display.width", 250)
    print(tab.round(1).to_string(index=False))


if __name__ == "__main__":
    main()
