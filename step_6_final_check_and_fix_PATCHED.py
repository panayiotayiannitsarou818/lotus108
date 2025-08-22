
# filename: step_6_final_check_and_fix_multi.py
from __future__ import annotations
"""
Patched: dynamic id_col + explicit Step 6 outputs.
"""
_IDCOL = "ID"
import itertools
from typing import Dict, List, Tuple, Optional
import pandas as pd
import numpy as np

# --------------------------
# Constants / Config
# --------------------------
BOY = "Α"           # Αγόρι
GIRL = "Κ"          # Κορίτσι
GOOD = "Ν"          # Καλή Γνώση Ελληνικών
NOTGOOD = "Ο"       # Όχι Καλή

MAX_PER_CLASS = 25
TARGET_POP_DIFF = 2
TARGET_GENDER_DIFF = 3
TARGET_LANG_DIFF = 3  # Στόχος: διαφορά γλώσσας ≤3

MAX_ITER = 5

# Αποδεκτές τιμές για στήλη ΒΗΜΑ_ΤΟΠΟΘΕΤΗΣΗΣ
STEP4_MARKERS = {4, "4", "Βήμα 4", "Step4", "Step4_Group", "Β4", "Β4_Δυάδα"}
STEP5_MARKERS = {5, "5", "Βήμα 5", "Step5", "Step5_Solo", "Β5", "Β5_Μεμονωμένος"}

# --------------------------
# Helpers
# --------------------------
def _classes(df: pd.DataFrame, class_col: str) -> List:
    cls = list(df[class_col].dropna().unique())
    if len(cls) < 2:
        raise ValueError("Απαιτούνται τουλάχιστον 2 τμήματα.")
    return list(cls)

def _metrics(df: pd.DataFrame, class_col: str, gender_col: str, lang_col: str) -> Dict:
    per = {}
    for c, sub in df.groupby(class_col):
        per[c] = dict(
            total=len(sub),
            boys=(sub[gender_col] == BOY).sum(),
            girls=(sub[gender_col] == GIRL).sum(),
            good=(sub[lang_col] == GOOD).sum(),
        )
    totals = [v["total"] for v in per.values()]
    boys   = [v["boys"]  for v in per.values()]
    girls  = [v["girls"] for v in per.values()]
    good   = [v["good"]  for v in per.values()]
    deltas = dict(
        pop   = (max(totals) - min(totals)) if totals else 0,
        boys  = (max(boys)   - min(boys))   if boys   else 0,
        girls = (max(girls)  - min(girls))  if girls  else 0,
        gender= max((max(boys)-min(boys)) if boys else 0, (max(girls)-min(girls)) if girls else 0),
        lang  = (max(good)   - min(good))  if good   else 0,
    )
    argmax = lambda s: max(per.keys(), key=lambda k: per[k][s]) if per else None
    argmin = lambda s: min(per.keys(), key=lambda k: per[k][s]) if per else None
    extremes = dict(
        pop_high = argmax("total"), pop_low  = argmin("total"),
        boys_high= argmax("boys"),  boys_low = argmin("boys"),
        girls_high=argmax("girls"), girls_low= argmin("girls"),
        lang_high= argmax("good"),  lang_low = argmin("good"),
    )
    return dict(per_class=per, deltas=deltas, extremes=extremes)

def penalty_score(df: pd.DataFrame, class_col: str, gender_col: str, lang_col: str) -> int:
    """
    Penalty:
      1) Πληθυσμός: +3 * max(0, Δπληθ - 1)
      2) Γλώσσα:    +1 * max(0, Δγλώσσας - 2)
      3) Φύλο:      +2 * (max(0, Δαγοριών-1) + max(0, Δκοριτσιών-1))
    """
    M = _metrics(df, class_col, gender_col, lang_col)
    d = M["deltas"]
    boys_over = max(0, d["boys"] - 1)
    girls_over = max(0, d["girls"] - 1)
    return 3 * max(0, d["pop"] - 1) + 1 * max(0, d["lang"] - 2) + 2 * (boys_over + girls_over)

def _is_step4(val) -> bool: return val in STEP4_MARKERS
def _is_step5(val) -> bool: return val in STEP5_MARKERS

def _eligible_units(df: pd.DataFrame, class_col: str, step_col: str, group_col: str,
                    gender_col: str, lang_col: str):
    """
    Επιστρέφει (singles, pairs), όπου:
    - singles[c] = IDs μεμονωμένων Βήματος 5 στο τμήμα c
    - pairs[c]   = λίστα dict για κάθε δυάδα Βήματος 4 στο τμήμα c:
        { 'group_id', 'ids':[id1,id2], 'gender_kind': 'Α'/'Κ'/'ΜΙΚΤΟ', 'lang_kind':'NN'/'OO'/'N+O' }
    """
    singles = {c: [] for c in _classes(df, class_col)}
    pairs   = {c: [] for c in _classes(df, class_col)}

    # singles: Βήμα 5, χωρίς group
    mask_solo = df[step_col].map(_is_step5) & (df[group_col].isna() | (df[group_col] == ""))
    for c, sub in df[mask_solo].groupby(class_col):
        singles[c] = sub[_IDCOL].tolist()

    # pairs: Βήμα 4, με group δύο μελών, όλα στο ίδιο τμήμα
    df_pairs = df[df[step_col].map(_is_step4) & df[group_col].notna()].copy()
    if not df_pairs.empty:
        for gid, g in df_pairs.groupby(group_col):
            if len(g) != 2:
                continue
            classes = g[class_col].unique()
            if len(classes) != 1:
                continue
            c = classes[0]
            genders = list(g[gender_col])
            langs   = list(g[lang_col])
            if genders.count(BOY) == 2:   gender_kind = BOY
            elif genders.count(GIRL) == 2:gender_kind = GIRL
            else:                         gender_kind = "ΜΙΚΤΟ"
            if langs.count(GOOD) == 2:    lang_kind = "NN"
            elif langs.count(NOTGOOD) == 2: lang_kind = "OO"
            else:                         lang_kind = "N+O"
            pairs[c].append(dict(group_id=gid, ids=list(g[_IDCOL]), gender_kind=gender_kind, lang_kind=lang_kind))
    return singles, pairs

def _check_size_ok(df: pd.DataFrame, class_col: str) -> bool:
    return (df[class_col].value_counts() <= MAX_PER_CLASS).all()

def _no_new_broken_friendships(df_before: pd.DataFrame, df_after: pd.DataFrame, class_col: str, group_col: str) -> bool:
    """Καμία διάσπαση δυάδων Β4 (μένουν στο ίδιο τμήμα)."""
    if group_col not in df_before.columns: return True
    b = df_before.dropna(subset=[group_col]).groupby(group_col)[class_col].nunique().le(1).all()
    a = df_after .dropna(subset=[group_col]).groupby(group_col)[class_col].nunique().le(1).all()
    return bool(b and a)

# --------------------------
# Swaps & Candidates (N classes)
# --------------------------
def _apply_swap(df: pd.DataFrame, class_col: str,
                fromA_ids: List[str], to_class_B,
                fromB_ids: List[str], to_class_A,
                reason: str, swap_idx: int,
                step_col: str, group_col: str) -> pd.DataFrame:
    """Εφαρμόζει ανταλλαγή ανάμεσα σε δύο ΣΥΓΚΕΚΡΙΜΕΝΑ τμήματα (N-classes safe)."""
    df = df.copy()
    if fromA_ids:
        df.loc[df[_IDCOL].isin(fromA_ids), class_col] = to_class_B
    if fromB_ids:
        df.loc[df[_IDCOL].isin(fromB_ids), class_col] = to_class_A

    swap_id = f"SWAP_{swap_idx}"
    moved_ids = list(fromA_ids) + list(fromB_ids)
    if moved_ids:
        m = df[_IDCOL].isin(moved_ids)
        df.loc[m, "ΒΗΜΑ6_ΚΙΝΗΣΗ"] = swap_id
        df.loc[m, "ΑΙΤΙΑ_ΑΛΛΑΓΗΣ"] = reason
        df.loc[m, "ΠΗΓΗ_ΒΗΜΑ"] = np.where(df.loc[m, group_col].notna(), "Β4_Δυάδα", "Β5_Μεμονωμένος")
    return df

def _rank_candidates(df_before: pd.DataFrame, class_col: str, gender_col: str, lang_col: str,
                     candidates, objective: str) -> List:
    """
    Κατατάσσει υποψήφιες ανταλλαγές:
      - LANG:  max μείωση Δγλώσσας, μετά Δφύλου, μετά μείωση penalty, μετά λιγότερες κινήσεις
      - GENDER:max μείωση Δφύλου,  μετά Δγλώσσας, μετά μείωση penalty, μετά λιγότερες κινήσεις
      - BOTH:  ταυτόχρονη μη-επιδείνωση και των δύο, προτερ. στη μείωση Δφύλου, μετά Δγλώσσας
    + Πληθυσμός (αυστηροποίηση):
      - Απαιτείται d_pop <= 2 ΠΑΝΤΑ.
      - Αν base_pop <= 2, τότε d_pop <= base_pop (μη επιδείνωση εντός στόχου).
    """
    base_M = _metrics(df_before, class_col, gender_col, lang_col)
    base_d = base_M["deltas"]
    base_pen = penalty_score(df_before, class_col, gender_col, lang_col)
    ranked = []

    for (fromA, classA, fromB, classB, reason) in candidates:
        tmp = _apply_swap(df_before, class_col, fromA, classB, fromB, classA, reason, 9999,
                          step_col="ΒΗΜΑ_ΤΟΠΟΘΕΤΗΣΗΣ", group_col="GROUP_ID")
        if not _check_size_ok(tmp, class_col):
            continue
        M = _metrics(tmp, class_col, gender_col, lang_col)
        d = M["deltas"]
        # 🔒 Population strictness
        if d["pop"] > TARGET_POP_DIFF:
            continue
        if base_d["pop"] <= TARGET_POP_DIFF and d["pop"] > base_d["pop"]:
            # μην επιδεινώνεις όταν ήδη εντός στόχου
            continue

        pen = penalty_score(tmp, class_col, gender_col, lang_col)
        dlang_gain   = base_d["lang"]   - d["lang"]
        dgender_gain = base_d["gender"] - d["gender"]
        pen_gain     = base_pen - pen

        # Μη χειροτέρευση του άλλου δείκτη
        if objective == "LANG"   and dgender_gain < 0: continue
        if objective == "GENDER" and dlang_gain   < 0: continue
        if objective == "BOTH"   and (dlang_gain < 0 or dgender_gain < 0): continue

        if objective in ("GENDER","BOTH"):
            key = (-dgender_gain, -dlang_gain, -pen_gain, len(fromA)+len(fromB))
        else:
            key = (-dlang_gain, -dgender_gain, -pen_gain, len(fromA)+len(fromB))
        ranked.append((key, fromA, classA, fromB, classB, reason))
    ranked.sort(key=lambda x: x[0])
    return [(fromA, classA, fromB, classB, reason) for _, fromA, classA, fromB, classB, reason in ranked]

def _enum_LANG(df: pd.DataFrame, class_col: str, gender_col: str, lang_col: str,
               step_col: str, group_col: str, top_k:int=2):
    """Υποψήφιοι swaps για Γλώσσα μεταξύ top_k υψηλών και χαμηλών τμημάτων ως προς 'good'."""
    M = _metrics(df, class_col, gender_col, lang_col)
    per = M["per_class"]
    # ταξινόμηση κατά good
    classes_sorted = sorted(per.keys(), key=lambda c: per[c]["good"], reverse=True)
    highs = classes_sorted[:top_k]
    lows  = list(reversed(classes_sorted))[:top_k]

    singles, pairs = _eligible_units(df, class_col, step_col, group_col, gender_col, lang_col)
    cand = []
    for high in highs:
        for low in lows:
            if high == low: continue
            # 1↔1 (Ν ↔ Ο)
            singles_high_good = df[df[_IDCOL].isin(singles[high]) & (df[lang_col] == GOOD)][_IDCOL].tolist()
            singles_low_not   = df[df[_IDCOL].isin(singles[low])  & (df[lang_col] == NOTGOOD)][_IDCOL].tolist()
            for i in singles_high_good:
                for j in singles_low_not:
                    cand.append(( [i], high, [j], low, "Language" ))
            # 2↔2 (NN ↔ OO)
            pairs_high_NN = [p for p in pairs[high] if p["lang_kind"]=="NN"]
            pairs_low_OO  = [p for p in pairs[low]  if p["lang_kind"]=="OO"]
            for pNN in pairs_high_NN:
                for pOO in pairs_low_OO:
                    cand.append(( pNN["ids"], high, pOO["ids"], low, "Language" ))
            # 2↔1+1 (NN ↔ Ο+Ο)
            if pairs_high_NN and len(singles_low_not) >= 2:
                for pNN in pairs_high_NN:
                    for two in itertools.combinations(singles_low_not, 2):
                        cand.append(( pNN["ids"], high, list(two), low, "Language" ))
            # αντίστροφα (OO ↔ Ν+Ν)
            pairs_high_OO = [p for p in pairs[high] if p["lang_kind"]=="OO"]
            singles_low_good = df[df[_IDCOL].isin(singles[low]) & (df[lang_col] == GOOD)][_IDCOL].tolist()
            if pairs_high_OO and len(singles_low_good) >= 2:
                for pOO in pairs_high_OO:
                    for two in itertools.combinations(singles_low_good, 2):
                        cand.append(( list(two), low, pOO["ids"], high, "Language" ))
    return cand

def _enum_GENDER(df: pd.DataFrame, class_col: str, gender_col: str, lang_col: str,
                 step_col: str, group_col: str, top_k:int=2):
    """Υποψήφιοι swaps για Φύλο μεταξύ top_k υψηλών και χαμηλών ως προς target gender."""
    M = _metrics(df, class_col, gender_col, lang_col)
    per = M["per_class"]
    # ποιο φύλο έχει μεγαλύτερη απόκλιση;
    boys_diff = M["deltas"]["boys"]
    girls_diff = M["deltas"]["girls"]
    target_gender = BOY if boys_diff >= girls_diff else GIRL

    # ταξινόμηση κατά πλήθος target φύλου
    classes_sorted = sorted(per.keys(), key=lambda c: per[c]["boys" if target_gender==BOY else "girls"], reverse=True)
    highs = classes_sorted[:top_k]
    lows  = list(reversed(classes_sorted))[:top_k]

    singles, pairs = _eligible_units(df, class_col, step_col, group_col, gender_col, lang_col)
    cand = []
    opp_gender = GIRL if target_gender==BOY else BOY
    for high in highs:
        for low in lows:
            if high == low: continue
            # 1↔1 (ίδια γνώση προτιμητέα)
            ids_high = df[df[_IDCOL].isin(singles[high]) & (df[gender_col] == target_gender)][_IDCOL].tolist()
            for i in ids_high:
                lang_i = df.loc[df[_IDCOL]==i, lang_col].iloc[0]
                same_lang = df[
                    df[_IDCOL].isin(singles[low]) & (df[gender_col]==opp_gender) & (df[lang_col]==lang_i)
                ][_IDCOL].tolist()
                any_lang = df[
                    df[_IDCOL].isin(singles[low]) & (df[gender_col]==opp_gender)
                ][_IDCOL].tolist()
                for j in same_lang: cand.append(([i], high, [j], low, "Gender"))
                for j in any_lang:  cand.append(([i], high, [j], low, "Gender"))
            # 2↔2
            pairs_high_g = [p for p in pairs[high] if p["gender_kind"]==target_gender]
            pairs_low_og = [p for p in pairs[low]  if p["gender_kind"]==opp_gender]
            for p1 in pairs_high_g:
                for p2 in pairs_low_og:
                    cand.append((p1["ids"], high, p2["ids"], low, "Gender"))
            # 2↔1+1
            singles_low_opp = df[df[_IDCOL].isin(singles[low]) & (df[gender_col]==opp_gender)][_IDCOL].tolist()
            for p1 in pairs_high_g:
                if len(singles_low_opp) >= 2:
                    for two in itertools.combinations(singles_low_opp, 2):
                        cand.append((p1["ids"], high, list(two), low, "Gender"))
    return cand

def _enum_BOTH(df: pd.DataFrame, class_col: str, gender_col: str, lang_col: str,
               step_col: str, group_col: str, top_k:int=2):
    cand = []
    cand += _enum_LANG(df, class_col, gender_col, lang_col, step_col, group_col, top_k=top_k)
    cand += _enum_GENDER(df, class_col, gender_col, lang_col, step_col, group_col, top_k=top_k)
    return cand

def _commit_best_swap_if_improves(df: pd.DataFrame, class_col: str, gender_col: str, lang_col: str,
                                  step_col: str, group_col: str, objective: str, swap_idx: int) -> Tuple[pd.DataFrame, bool]:
    # Υποψήφιοι
    if objective == "LANG":
        candidates = _enum_LANG(df, class_col, gender_col, lang_col, step_col, group_col)
    elif objective == "GENDER":
        candidates = _enum_GENDER(df, class_col, gender_col, lang_col, step_col, group_col)
    else:
        candidates = _enum_BOTH(df, class_col, gender_col, lang_col, step_col, group_col)

    ranked = _rank_candidates(df, class_col, gender_col, lang_col, candidates, objective)
    if not ranked: return df, False

    base_M = _metrics(df, class_col, gender_col, lang_col)
    base_d = base_M["deltas"]
    base_pen = penalty_score(df, class_col, gender_col, lang_col)

    for (fromA, classA, fromB, classB, reason) in ranked:
        tmp = _apply_swap(df, class_col, fromA, classB, fromB, classA, reason, swap_idx, step_col, group_col)
        # Σκληροί έλεγχοι
        if not _check_size_ok(tmp, class_col): continue
        if not _no_new_broken_friendships(df, tmp, class_col, group_col): continue
        # Πληθυσμός: πάντα <=2 και μη-επιδείνωση όταν ήδη εντός
        d = _metrics(tmp, class_col, gender_col, lang_col)["deltas"]
        if d["pop"] > TARGET_POP_DIFF: continue
        if base_d["pop"] <= TARGET_POP_DIFF and d["pop"] > base_d["pop"]: continue
        # Μείωση penalty
        if penalty_score(tmp, class_col, gender_col, lang_col) < base_pen:
            return tmp, True
    return df, False

# --------------------------
# Public API
# --------------------------

def apply_step6_to_step5_scenarios(step5_outputs: Dict[str, pd.DataFrame],
                                   *, class_col="ΤΜΗΜΑ", id_col="ID", gender_col="ΦΥΛΟ",
                                   lang_col="ΚΑΛΗ_ΓΝΩΣΗ_ΕΛΛΗΝΙΚΩΝ", step_col="ΒΗΜΑ_ΤΟΠΟΘΕΤΗΣΗΣ",
                                   group_col="GROUP_ID", max_iter: int = MAX_ITER) -> Dict[str, Dict]:
    """
    Adapter: Τρέχει το Βήμα 6 πάνω σε ΠΟΛΛΑ σενάρια που έρχονται από το Βήμα 5.
    Είσοδος: dict { "ΣΕΝΑΡΙΟ_1": df5_1, "ΣΕΝΑΡΙΟ_2": df5_2, ... }
    Έξοδος: dict με ίδια keys και values {"df": df6, "summary": {...}}
    """
    results = {}
    for name, df5 in step5_outputs.items():
        out = apply_step6(df5.copy(), class_col=class_col, id_col=id_col, gender_col=gender_col,
                          lang_col=lang_col, step_col=step_col, group_col=group_col, max_iter=max_iter)
        results[name] = out
    return results

if __name__ == "__main__":
    # Optional: quick smoke test with 3 classes
    data = [
        [1, "Α1", "Α", "Ν", 4, "G1"],
        [2, "Α1", "Α", "Ν", 4, "G1"],
        [3, "Α1", "Κ", "Ο", 5, None],
        [4, "Α1", "Κ", "Ν", 5, None],

        [5, "Β1", "Κ", "Ο", 4, "G2"],
        [6, "Β1", "Κ", "Ο", 4, "G2"],
        [7, "Β1", "Α", "Ν", 5, None],
        [8, "Β1", "Α", "Ο", 5, None],

        [9,  "Γ1", "Α", "Ν", 5, None],
        [10, "Γ1", "Κ", "Ν", 5, None],
    ]
    df_ex = pd.DataFrame(data, columns=["ID", "ΤΜΗΜΑ", "ΦΥΛΟ", "ΚΑΛΗ_ΓΝΩΣΗ_ΕΛΛΗΝΙΚΩΝ", "ΒΗΜΑ_ΤΟΠΟΘΕΤΗΣΗΣ", "GROUP_ID"])
    res = apply_step6(df_ex)
    print(res["summary"])



def apply_step6(df: pd.DataFrame,
                *, class_col="ΤΜΗΜΑ", id_col="ID", gender_col="ΦΥΛΟ",
                lang_col="ΚΑΛΗ_ΓΝΩΣΗ_ΕΛΛΗΝΙΚΩΝ", step_col="ΒΗΜΑ_ΤΟΠΟΘΕΤΗΣΗΣ",
                group_col="GROUP_ID", max_iter: int = MAX_ITER) -> Dict:
    """
    Εφαρμογή Βήματος 6 για N (≥2) τμήματα.
    Κινήσεις ΜΟΝΟ μεταξύ Β4-δυάδων (αδιαίρετες) και Β5-μεμονωμένων.
    Δεν αγγίζονται μαθητές Βημάτων 1–3.
    Targets: Δπληθ ≤2, Δφύλου ≤3, Δγλώσσας ≤3.

    Όταν οι αποκλίσεις είναι ήδη εντός στόχων (Δπληθ ≤2, Δφύλου ≤3, Γλώσσας ≤3),
    ο αλγόριθμος δεν σταματά αμέσως· δοκιμάζει επιπλέον έγκυρες ανταλλαγές που:
      • μειώνουν το συνολικό penalty,
      • δεν χειροτερεύουν τον άλλο δείκτη (φύλο/γλώσσα),
      • τηρούν SIZE_OK (≤25), FRIENDS_OK (δεν σπάει δυάδες), SCOPE_OK (μόνο Β4-δυάδες/Β5-μεμονωμένοι),
      • δεν αυξάνουν τη διαφορά πληθυσμού (και πάντα κρατούν Δπληθ ≤2).
    Σταματά όταν δεν υπάρχει καλύτερη ανταλλαγή ή φτάσει ≤5 iterations.
    """
    # --- Patched prologue ---
    global _IDCOL
    _IDCOL = id_col
    # BEFORE snapshot for auditing
    if "ΤΜΗΜΑ_ΠΡΙΝ_ΒΗΜΑ6" not in df.columns and class_col in df.columns:
        df["ΤΜΗΜΑ_ΠΡΙΝ_ΒΗΜΑ6"] = df[class_col]

    # Έλεγχοι βασικών στηλών
    for col in [id_col, class_col, gender_col, lang_col, step_col]:
        if col not in df.columns:
            raise ValueError(f"Λείπει η στήλη '{col}'.")
    if group_col not in df.columns:
        df = df.copy()
        df[group_col] = np.nan

    # Audit columns
    for c in ["ΒΗΜΑ6_ΚΙΝΗΣΗ", "ΑΙΤΙΑ_ΑΛΛΑΓΗΣ", "ΠΗΓΗ_ΒΗΜΑ"]:
        if c not in df.columns:
            df[c] = None

    # Iterations
    iterations = 0
    status = "VALID"
    while iterations < max_iter:
        iterations += 1
        d = _metrics(df, class_col, gender_col, lang_col)["deltas"]
        within_targets = (d["pop"] <= TARGET_POP_DIFF) and (d["gender"] <= TARGET_GENDER_DIFF) and (d["lang"] <= TARGET_LANG_DIFF)

        # Triggers
        if not within_targets:
            if (d["gender"] <= TARGET_GENDER_DIFF) and (d["lang"] > TARGET_LANG_DIFF):
                objective = "LANG"
            elif (d["lang"] <= TARGET_LANG_DIFF) and (d["gender"] > TARGET_GENDER_DIFF):
                objective = "GENDER"
            else:
                objective = "BOTH"
        else:
            # Εντός στόχων: προσπάθησε να μειώσεις περαιτέρω το penalty χωρίς να χαλάς τίποτα
            objective = "BOTH"

        df2, changed = _commit_best_swap_if_improves(df, class_col, gender_col, lang_col, step_col, group_col, objective, iterations)
        if not changed:
            # Δεν υπάρχει καλύτερη ανταλλαγή — τερματισμός
            break
        df = df2

    final_M = _metrics(df, class_col, gender_col, lang_col)
    final_pen = penalty_score(df, class_col, gender_col, lang_col)
    final_ok = (final_M["deltas"]["pop"] <= TARGET_POP_DIFF) and \
               (final_M["deltas"]["gender"] <= TARGET_GENDER_DIFF) and \
               (final_M["deltas"]["lang"] <= TARGET_LANG_DIFF)
    if not final_ok:
        status = "IMPOSSIBLE"

    summary = dict(
        iterations=iterations,
        final_deltas=final_M["deltas"],
        per_class=final_M["per_class"],
        final_penalty=final_pen,
        status=status,
    )
    
    # === Patched explicit Step 6 outputs ===
    if "ΤΜΗΜΑ_ΜΕΤΑ_ΒΗΜΑ6" not in df.columns and class_col in df.columns:
        df["ΤΜΗΜΑ_ΜΕΤΑ_ΒΗΜΑ6"] = df[class_col]
    try:
        import numpy as np
        df["ΜΕΤΑΒΟΛΗ_ΤΜΗΜΑΤΟΣ"] = np.where(
            df["ΤΜΗΜΑ_ΠΡΙΝ_ΒΗΜΑ6"].astype(str) == df["ΤΜΗΜΑ_ΜΕΤΑ_ΒΗΜΑ6"].astype(str),
            "STAY",
            df["ΤΜΗΜΑ_ΠΡΙΝ_ΒΗΜΑ6"].astype(str) + "→" + df["ΤΜΗΜΑ_ΜΕΤΑ_ΒΗΜΑ6"].astype(str)
        )
    except Exception:
        pass
    df["ΒΗΜΑ6_ΤΜΗΜΑ"] = df.get("ΤΜΗΜΑ_ΜΕΤΑ_ΒΗΜΑ6", df.get(class_col))
    # Scenario-specific ΒΗΜΑ6_ΣΕΝΑΡΙΟ_N__1 if we detect N from Step 5 columns
    scen_num = None
    import re as _re
    for c in df.columns:
        m = _re.match(r"ΒΗΜΑ5_ΣΕΝΑΡΙΟ_(\d+)__1$", str(c))
        if m:
            scen_num = m.group(1)
            break
    if scen_num and f"ΒΗΜΑ6_ΣΕΝΑΡΙΟ_{scen_num}__1" not in df.columns:
        df[f"ΒΗΜΑ6_ΣΕΝΑΡΙΟ_{scen_num}__1"] = df["ΒΗΜΑ6_ΤΜΗΜΑ"]
    return {"df": df, "summary": summary}