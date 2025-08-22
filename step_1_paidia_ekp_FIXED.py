# -*- coding: utf-8 -*-
"""
Βήμα 1 – Κατανομή Παιδιών Εκπαιδευτικών (τελική λογική)
------------------------------------------------------
Εφαρμόζεται ΜΟΝΟ στα παιδιά με ΠΑΙΔΙ_ΕΚΠΑΙΔΕΥΤΙΚΟΥ = "Ν".

Κανόνας 1 (k <= m): Τοποθετείται το πολύ 1 παιδί/τμήμα, σειριακά. Παράγεται 1 σενάριο.
Κανόνας 2 (k > m): Εξαντλητική παραγωγή όλων των κατανομών στα διαθέσιμα τμήματα και
άμεση απόρριψη σεναρίων που:
  • περιέχουν ζεύγη «ΣΥΓΚΡΟΥΣΗ_ΜΕ» στο ίδιο τμήμα,
  • έχουν ανισοκατανομή > 1 (max(count) - min(count) > 1),
  • βάζουν όλα τα παιδιά στο ίδιο τμήμα.

Κανονικοποίηση: Θεωρούνται ίδια σενάρια όσα έχουν τα ίδια σύνολα μαθητών ανά τμήμα,
ανεξάρτητα από την ετικέτα τμήματος (Α1/Α2/…).
Περιορισμός: Επιστρέφονται έως 5 σενάρια. Αν >5, προτιμώνται όσα ΔΕΝ «σπάνε»
πλήρως αμοιβαίες φιλίες μεταξύ παιδιών εκπαιδευτικών (στήλη «ΦΙΛΟΙ»). Αν και πάλι >5,
επιλέγονται τυχαία 5 (με σταθερό seed για αναπαραγωγιμότητα).
Αν δεν υπάρχει σενάριο που να διατηρεί όλες τις αμοιβαίες φιλίες, κρατιούνται όσα
σπάνε τις λιγότερες (tie → τυχαία 5 με seed).

Έξοδος: Προσθέτει έως 5 στήλες ΒΗΜΑ1_ΣΕΝΑΡΙΟ_1 … _5 που συμπληρώνονται ΜΟΝΟ για
τα παιδιά εκπαιδευτικών. Οι υπόλοιπες γραμμές μένουν κενές στο Βήμα 1.
"""

from __future__ import annotations
import itertools
import random
from typing import Dict, List, Tuple, Set, Iterable, Optional
import pandas as pd


# ----------------------------- Βοηθητικά ------------------------------------

def _coerce_str(x) -> str:
    if pd.isna(x):
        return ""
    return str(x).strip()


def _parse_list(cell: str) -> List[str]:
    """Παίρνει κελί με ονόματα χωρισμένα με κόμμα και επιστρέφει λίστα καθαρών ονομάτων."""
    s = _coerce_str(cell)
    if not s:
        return []
    return [part.strip() for part in s.split(",") if part.strip()]


def _detect_col(df: pd.DataFrame, candidates: Iterable[str]) -> Optional[str]:
    """Επιστρέφει το πρώτο όνομα στήλης που υπάρχει στο df από τα candidates (case-insensitive)."""
    lowered = {c.lower(): c for c in df.columns}
    for cand in candidates:
        key = cand.lower()
        if key in lowered:
            return lowered[key]
    # χαλαρό matching: περιέχει υπο-αλφαριθμητικό
    for col in df.columns:
        col_l = col.lower().replace(" ", "")
        for cand in candidates:
            c = cand.lower().replace(" ", "")
            if c in col_l:
                return col
    return None


def _build_conflict_pairs(df_teach: pd.DataFrame, name_col: str, conflict_col: Optional[str]) -> Set[frozenset]:
    """Φτιάχνει σύνολο ζευγών σύγκρουσης (μη κατευθυντικά) μεταξύ παιδιών εκπαιδευτικών."""
    pairs: Set[frozenset] = set()
    if conflict_col is None or conflict_col not in df_teach.columns:
        return pairs
    names_set = set(df_teach[name_col].astype(str))
    for _, row in df_teach.iterrows():
        a = _coerce_str(row[name_col])
        for b in _parse_list(_coerce_str(row[conflict_col])):
            if b in names_set and a and b and a != b:
                pairs.add(frozenset((a, b)))
    return pairs


def _build_mutual_friend_groups(df_teach: pd.DataFrame, name_col: str, friends_col: Optional[str]) -> Tuple[Set[frozenset], Set[frozenset]]:
    """
    Επιστρέφει δύο σύνολα:
      • mutual_pairs: αμοιβαίες δυάδες (A<->B)
      • mutual_trios: πλήρως αμοιβαίες τριάδες (A<->B, B<->C, A<->C)
    Χρησιμοποιείται ΜΟΝΟ για να προτιμηθούν σενάρια που ΔΕΝ «σπάνε» φιλίες.
    """
    mutual_pairs: Set[frozenset] = set()
    mutual_trios: Set[frozenset] = set()
    if friends_col is None or friends_col not in df_teach.columns:
        return mutual_pairs, mutual_trios

    names = list(df_teach[name_col].astype(str))
    idx_by_name = {n: i for i, n in enumerate(names)}

    # adjacency: name -> set(friend_names declared)
    declared = {n: set() for n in names}
    for _, row in df_teach.iterrows():
        a = _coerce_str(row[name_col])
        for b in _parse_list(_coerce_str(row[friends_col])):
            if b in idx_by_name and b != a:
                declared[a].add(b)

    # αμοιβαίες δυάδες
    for a, b in itertools.combinations(names, 2):
        if b in declared.get(a, set()) and a in declared.get(b, set()):
            mutual_pairs.add(frozenset((a, b)))

    # πλήρως αμοιβαίες τριάδες (επιτρέπεται στο Βήμα 1 – οι κανόνες 3–5 δεν ισχύουν εδώ)
    for a, b, c in itertools.combinations(names, 3):
        if (frozenset((a, b)) in mutual_pairs and
            frozenset((a, c)) in mutual_pairs and
            frozenset((b, c)) in mutual_pairs):
            mutual_trios.add(frozenset((a, b, c)))

    return mutual_pairs, mutual_trios


def _counts_ok(counts: List[int]) -> bool:
    """Ανισοκατανομή <=1 και όχι όλα στο ίδιο τμήμα."""
    if not counts:
        return True
    if max(counts) - min(counts) > 1:
        return False
    if max(counts) == sum(counts):  # όλα σε ένα τμήμα
        # επιτρέπεται μόνο αν υπάρχει 1 τμήμα· αλλιώς reject
        return len(counts) == 1
    return True


def _scenario_signature(assign: Dict[str, str], classes: List[str]) -> Tuple[Tuple[str, ...], ...]:
    """
    Κανονικοποιημένη υπογραφή σεναρίου: λίστα από «ομάδες ονομάτων ανά τμήμα»
    (ως ταξινομημένα tuples), ταξινομημένη ανεξάρτητα από την ετικέτα τμήματος.
    Έτσι Α1↔Α2 παράγουν την ίδια υπογραφή → θεωρούνται ίδιο σενάριο.
    """
    by_class = {c: [] for c in classes}
    for name, cls in assign.items():
        by_class[cls].append(name)
    groups = [tuple(sorted(v)) for v in by_class.values()]
    groups.sort()  # αγνοούμε label τμήματος
    return tuple(groups)


def _broken_friendships_score(assign: Dict[str, str],
                              mutual_pairs: Set[frozenset],
                              mutual_trios: Set[frozenset]) -> int:
    """Μετρά «σπασμένες» αμοιβαίες φιλίες σε δυάδες & τριάδες (αν μέλη σε διαφορετικά τμήματα)."""
    score = 0
    # δυάδες
    for pair in mutual_pairs:
        a, b = tuple(pair)
        if assign.get(a) != assign.get(b):
            score += 1
    # τριάδες
    for trio in mutual_trios:
        a, b, c = tuple(trio)
        cls = assign.get(a)
        if not (assign.get(b) == cls and assign.get(c) == cls):
            score += 1
    return score


# --------------------------- Πυρήνας Βήματος 1 -------------------------------

def step1_assign_teacher_children(
    df: pd.DataFrame,
    classes: List[str],
    name_col_candidates: Iterable[str] = ("ΟΝΟΜΑ", "ΟΝΟΜΑΤΕΠΩΝΥΜΟ", "ΜΑΘΗΤΗΣ", "ΜΑΘΗΤΗΣ/ΡΙΑ"),
    teacher_child_col_candidates: Iterable[str] = ("ΠΑΙΔΙ_ΕΚΠΑΙΔΕΥΤΙΚΟΥ", "ΠΑΙΔΙ ΕΚΠΑΙΔΕΥΤΙΚΟΥ", "ΕΚΠΑΙΔΕΥΤΙΚΟΙ"),
    conflict_col_candidates: Iterable[str] = ("ΣΥΓΚΡΟΥΣΗ_ΜΕ", "ΣΥΓΚΡΟΥΣΗ", "ΣΥΓΚΡΟΥΣΕΙΣ", "CONFLICT_WITH"),
    friends_col_candidates: Iterable[str] = ("ΦΙΛΟΙ", "ΦΙΛΙΑ", "ΦΙΛΟΙ_ΜΕ", "FRIENDS"),
    scenario_prefix: str = "ΒΗΜΑ1_ΣΕΝΑΡΙΟ_",
    max_scenarios: int = 5,
    random_seed: int = 20250822,
) -> pd.DataFrame:
    """
    Προσθέτει έως 5 στήλες σεναρίων Βήματος 1 στο df, μόνο για τα παιδιά εκπαιδευτικών.
    Επιστρέφει το df (αντιγραφή).
    """
    df = df.copy()

    name_col = _detect_col(df, name_col_candidates)
    tch_col = _detect_col(df, teacher_child_col_candidates)
    conflict_col = _detect_col(df, conflict_col_candidates)
    friends_col = _detect_col(df, friends_col_candidates)

    if not name_col:
        raise KeyError("Δεν βρέθηκε στήλη ονόματος (π.χ. 'ΟΝΟΜΑ'/'ΟΝΟΜΑΤΕΠΩΝΥΜΟ'/'ΜΑΘΗΤΗΣ').")
    if not tch_col:
        raise KeyError("Δεν βρέθηκε στήλη 'ΠΑΙΔΙ_ΕΚΠΑΙΔΕΥΤΙΚΟΥ'.")

    # Filter: παιδιά εκπαιδευτικών
    mask = df[tch_col].astype(str).str.upper().str.strip().eq("Ν")
    df_teach = df.loc[mask].copy()
    df_teach[name_col] = df_teach[name_col].astype(str)
    names = list(df_teach[name_col])

    # Αν δεν υπάρχουν, δεν δημιουργούμε στήλες – το pipeline προχωρά στο Βήμα 2
    if len(names) == 0:
        return df

    # Σύγκρουση-φίλοι (μόνο στο υποσύνολο παιδιών εκπαιδευτικών)
    conflict_pairs = _build_conflict_pairs(df_teach, name_col, conflict_col)
    mutual_pairs, mutual_trios = _build_mutual_friend_groups(df_teach, name_col, friends_col)

    m = len(classes)
    k = len(names)

    # Προετοιμασία output στηλών
    out_cols = [f"{scenario_prefix}{i}" for i in range(1, max_scenarios + 1)]
    for c in out_cols:
        df[c] = ""  # γεμίζουμε με κενό string για καθαρή εμφάνιση στο Excel

    # ---------------- Κανόνας 1: k <= m ----------------
    if k <= m:
        assign = {}
        for i, child in enumerate(names):
            cls = classes[i % m]  # «το πολύ 1 ανά τμήμα» → απλώς σειριακή τοποθέτηση
            assign[child] = cls
        # Γράψιμο στη ΒΗΜΑ1_ΣΕΝΑΡΙΟ_1
        col = out_cols[0]
        for child, cls in assign.items():
            idx = df.index[df[name_col].astype(str) == child]
            df.loc[idx, col] = cls
        return df

    # ---------------- Κανόνας 2: k > m -----------------
    # Εξαντλητική παραγωγή όλων των κατανομών (m^k)
    all_assignments: List[Dict[str, str]] = []
    for choice in itertools.product(classes, repeat=k):
        assign = {child: choice[i] for i, child in enumerate(names)}
        all_assignments.append(assign)

    # Άμεση απόρριψη / validation
    def is_valid(assign: Dict[str, str]) -> bool:
        # (α) ζεύγη σύγκρουσης στο ίδιο τμήμα → reject
        for pair in conflict_pairs:
            a, b = tuple(pair)
            if assign.get(a) == assign.get(b):
                return False
        # (β) ανισοκατανομή > 1
        counts_by_class = {c: 0 for c in classes}
        for cls in assign.values():
            counts_by_class[cls] += 1
        counts = list(counts_by_class.values())
        if not _counts_ok(counts):
            return False
        return True

    valid: List[Dict[str, str]] = [a for a in all_assignments if is_valid(a)]

    # Κανονικοποίηση/Μοναδικότητα (αγνοούμε label τμήματος)
    seen = set()
    unique_valid: List[Dict[str, str]] = []
    for a in valid:
        sig = _scenario_signature(a, classes)
        if sig not in seen:
            seen.add(sig)
            unique_valid.append(a)

    # Αν δεν υπάρχουν έγκυρα → καθόλου output (μένουν κενές οι στήλες)
    if not unique_valid:
        return df

    # Αν >5, προτιμάμε όσα ΔΕΝ σπάνε αμοιβαίες φιλίες (δυάδες/τριάδες)
    random.seed(random_seed)

    def broken_score(a: Dict[str, str]) -> int:
        return _broken_friendships_score(a, mutual_pairs, mutual_trios)

    selected: List[Dict[str, str]]

    if len(unique_valid) > 5:
        zero_break = [a for a in unique_valid if broken_score(a) == 0]
        if len(zero_break) == 0:
            # δεν υπάρχει σενάριο που να κρατά όλες τις φιλίες → πάμε στα «λιγότερα σπασίματα»
            min_br = min(broken_score(a) for a in unique_valid)
            best = [a for a in unique_valid if broken_score(a) == min_br]
            selected = random.sample(best, k=min(5, len(best)))
        elif len(zero_break) <= 5:
            selected = zero_break
        else:
            selected = random.sample(zero_break, k=5)
    else:
        selected = unique_valid

    # Γράψιμο έως 5 στηλών
    for j, assign in enumerate(selected, start=1):
        col = f"{scenario_prefix}{j}"
        for child, cls in assign.items():
            idx = df.index[df[name_col].astype(str) == child]
            df.loc[idx, col] = cls

    return df


# ------------------------------- CLI ----------------------------------------

def _cli():
    import argparse
    parser = argparse.ArgumentParser(
        description="Βήμα 1 – Κατανομή Παιδιών Εκπαιδευτικών (παραγωγή έως 5 σεναρίων)."
    )
    parser.add_argument("--input", required=True, help="Είσοδος Excel (.xlsx)")
    parser.add_argument("--output", required=True, help="Έξοδος Excel (.xlsx)")
    parser.add_argument("--classes", required=False, default="Α1,Α2",
                        help="Λίστα τμημάτων χωρισμένα με κόμμα (default: Α1,Α2)")
    parser.add_argument("--sheet", required=False, default=None,
                        help="Όνομα φύλλου (default: πρώτο φύλλο)")
    parser.add_argument("--seed", required=False, type=int, default=20250822,
                        help="Random seed για επιλογή 5 σεναρίων")
    args = parser.parse_args()

    classes = [c.strip() for c in args.classes.split(",") if c.strip()]
    if not classes:
        raise SystemExit("Δώσε τουλάχιστον ένα τμήμα με --classes.")

    # Διαβάζουμε
    if args.sheet:
        df = pd.read_excel(args.input, sheet_name=args.sheet)
    else:
        df = pd.read_excel(args.input)

    # Τρέχουμε Βήμα 1
    out = step1_assign_teacher_children(df, classes=classes, random_seed=args.seed)

    # Γράφουμε
    with pd.ExcelWriter(args.output, engine="xlsxwriter") as writer:
        out.to_excel(writer, index=False)

    print(f"✔ Αποθήκευση ολοκληρώθηκε: {args.output}")


if __name__ == "__main__":
    _cli()
