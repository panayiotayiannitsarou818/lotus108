
# -*- coding: utf-8 -*-
"""
step_7_final_score_FIXED.py

Διορθωμένο Step 7 — Υπολογισμός τελικού score & επιλογή σεναρίου
---------------------------------------------------------------
Καλύπτει τις παρατηρήσεις:
1) Φύλο: σωστό key για κορίτσια ('Κ', όχι 'Θ').
2) Γνώση ελληνικών: μετράει *ανά τμήμα* (max - min), όχι διαφορά συνόλων.
3) Σπασμένες φιλίες: πραγματικός υπολογισμός από DataFrame (αμοιβαίες δυάδες).
4) Ιεραρχία ισοπαλίας: total → πληθυσμός → φύλο → γνώση → τυχαία.
5) Robust normalizations (encoding/μορφές): Ν/Ο, ΚΑΛΗ/ΟΧΙ_ΚΑΛΗ κ.λπ.

Χρήση (ενδεικτικά):
-------------------
from step_7_final_score_FIXED import score_one_scenario, pick_best_scenario

scores = score_one_scenario(df, scenario_col='ΒΗΜΑ6_ΣΕΝΑΡΙΟ_1', num_classes=2)
best = pick_best_scenario(df, ['ΒΗΜΑ6_ΣΕΝΑΡΙΟ_1','ΒΗΜΑ6_ΣΕΝΑΡΙΟ_2','ΒΗΜΑ6_ΣΕΝΑΡΙΟ_3'])

Προαιρετικά μπορείς να περάσεις critical_pairs=[('Ονομα Α','Ονομα Β'),...] αν
θες να αξιολογήσεις μόνο συγκεκριμένες «κρίσιμες» αμοιβαίες φιλίες.
Αλλιώς, αν δεν δοθεί, ανιχνεύονται όλες οι *πλήρως αμοιβαίες δυάδες* από τη στήλη «ΦΙΛΟΙ».
"""
from __future__ import annotations
import random
from typing import Iterable, List, Tuple, Dict, Any, Optional
import pandas as pd
import numpy as np
import re

RANDOM_SEED = 42
random.seed(RANDOM_SEED)

# ------------------------ Normalizations ------------------------

YES_TOKENS = {"Ν", "ΝΑΙ", "Y", "YES", "TRUE", "1"}
NO_TOKENS  = {"Ο", "ΟΧΙ", "N", "NO", "FALSE", "0"}

def _norm_str(x) -> str:
    return str(x).strip().upper()

def _is_yes(x) -> bool:
    return _norm_str(x) in YES_TOKENS

def _is_no(x) -> bool:
    return _norm_str(x) in NO_TOKENS

def _parse_friends_cell(x) -> List[str]:
    """Δέχεται λίστα ή string. Επιστρέφει λίστα ονομάτων (stripped)."""
    if isinstance(x, list):
        return [str(t).strip() for t in x if str(t).strip()]
    s = str(x) if x is not None else ""
    s = s.strip()
    if not s or s.upper() == "NAN":
        return []
    # Προσπάθησε python-literal list
    try:
        val = eval(s, {}, {})
        if isinstance(val, list):
            return [str(t).strip() for t in val if str(t).strip()]
    except Exception:
        pass
    # Αλλιώς split σε κοινούς διαχωριστές
    parts = re.split(r"[,\|\;/·\n]+", s)
    return [p.strip() for p in parts if p.strip()]

def _infer_num_classes_from_values(vals: Iterable[str]) -> int:
    """Επιστρέφει #τμημάτων κοιτώντας labels τύπου Α1, Α2, ..."""
    labels = sorted({str(v) for v in vals if re.match(r"^Α\d+$", str(v))})
    if not labels:
        return 2
    return len(labels)

# ------------------------ Core scoring helpers ------------------------

def _counts_per_class(df: pd.DataFrame, scenario_col: str, label_filter=None) -> Dict[str, int]:
    """Γενικός μετρητής ανά τμήμα (π.χ. για φύλο). Αν label_filter=None, μετρά σύνολο πληθυσμού."""
    labels = sorted([c for c in df[scenario_col].dropna().astype(str).unique() if re.match(r"^Α\d+$", str(c))])
    res = {lab: 0 for lab in labels}
    if label_filter is None:
        for lab in labels:
            res[lab] = int((df[scenario_col] == lab).sum())
        return res
    # label_filter είναι συνάρτηση που δέχεται row και επιστρέφει bool
    mask = df.apply(label_filter, axis=1)
    for lab in labels:
        res[lab] = int(((df[scenario_col] == lab) & mask).sum())
    return res

def _boys_filter(row) -> bool:
    return _norm_str(row.get("ΦΥΛΟ")) == "Α"

def _girls_filter(row) -> bool:
    # Fix: 'Κ' για Κορίτσια (όχι 'Θ')
    return _norm_str(row.get("ΦΥΛΟ")) == "Κ"

def _good_greek_filter(row) -> bool:
    """True αν έχει 'καλή γνώση' σύμφωνα με ΟΠΟΙΑ στήλη υπάρχει."""
    if "ΚΑΛΗ_ΓΝΩΣΗ_ΕΛΛΗΝΙΚΩΝ" in row:
        # αναμένει 'Ν'/'Ο'
        val = row.get("ΚΑΛΗ_ΓΝΩΣΗ_ΕΛΛΗΝΙΚΩΝ")
        return _is_yes(val)
    if "ΓΝΩΣΗ_ΕΛΛΗΝΙΚΩΝ" in row:
        # αναμένει 'ΚΑΛΗ'/'ΟΧΙ_ΚΑΛΗ'
        v = _norm_str(row.get("ΓΝΩΣΗ_ΕΛΛΗΝΙΚΩΝ"))
        return v in {"ΚΑΛΗ", "Ν", "GOOD"}
    # fallback: not available → False
    return False

def _pair_conflict_penalty(aZ, aI, bZ, bI) -> int:
    if aI and bI: return 5
    if (aI and bZ) or (bI and aZ): return 4
    if aZ and bZ: return 3
    return 0

def _class_conflict_sum(class_df: pd.DataFrame) -> int:
    s = 0
    rows = class_df[['ΖΩΗΡΟΣ','ΙΔΙΑΙΤΕΡΟΤΗΤΑ']].fillna("").to_dict('records')
    for i in range(len(rows)):
        for j in range(i+1, len(rows)):
            a = rows[i]; b = rows[j]
            aZ = _is_yes(a.get('ΖΩΗΡΟΣ')); aI = _is_yes(a.get('ΙΔΙΑΙΤΕΡΟΤΗΤΑ'))
            bZ = _is_yes(b.get('ΖΩΗΡΟΣ')); bI = _is_yes(b.get('ΙΔΙΑΙΤΕΡΟΤΗΤΑ'))
            s += _pair_conflict_penalty(aZ, aI, bZ, bI)
    return s

def _all_conflicts_sum(df: pd.DataFrame, scenario_col: str) -> int:
    s = 0
    for lab, class_df in df.groupby(scenario_col):
        if not re.match(r"^Α\d+$", str(lab)):  # ignore non-class values
            continue
        s += _class_conflict_sum(class_df)
    return s

def _mutual_pairs(df: pd.DataFrame) -> List[Tuple[str,str]]:
    """Βρίσκει όλες τις *πλήρως αμοιβαίες* δυάδες από «ΦΙΛΟΙ»."""
    if "ΦΙΛΟΙ" not in df.columns:
        return []
    name2friends = {}
    for _, r in df.iterrows():
        name = str(r.get("ΟΝΟΜΑ")).strip()
        friends = set(_parse_friends_cell(r.get("ΦΙΛΟΙ")))
        name2friends[name] = friends
    pairs = set()
    names = sorted(name2friends.keys())
    for i, a in enumerate(names):
        for b in names[i+1:]:
            if a in name2friends.get(b, set()) and b in name2friends.get(a, set()):
                pairs.add(tuple(sorted((a,b))))
    return sorted(pairs)

def _broken_friendships_count(df: pd.DataFrame, scenario_col: str, critical_pairs: Optional[List[Tuple[str,str]]] = None,
                              count_unassigned_as_broken: bool=False) -> int:
    """Μετρά πόσες αμοιβαίες δυάδες ΔΕΝ κατέληξαν στο ίδιο τμήμα.
       Αν critical_pairs=None → αντλεί όλες τις πλήρως αμοιβαίες από «ΦΙΛΟΙ».
       Αν count_unassigned_as_broken=True, το NaN για κάποιον μετρά ως break.
    """
    if critical_pairs is None:
        pairs = _mutual_pairs(df)
    else:
        # κανονικοποίηση γραφής ονομάτων
        pairs = [tuple(sorted((str(a).strip(), str(b).strip()))) for a,b in critical_pairs]
    name2class = {str(r["ΟΝΟΜΑ"]).strip(): r.get(scenario_col) for _, r in df.iterrows()}
    broken = 0
    for a,b in pairs:
        ca = name2class.get(a, np.nan)
        cb = name2class.get(b, np.nan)
        if pd.isna(ca) or pd.isna(cb):
            if count_unassigned_as_broken:
                broken += 1
            continue
        if str(ca) != str(cb):
            broken += 1
    return broken

# ------------------------ Public API ------------------------

def score_one_scenario(df: pd.DataFrame, scenario_col: str, num_classes: Optional[int]=None,
                       critical_pairs: Optional[List[Tuple[str,str]]]=None,
                       count_unassigned_as_broken: bool=False) -> Dict[str, Any]:
    """Υπολογίζει το αναλυτικό score για ένα σενάριο."""
    df = df.copy()
    if num_classes is None:
        num_classes = _infer_num_classes_from_values(df[scenario_col].values)

    # Πληθυσμός ανά τμήμα
    pop_counts = _counts_per_class(df, scenario_col)
    pops = list(pop_counts.values())
    pop_diff = (max(pops) - min(pops)) if pops else 0
    population_penalty = max(0, pop_diff - 1) * 3

    # Φύλο ανά τμήμα
    boys_counts = _counts_per_class(df, scenario_col, label_filter=_boys_filter)
    girls_counts= _counts_per_class(df, scenario_col, label_filter=_girls_filter)
    boys = list(boys_counts.values()); girls = list(girls_counts.values())
    boys_diff = (max(boys) - min(boys)) if boys else 0
    girls_diff = (max(girls) - min(girls)) if girls else 0
    gender_penalty = max(0, boys_diff - 1) * 2 + max(0, girls_diff - 1) * 2

    # Καλή γνώση ανά τμήμα
    good_counts = _counts_per_class(df, scenario_col, label_filter=_good_greek_filter)
    good = list(good_counts.values())
    greek_diff = (max(good) - min(good)) if good else 0
    greek_penalty = max(0, greek_diff - 2) * 1

    # Παιδαγωγικές συγκρούσεις (σύνολο) — (3/4/5)
    conflict_penalty = _all_conflicts_sum(df, scenario_col)

    # Σπασμένες αμοιβαίες φιλίες
    broken = _broken_friendships_count(df, scenario_col, critical_pairs, count_unassigned_as_broken)
    broken_friendships_penalty = 5 * broken

    total = population_penalty + gender_penalty + greek_penalty + conflict_penalty + broken_friendships_penalty

    return {
        "scenario_col": scenario_col,
        "num_classes": num_classes,
        "population_counts": pop_counts,
        "boys_counts": boys_counts,
        "girls_counts": girls_counts,
        "good_greek_counts": good_counts,
        "diff_population": int(pop_diff),
        "diff_gender": int(max(boys_diff, girls_diff)),  # για tie-break παίρνουμε τη χειρότερη από τις δύο
        "diff_greek": int(greek_diff),
        "population_penalty": int(population_penalty),
        "gender_penalty": int(gender_penalty),
        "greek_penalty": int(greek_penalty),
        "conflict_penalty": int(conflict_penalty),
        "broken_friendships": int(broken),
        "broken_friendships_penalty": int(broken_friendships_penalty),
        "total_score": int(total),
    }

def pick_best_scenario(df: pd.DataFrame, scenario_cols: List[str], num_classes: Optional[int]=None,
                       critical_pairs: Optional[List[Tuple[str,str]]]=None,
                       count_unassigned_as_broken: bool=False,
                       k_best: int=1, random_seed: int=42) -> Dict[str, Any]:
    """Βαθμολογεί και επιλέγει βέλτιστο σενάριο με ιεραρχία:
       1) χαμηλότερο total_score
       2) μικρότερη diff_population
       3) μικρότερη diff_gender
       4) μικρότερη diff_greek
       5) τυχαία επιλογή μεταξύ ισάξιων
    """
    if num_classes is None and scenario_cols:
        num_classes = _infer_num_classes_from_values(df[scenario_cols[0]].values)

    scores = [score_one_scenario(df, c, num_classes, critical_pairs, count_unassigned_as_broken)
              for c in scenario_cols if c in df.columns]

    if not scores:
        return {"best": None, "scores": []}

    # Ταξινόμηση με βάση την ιεραρχία
    scores_sorted = sorted(
        scores,
        key=lambda s: (s["total_score"], s["diff_population"], s["diff_gender"], s["diff_greek"])
    )

    # Ομάδα κορυφής (ίδιες 4 τιμές) → τυχαία επιλογή μέσα στην ομάδα
    top = [scores_sorted[0]]
    for s in scores_sorted[1:]:
        if (s["total_score"] == top[0]["total_score"] and
            s["diff_population"] == top[0]["diff_population"] and
            s["diff_gender"] == top[0]["diff_gender"] and
            s["diff_greek"] == top[0]["diff_greek"]):
            top.append(s)
        else:
            break

    random.seed(random_seed)
    best = random.choice(top)

    return {"best": best, "scores": scores_sorted[:max(k_best,1)]}

# ------------------------ Convenience: score many & to Excel ------------------------

def score_to_dataframe(df: pd.DataFrame, scenario_cols: List[str], **kwargs) -> pd.DataFrame:
    rows = []
    for c in scenario_cols:
        if c not in df.columns:
            continue
        s = score_one_scenario(df, c, **kwargs)
        rows.append({
            "SCENARIO": c,
            "TOTAL": s["total_score"],
            "POP_DIFF": s["diff_population"],
            "GENDER_DIFF": s["diff_gender"],
            "GREEK_DIFF": s["diff_greek"],
            "POP_PEN": s["population_penalty"],
            "GENDER_PEN": s["gender_penalty"],
            "GREEK_PEN": s["greek_penalty"],
            "CONFLICT_PEN": s["conflict_penalty"],
            "BROKEN_COUNT": s["broken_friendships"],
            "BROKEN_PEN": s["broken_friendships_penalty"],
        })
    return pd.DataFrame(rows)

def export_scores_excel(df: pd.DataFrame, scenario_cols: List[str], out_path: str, **kwargs) -> str:
    tbl = score_to_dataframe(df, scenario_cols, **kwargs)
    with pd.ExcelWriter(out_path, engine="openpyxl") as w:
        tbl.to_excel(w, index=False, sheet_name="Scores")
    return out_path


# === Patched helpers for auto scenario detection & normalization ===

def _find_scenario_col_auto(df: pd.DataFrame) -> str | None:
    # Prefer ΒΗΜΑ6_ΣΕΝΑΡΙΟ_N__1, else ΒΗΜΑ6_ΤΜΗΜΑ, else ΤΜΗΜΑ_ΜΕΤΑ_ΒΗΜΑ6, else ΤΜΗΜΑ
    import re
    for c in df.columns:
        if re.match(r"^ΒΗΜΑ6_ΣΕΝΑΡΙΟ_\d+__1$", str(c)):
            return c
    for c in ("ΒΗΜΑ6_ΤΜΗΜΑ", "ΤΜΗΜΑ_ΜΕΤΑ_ΒΗΜΑ6", "ΤΜΗΜΑ"):
        if c in df.columns:
            return c
    return None

def _normalize_class_labels(df: pd.DataFrame, col: str):
    # Convert Latin 'A1' to Greek 'Α1'
    import re
    greek_A = "Α"
    df[col] = df[col].apply(lambda s: (greek_A + str(s)[1:]) if re.match(r"^A\d+$", str(s).strip()) else str(s).strip())

def _ensure_optional_cols(df: pd.DataFrame):
    # Ensure optional columns with safe defaults
    defaults = {
        "ΖΩΗΡΟΣ": "Ο",
        "ΙΔΙΑΙΤΕΡΟΤΗΤΑ": "Ο",
        "ΣΥΓΚΡΟΥΣΗ": "",
        "ΦΙΛΟΙ": "",
    }
    for k,v in defaults.items():
        if k not in df.columns:
            df[k] = v

def score_one_scenario_auto(df: pd.DataFrame, scenario_col: str | None = None, **kwargs):
    df = df.copy()
    if scenario_col is None:
        scenario_col = _find_scenario_col_auto(df)
    if scenario_col is None:
        raise ValueError("Δεν βρέθηκε κατάλληλη στήλη τμήματος για το Βήμα 7.")
    _normalize_class_labels(df, scenario_col)
    _ensure_optional_cols(df)
    return score_one_scenario(df, scenario_col, **kwargs)
