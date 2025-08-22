# -*- coding: utf-8 -*-
"""
Step 2 — Ζωηροί & Ιδιαιτερότητες (Fixed v3, **patched**)
- Η στήλη εξόδου του Βήματος 2 ΜΕΤΟΝΟΜΑΖΕΤΑΙ σε «ΒΗΜΑ2_ΣΕΝΑΡΙΟ_{k}»
  όπου k είναι ο αριθμός από το step1_col_name (π.χ. ΒΗΜΑ1_ΣΕΝΑΡΙΟ_2 -> k=2).
- Όλα τα υπόλοιπα παραμένουν συμβατά.
"""
from typing import List, Dict, Tuple, Any, Set
import pandas as pd
import random
import re

from step_2_helpers_FIXED import (
    normalize_columns, parse_friends_cell, scope_step2, mutual_pairs_in_scope
)

RANDOM_SEED = 42
random.seed(RANDOM_SEED)


def _pair_conflict_penalty(aZ, aI, bZ, bI) -> int:
    if aI and bI:
        return 5
    if (aI and bZ) or (bI and aZ):
        return 4
    if aZ and bZ:
        return 3
    return 0


def _count_ped_conflicts(df: pd.DataFrame, col: str) -> int:
    cnt = 0
    by_class = {}
    for _, r in df.iterrows():
        cl = r.get(col)
        if pd.isna(cl):
            continue
        by_class.setdefault(str(cl), []).append(r)
    for _cl, rows in by_class.items():
        for i in range(len(rows)):
            for j in range(i + 1, len(rows)):
                aZ = str(rows[i].get("ΖΩΗΡΟΣ", "")).strip() == "Ν"
                aI = str(rows[i].get("ΙΔΙΑΙΤΕΡΟΤΗΤΑ", "")).strip() == "Ν"
                bZ = str(rows[j].get("ΖΩΗΡΟΣ", "")).strip() == "Ν"
                bI = str(rows[j].get("ΙΔΙΑΙΤΕΡΟΤΗΤΑ", "")).strip() == "Ν"
                if _pair_conflict_penalty(aZ, aI, bZ, bI) > 0:
                    cnt += 1
    return cnt


def _sum_conflicts(df: pd.DataFrame, col: str) -> int:
    s = 0
    by_class = {}
    for _, r in df.iterrows():
        cl = r.get(col)
        if pd.isna(cl):
            continue
        by_class.setdefault(str(cl), []).append(r)
    for _cl, rows in by_class.items():
        for i in range(len(rows)):
            for j in range(i + 1, len(rows)):
                aZ = str(rows[i].get("ΖΩΗΡΟΣ", "")).strip() == "Ν"
                aI = str(rows[i].get("ΙΔΙΑΙΤΕΡΟΤΗΤΑ", "")).strip() == "Ν"
                bZ = str(rows[j].get("ΖΩΗΡΟΣ", "")).strip() == "Ν"
                bI = str(rows[j].get("ΙΔΙΑΙΤΕΡΟΤΗΤΑ", "")).strip() == "Ν"
                s += _pair_conflict_penalty(aZ, aI, bZ, bI)
    return s


def _broken_mutual_pairs(df: pd.DataFrame, col: str, scope: Set[str]) -> int:
    pairs = mutual_pairs_in_scope(df, scope)
    name2class = {
        str(r["ΟΝΟΜΑ"]).strip(): str(r.get(col))
        for _, r in df.iterrows()
        if pd.notna(r.get(col))
    }
    return sum(1 for a, b in pairs if name2class.get(a) != name2class.get(b))


def _compute_targets_global(
    df: pd.DataFrame, step1_col: str, class_labels: List[str]
) -> Dict[str, Dict[str, int]]:
    """
    Υπολογίζει ΤΕΛΙΚΟΥΣ στόχους για σύνολο Ζ/Ι μετά το Βήμα 2 (δηλ. step1 + to_place).
    - final_totals = Z_step1_total + Z_to_place_total (και αντίστοιχα για Ι).
    - Τελικός στόχος ανά τμήμα: q ή q+1 όπου q,r = divmod(final_total, num_classes).
    """
    Z_step1 = {cl: 0 for cl in class_labels}
    I_step1 = {cl: 0 for cl in class_labels}
    Z_total_step1 = 0
    I_total_step1 = 0
    for _, r in df.iterrows():
        cl = r.get(step1_col)
        z = str(r.get("ΖΩΗΡΟΣ", "")).strip() == "Ν"
        i = str(r.get("ΙΔΙΑΙΤΕΡΟΤΗΤΑ", "")).strip() == "Ν"
        if not pd.isna(cl):
            if z:
                Z_step1[str(cl)] += 1
                Z_total_step1 += 1
            if i:
                I_step1[str(cl)] += 1
                I_total_step1 += 1

    to_place = df[pd.isna(df[step1_col])]
    Z_to_place = int((to_place["ΖΩΗΡΟΣ"].astype(str).str.strip() == "Ν").sum())
    I_to_place = int((to_place["ΙΔΙΑΙΤΕΡΟΤΗΤΑ"].astype(str).str.strip() == "Ν").sum())

    Z_final_total = Z_total_step1 + Z_to_place
    I_final_total = I_total_step1 + I_to_place

    def _qmax(total):
        q, r = divmod(total, len(class_labels))
        return {"q": q, "max": q + (1 if r > 0 else 0)}

    return {
        "Z": _qmax(Z_final_total),
        "I": _qmax(I_final_total),
        "Z_step1": Z_step1,
        "I_step1": I_step1,
    }


def _prereject(assign_map, next_name, next_cl, df, step1_col, class_labels, targets) -> bool:
    """Γρήγορο pruning πριν από απόπειρα ανάθεσης."""
    Zc = targets["Z_step1"].copy()
    Ic = targets["I_step1"].copy()
    tmp = assign_map.copy()
    if next_name and next_cl:
        tmp[next_name] = next_cl

    # Προσωρινή καταμέτρηση Ζ/Ι αν μπει το next
    for n, cl in tmp.items():
        row = df[df["ΟΝΟΜΑ"] == n].iloc[0]
        if str(row.get("ΖΩΗΡΟΣ", "")).strip() == "Ν":
            Zc[cl] += 1
        if str(row.get("ΙΔΙΑΙΤΕΡΟΤΗΤΑ", "")).strip() == "Ν":
            Ic[cl] += 1

    # Upper bounds per targets
    for cl in class_labels:
        if Zc[cl] > targets["Z"]["max"]:
            return False
        if Ic[cl] > targets["I"]["max"]:
            return False

    # Γρήγορος έλεγχος συγκρούσεων με fixed/partial της ίδιας τάξης
    if next_name and next_cl and "ΣΥΓΚΡΟΥΣΗ" in df.columns:
        mask_next = (df["ΟΝΟΜΑ"] == next_name)
        next_conf_cell = df.loc[mask_next, "ΣΥΓΚΡΟΥΣΗ"]
        toks_next = set(parse_friends_cell(next_conf_cell.values[0] if not next_conf_cell.empty else ""))

        fixed_same = df[(pd.notna(df[step1_col])) & (df[step1_col] == next_cl)]
        if any((n in toks_next) for n in fixed_same["ΟΝΟΜΑ"].astype(str).tolist()):
            return False

        for n2, cl2 in tmp.items():
            if cl2 != next_cl:
                continue
            mask_n2 = (df["ΟΝΟΜΑ"] == n2)
            n2_conf_cell = df.loc[mask_n2, "ΣΥΓΚΡΟΥΣΗ"]
            toks2 = set(parse_friends_cell(n2_conf_cell.values[0] if not n2_conf_cell.empty else ""))
            if (next_name in toks2) or (n2 in toks_next):
                return False
    return True


def _extract_step1_id(step1_col_name: str) -> int:
    """
    Επιστρέφει τον αριθμό k από «ΒΗΜΑ1_ΣΕΝΑΡΙΟ_k» ή «V1_ΣΕΝΑΡΙΟ_k».
    Αν δεν βρεθεί, επιστρέφει 1.
    """
    m = re.search(r'(?:ΒΗΜΑ1_|V1_)ΣΕΝΑΡΙΟ[_\s]*(\d+)', str(step1_col_name))
    if not m:
        return 1
    return int(m.group(1))


def step2_apply_FIXED_v3(
    df_in: pd.DataFrame,
    num_classes: int,
    step1_col_name: str,
    *,
    seed: int = 42,
    max_results: int = 5,
) -> List[Tuple[str, pd.DataFrame, Dict[str, Any]]]:
    """
    Επιστρέφει έως max_results σενάρια ως (label, DataFrame, metrics).
    Το DataFrame περιέχει στήλες εισόδου + «ΒΗΜΑ2_ΣΕΝΑΡΙΟ_{k}» όπου k = id του ΒΗΜΑ1_ΣΕΝΑΡΙΟ_k.
    """
    random.seed(seed)
    df = normalize_columns(df_in).copy()
    class_labels = [f"Α{i+1}" for i in range(num_classes)]
    scope = scope_step2(df, step1_col=step1_col_name)

    # Μόνο Ζ/Ι προς τοποθέτηση
    to_place = df[(pd.isna(df[step1_col_name])) & ((df["ΖΩΗΡΟΣ"] == "Ν") | (df["ΙΔΙΑΙΤΕΡΟΤΗΤΑ"] == "Ν"))]["ΟΝΟΜΑ"].astype(str).tolist()
    targets = _compute_targets_global(df, step1_col=step1_col_name, class_labels=class_labels)

    best: List[Tuple[pd.DataFrame, int, int, int, int]] = []
    assign: Dict[str, str] = {}

    # Σειρά δυσκολίας
    def deg(name: str) -> int:
        row = df[df["ΟΝΟΜΑ"] == name].iloc[0]
        return len(parse_friends_cell(row.get("ΣΥΓΚΡΟΥΣΗ", ""))) + len(parse_friends_cell(row.get("ΦΙΛΟΙ", "")))

    to_place_sorted = sorted(
        to_place,
        key=lambda n: (
            -(
                str(df.loc[df["ΟΝΟΜΑ"] == n, "ΖΩΗΡΟΣ"].values[0]).strip() == "Ν"
                and str(df.loc[df["ΟΝΟΜΑ"] == n, "ΙΔΙΑΙΤΕΡΟΤΗΤΑ"].values[0]).strip() == "Ν"
            ),
            -(str(df.loc[df["ΟΝΟΜΑ"] == n, "ΙΔΙΑΙΤΕΡΟΤΗΤΑ"].values[0]).strip() == "Ν"),
            -(str(df.loc[df["ΟΝΟΜΑ"] == n, "ΖΩΗΡΟΣ"].values[0]).strip() == "Ν"),
            -deg(n),
        ),
    )

    def backtrack(i: int) -> None:
        if i == len(to_place_sorted):
            cand = df.copy()
            cand_col = "ΒΗΜΑ2_TMP"
            cand[cand_col] = cand[step1_col_name]
            for n, cl in assign.items():
                cand.loc[cand["ΟΝΟΜΑ"] == n, cand_col] = cl

            # reject "όλοι στην ίδια τάξη"
            counts_new = {cl: 0 for cl in class_labels}
            for cl in assign.values():
                counts_new[cl] += 1
            if sum(counts_new.values()) > 0 and max(counts_new.values()) == sum(counts_new.values()):
                return

            # έλεγχος στόχων Ζ/Ι
            Zc = targets["Z_step1"].copy()
            Ic = targets["I_step1"].copy()
            for n, cl in assign.items():
                row = df[df["ΟΝΟΜΑ"] == n].iloc[0]
                if str(row.get("ΖΩΗΡΟΣ", "")).strip() == "Ν":
                    Zc[cl] += 1
                if str(row.get("ΙΔΙΑΙΤΕΡΟΤΗΤΑ", "")).strip() == "Ν":
                    Ic[cl] += 1
            for cl in class_labels:
                if not (targets["Z"]["q"] <= Zc[cl] <= targets["Z"]["max"]):
                    return
                if not (targets["I"]["q"] <= Ic[cl] <= targets["I"]["max"]):
                    return

            ped_cnt = _count_ped_conflicts(cand, cand_col)
            conf_sum = _sum_conflicts(cand, cand_col)
            broken = _broken_mutual_pairs(cand, cand_col, scope)
            total = conf_sum + 5 * broken
            best.append((cand, ped_cnt, broken, total, conf_sum))
            return

        name = to_place_sorted[i]
        for cl in class_labels:
            if not _prereject(assign, name, cl, df, step1_col_name, class_labels, targets):
                continue
            assign[name] = cl
            backtrack(i + 1)
            del assign[name]

    backtrack(0)

    # Αν δεν βρέθηκε τίποτα, «pass-through»
    if not best:
        tmp = df.copy()
        # Στήλη Β2: να πάρει id από το step1_col_name
        base_id = _extract_step1_id(step1_col_name)
        tmp[f"ΒΗΜΑ2_ΣΕΝΑΡΙΟ_{base_id}"] = tmp[step1_col_name]
        return [("option_1", tmp, {"ped_conflicts": None, "broken": None, "penalty": None})]

    # --- Επιλογή σεναρίων ---
    zero_ped = [x for x in best if x[1] == 0]
    selected = []

    # Για ρητή ορολογία «διατηρημένες φιλίες», υπολογίζουμε το σταθερό πλήθος συνολικών αμοιβαίων
    total_pairs = len(mutual_pairs_in_scope(df, scope))

    if zero_ped:
        # 1) λιγότερα broken
        min_broken = min(x[2] for x in zero_ped)
        tier1 = [x for x in zero_ped if x[2] == min_broken]
        # 2) χαμηλότερο συνολικό penalty
        min_total = min(x[3] for x in tier1)
        tier2 = [x for x in tier1 if x[3] == min_total]
        # 3) τυχαία αν > max_results
        if len(tier2) > max_results:
            random.shuffle(tier2)
            tier2 = tier2[:max_results]
        selected = tier2
    else:
        # ΌΛΑ έχουν παιδαγωγικές συγκρούσεις (Υποχρεωτική Τοποθέτηση)
        # 1) μικρότερο συνολικό penalty
        min_total = min(x[3] for x in best)
        tier1 = [x for x in best if x[3] == min_total]
        # 2) ΠΕΡΙΣΣΟΤΕΡΕΣ διατηρημένες φιλίες  ==  (total_pairs - broken) μέγιστο
        max_preserved = max(total_pairs - x[2] for x in tier1)
        tier2 = [x for x in tier1 if (total_pairs - x[2]) == max_preserved]
        # 3) τυχαία αν > max_results
        if len(tier2) > max_results:
            random.shuffle(tier2)
            tier2 = tier2[:max_results]
        selected = tier2

    # --- Κατασκευή αποτελεσμάτων ---
    results: List[Tuple[str, pd.DataFrame, Dict[str, Any]]] = []
    base_id = _extract_step1_id(step1_col_name)
    for k, (cand, ped_cnt, broken, total, conf_sum) in enumerate(selected, start=1):
        out = cand.copy()
        # ΠΑΝΤΑ οριστικοποιούμε τη στήλη ως «ΒΗΜΑ2_ΣΕΝΑΡΙΟ_{base_id}»
        final_col = f"ΒΗΜΑ2_ΣΕΝΑΡΙΟ_{base_id}"
        out[final_col] = out["ΒΗΜΑ2_TMP"]
        out.drop(columns=["ΒΗΜΑ2_TMP"], inplace=True)
        results.append(
            (
                f"option_{k}",
                out,
                {"ped_conflicts": int(ped_cnt), "broken": int(broken), "penalty": int(total)},
            )
        )
    return results
