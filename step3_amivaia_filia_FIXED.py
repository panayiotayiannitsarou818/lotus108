
# -*- coding: utf-8 -*-
"""
step3_amivaia_filia_FIXED.py
- Επεξεργάζεται ΟΛΑ τα sheets "ΒΗΜΑ2_ΣΕΝΑΡΙΟ_*" από workbook Βήμα 2
- Φτιάχνει ανά sheet μια νέα στήλη "ΒΗΜΑ3_ΣΕΝΑΡΙΟ_k" με τοποθέτηση ΜΟΝΟ ΔΥΑΔΩΝ
  όπου ο 1 είναι ήδη τοποθετημένος (στο Βήμα 2) και ο 2 είναι ατοποθέτητος.
- Δεν «σπάει» καμία δυάδα: αν δεν χωράει λόγω ορίου 25, η δυάδα μετρά ως broken και ο ατοποθέτητος παραμένει κενός.
- Υπολογίζει broken δυάδες & penalty, επιλέγει έως 5 καλύτερα σενάρια.
"""

from typing import List, Tuple, Dict
import pandas as pd
import re
from pathlib import Path
from step_3_helpers_FIXED import (
    parse_friends_string, are_mutual_pair, mutual_dyads,
    count_broken_dyads, calculate_penalty_score_step3, select_best_scenarios
)

def _class_fits(df: pd.DataFrame, col: str, class_name: str, add: int=1) -> bool:
    return (df[col]==class_name).sum() + add <= 25

def apply_step3_on_sheet(df2: pd.DataFrame, scenario_col: str, num_classes: int) -> Tuple[pd.DataFrame, Dict]:
    """
    Παίρνει ένα DataFrame από Βήμα 2 (ένα sheet) και επιστρέφει:
    - df_after: με νέα στήλη ΒΗΜΑ3_ΣΕΝΑΡΙΟ_k (ίδιο όνομα με το sheet αλλά με 'ΒΗΜΑ3')
    - meta: {"broken": int, "penalty": int}
    Κανόνας: τοποθετούμε ΜΟΝΟ δυάδες (u,v) όπου u είναι unplaced, v είναι placed, και είναι αμοιβαία φίλοι.
    """
    df = df2.copy()
    # νέα στήλη
    new_col = re.sub(r"^ΒΗΜΑ2", "ΒΗΜΑ3", scenario_col)
    df[new_col] = df[scenario_col]

    placed = df[df[scenario_col].notna()][["ΟΝΟΜΑ", scenario_col]].set_index("ΟΝΟΜΑ")[scenario_col].to_dict()
    # unplaced υποψήφιοι (γενικά όλοι οι κενές αναθέσεις)
    unplaced_names = df[df[new_col].isna()]["ΟΝΟΜΑ"].astype(str).tolist()

    # δώσε προτεραιότητα σε όσους έχουν ΑΚΡΙΒΩΣ 1 αμοιβαίο φίλο (μονοσήμαντες δυάδες)
    def mutual_friends_of(u: str) -> list:
        friends = parse_friends_string(df.loc[df["ΟΝΟΜΑ"]==u, "ΦΙΛΟΙ"].values[0] if not df.loc[df["ΟΝΟΜΑ"]==u, "ΦΙΛΟΙ"].empty else "")
        return [v for v in friends if are_mutual_pair(df, u, v)]

    # κατασκεύασε λίστα (u, v, class_v) για v ήδη placed
    candidates = []
    for u in unplaced_names:
        for v in mutual_friends_of(u):
            if v in placed:
                candidates.append((u, v, placed[v]))

    # Ταξινόμηση: λιγότερες επιλογές πρώτα → μειώνει αδιέξοδα
    degree = {u: len([1 for x in candidates if x[0]==u]) for u in unplaced_names}
    candidates.sort(key=lambda t: (degree.get(t[0], 99), t[2]))

    used_u = set()
    for u, v, cl in candidates:
        if u in used_u:
            continue
        if _class_fits(df, new_col, cl, add=1):
            df.loc[df["ΟΝΟΜΑ"]==u, new_col] = cl
            used_u.add(u)
            # ενημέρωσε και το placed ώστε αν έχει κι άλλος φίλος τον u, τώρα να θεωρείται placed
            placed[u] = cl

    # Μετρικά
    broken = count_broken_dyads(df2, df, new_col)
    penalty = calculate_penalty_score_step3(df, new_col, num_classes)
    meta = {"broken": int(broken), "penalty": int(penalty)}
    return df, meta

def step3_run_all_from_step2(step2_xlsx_path: str, output_xlsx_path: str) -> str:
    """
    Διαβάζει το workbook του Βήμα 2 και παράγει νέο workbook για το Βήμα 3
    με ένα sheet ανά σενάριο. Επιστρέφει το path του αρχείου.
    """
    p = Path(step2_xlsx_path)
    assert p.exists(), f"Δεν βρέθηκε: {p}"
    xls = pd.ExcelFile(p)
    s2_sheets = [s for s in xls.sheet_names if s.startswith("ΒΗΜΑ2_ΣΕΝΑΡΙΟ_")]
    if not s2_sheets:
        raise ValueError("Δεν βρέθηκαν sheets 'ΒΗΜΑ2_ΣΕΝΑΡΙΟ_*' στο αρχείο Βήμα 2.")

    # infer num_classes από το πρώτο sheet
    df0 = pd.read_excel(p, sheet_name=s2_sheets[0])
    classes = sorted([c for c in df0[s2_sheets[0]].dropna().astype(str).unique() if re.match(r"^Α\d+$", str(c))])
    num_classes = len(classes) if classes else 2

    results = []
    for s in s2_sheets:
        df2 = pd.read_excel(p, sheet_name=s)
        df3, meta = apply_step3_on_sheet(df2, scenario_col=s, num_classes=num_classes)
        results.append((re.sub(r"^ΒΗΜΑ2", "ΒΗΜΑ3", s), df3, meta))

    # Επιλογή έως 5 καλύτερων
    selected = select_best_scenarios(results)

    # Γράψε αρχείο
    out = Path(output_xlsx_path)
    with pd.ExcelWriter(out, engine="openpyxl") as w:
        for name, df3, meta in selected:
            df3.to_excel(w, index=False, sheet_name=name[:31])
        # και ένα sheet "Σύνοψη"
        rows = [{"Sheet": name, "Broken_dyads": meta["broken"], "Penalty": meta["penalty"]}
                for name, _, meta in selected]
        pd.DataFrame(rows).to_excel(w, index=False, sheet_name="Σύνοψη")

    return out.as_posix()
