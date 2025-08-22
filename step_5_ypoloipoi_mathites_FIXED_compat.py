
# -*- coding: utf-8 -*-
"""
step_5_ypoloipoi_mathites_FIXED_compat.py

Forward/Backward compatible Βήμα 5, συμβατό με:
- "ΓΝΩΣΗ_ΕΛΛΗΝΙΚΩΝ" = {"ΚΑΛΗ","ΟΧΙ_ΚΑΛΗ"} (παλιό)
- "ΚΑΛΗ_ΓΝΩΣΗ_ΕΛΛΗΝΙΚΩΝ" = {"Ν","Ο"}       (νέο)
- "ΠΛΗΡΩΣ_ΑΜΟΙΒΑΙΑ"/"ΣΠΑΣΜΕΝΗ_ΦΙΛΙΑ"   → αναγνωρίζονται Ν/Ο, ΝΑΙ/ΟΧΙ, YES/NO, 1/0
- "ΦΙΛΟΙ" ως λίστα ή string (με διάφορους διαχωριστές)

Tip: Αν έχεις ήδη ενσωματώσει το utils/schema.normalize_dataset & ensure_step5_6_columns,
το παρόν module θα λειτουργεί «out of the box».
"""

from __future__ import annotations
import random, re
from typing import List, Dict, Tuple, Any, Optional
import pandas as pd

RANDOM_SEED = 42
random.seed(RANDOM_SEED)

YES_TOKENS = {"Ν", "ΝΑΙ", "YES", "Y", "TRUE", "1"}
NO_TOKENS  = {"Ο", "ΟΧΙ", "NO", "N", "FALSE", "0"}

def _norm_str(x) -> str:
    return str(x).strip().upper()

def _is_yes(x) -> bool:
    return _norm_str(x) in YES_TOKENS

def _is_no(x) -> bool:
    return _norm_str(x) in NO_TOKENS

def _parse_list_cell(x) -> List[str]:
    if isinstance(x, list):
        return [str(t).strip() for t in x if str(t).strip()]
    s = "" if pd.isna(x) else str(x)
    s = s.strip()
    if not s or s.upper()=="NAN":
        return []
    # προσπαθησε python list
    try:
        v = eval(s, {}, {})
        if isinstance(v, list):
            return [str(t).strip() for t in v if str(t).strip()] 
    except Exception:
        pass
    parts = re.split(r"[,\|\;/·\n]+", s)
    return [p.strip() for p in parts if p.strip()]

def _is_good_greek(row: pd.Series) -> bool:
    if "ΚΑΛΗ_ΓΝΩΣΗ_ΕΛΛΗΝΙΚΩΝ" in row:
        return _is_yes(row.get("ΚΑΛΗ_ΓΝΩΣΗ_ΕΛΛΗΝΙΚΩΝ"))
    if "ΓΝΩΣΗ_ΕΛΛΗΝΙΚΩΝ" in row:
        return _norm_str(row.get("ΓΝΩΣΗ_ΕΛΛΗΝΙΚΩΝ")) in {"ΚΑΛΗ", "GOOD", "Ν"}
    return False

def _labels(df: pd.DataFrame, senario_col: str) -> List[str]:
    labs = sorted([str(v) for v in df[senario_col].dropna().unique() if re.match(r"^Α\d+$", str(v))])
    return labs or [f"Α{i+1}" for i in range(2)]

def calculate_penalty_score(df: pd.DataFrame, senario_col: str, num_classes: Optional[int]=None) -> int:
    labs = _labels(df, senario_col)
    if num_classes is None:
        num_classes = len(labs)

    # --- Ισορροπία Γνώσης Ελληνικών (ανά τμήμα) ---
    greek_counts = []
    for lab in labs:
        sub = df[df[senario_col] == lab].copy()
        greek_counts.append(int(sub.apply(_is_good_greek, axis=1).sum()))
    greek_diff = max(greek_counts) - min(greek_counts) if greek_counts else 0
    penalty = max(0, greek_diff - 2) * 1

    # --- Ισορροπία Πληθυσμού ---
    class_sizes = [int((df[senario_col] == lab).sum()) for lab in labs]
    pop_diff = max(class_sizes) - min(class_sizes) if class_sizes else 0
    penalty += max(0, pop_diff - 1) * 3  # βάρη σύμφωνα με Step 6/7

    # --- Ισορροπία Φύλου (αγόρια/κορίτσια) ---
    boys_counts  = [int(((df[senario_col] == lab) & (df["ΦΥΛΟ"].astype(str).str.upper()=="Α")).sum()) for lab in labs]
    girls_counts = [int(((df[senario_col] == lab) & (df["ΦΥΛΟ"].astype(str).str.upper()=="Κ")).sum()) for lab in labs]
    boys_diff = max(boys_counts) - min(boys_counts) if boys_counts else 0
    girls_diff = max(girls_counts) - min(girls_counts) if girls_counts else 0
    penalty += max(0, boys_diff - 1) * 2 + max(0, girls_diff - 1) * 2

    # --- Σπασμένες Πλήρως Αμοιβαίες Φιλίες ---
    if "ΣΠΑΣΜΕΝΗ_ΦΙΛΙΑ" in df.columns:
        br = int(df["ΣΠΑΣΜΕΝΗ_ΦΙΛΙΑ"].apply(_is_yes).sum())
        penalty += 5 * br

    return int(penalty)

def step5_filikoi_omades(df: pd.DataFrame, senario_col: str, num_classes: Optional[int]=None):
    """
    Τοποθετεί διαδοχικά τους μη τοποθετημένους μαθητές που ΔΕΝ έχουν πλήρως αμοιβαίες φιλίες,
    με προτεραιότητα: (1) μικρότερος πληθυσμός, (2) ισορροπία φύλου.
    """
    df = df.copy()
    labs = _labels(df, senario_col)
    if num_classes is None:
        num_classes = len(labs)

    classes = {lab: df[df[senario_col] == lab]["ΟΝΟΜΑ"].astype(str).tolist() for lab in labs}

    # --- Mask Step 5: δεν έχουν τοποθέτηση ΚΑΙ (χωρίς φίλους ή όχι-αμοιβαίοι ή σπασμένη φιλία) ---
    friends_list = df["ΦΙΛΟΙ"].map(_parse_list_cell) if "ΦΙΛΟΙ" in df.columns else pd.Series([[]]*len(df))
    fully_mut = df["ΠΛΗΡΩΣ_ΑΜΟΙΒΑΙΑ"].apply(_is_yes) if "ΠΛΗΡΩΣ_ΑΜΟΙΒΑΙΑ" in df.columns else pd.Series([False]*len(df))
    broken    = df["ΣΠΑΣΜΕΝΗ_ΦΙΛΙΑ"].apply(_is_yes) if "ΣΠΑΣΜΕΝΗ_ΦΙΛΙΑ" in df.columns else pd.Series([False]*len(df))

    mask_step5 = (
        df[senario_col].isna()
        & ((friends_list.map(len) == 0) | (~fully_mut) | (broken))
    )

    remaining = df[mask_step5].copy()

    for _, row in remaining.iterrows():
        name = str(row["ΟΝΟΜΑ"]).strip()
        gender = str(row["ΦΥΛΟ"]).strip().upper()

        # (1) διάλεξε υποψήφια τμήματα με ελάχιστο πληθυσμό & <25
        population = {lab: len(classes[lab]) for lab in labs}
        min_pop = min(population.values())
        candidates = [lab for lab, cnt in population.items() if cnt == min_pop and cnt < 25]
        if not candidates:
            continue

        if len(candidates) == 1:
            chosen = candidates[0]
        else:
            # (2) ισορροπία φύλου — προσομοίωσε την προσθήκη
            boys = {lab: int(((df[senario_col] == lab) & (df["ΦΥΛΟ"].astype(str).str.upper()=="Α")).sum()) for lab in candidates}
            girls= {lab: int(((df[senario_col] == lab) & (df["ΦΥΛΟ"].astype(str).str.upper()=="Κ")).sum()) for lab in candidates}

            scores = {}
            for lab in candidates:
                pb = boys[lab] + (1 if gender=="Α" else 0)
                pg = girls[lab]+ (1 if gender=="Κ" else 0)
                # diff μέσα στους candidates
                boys_vals  = [pb if x==lab else boys[x]  for x in candidates]
                girls_vals = [pg if x==lab else girls[x] for x in candidates]
                scores[lab] = (max(boys_vals)-min(boys_vals)) + (max(girls_vals)-min(girls_vals))

            best = min(scores.values())
            pool = [lab for lab, sc in scores.items() if sc == best]
            chosen = random.choice(pool)

        df.loc[df["ΟΝΟΜΑ"] == name, senario_col] = chosen
        classes[chosen].append(name)

    return df, calculate_penalty_score(df, senario_col, num_classes)

def apply_step5_to_all_scenarios(scenarios_dict: Dict[str, pd.DataFrame], senario_col: str, num_classes: Optional[int]=None):
    results = {}
    for scenario_name, scenario_df in scenarios_dict.items():
        updated_df, score = step5_filikoi_omades(scenario_df, senario_col, num_classes)
        results[scenario_name] = {"df": updated_df, "penalty_score": score}

    min_score = min(v["penalty_score"] for v in results.values()) if results else 0
    best = [k for k, v in results.items() if v["penalty_score"] == min_score]
    pick = random.choice(best) if best else None
    return results[pick]["df"] if pick else None
