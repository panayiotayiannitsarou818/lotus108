
# -*- coding: utf-8 -*-
"""
friendship_filters_fixed.py

Διορθώσεις σύμφωνα με τις απαιτήσεις σου:
1) Σωστή μέτρηση «σπασμένων» πλήρως αμοιβαίων φιλιών (χωρίς διπλομέτρηση)
2) Ασφαλής έλεγχος αμοιβαίας φιλίας (χωρίς substring matches)
3) Φιλτράρισμα σεναρίων όταν είναι >5 ώστε να προτιμούνται όσα ΔΕΝ σπάνε φιλίες.
   - Αν υπάρχουν ≥5 με 0 σπασμένες φιλίες → επέστρεψε τα 5 πρώτα
   - Αλλιώς προτίμησε πρώτα τα 0-σπασμένες και συμπλήρωσε με τα λιγότερα σπασίματα
4) Όλα τα μετρικά υπολογίζονται ΜΙΑ φορά ανά σενάριο (όχι τριπλές κλήσεις)

Σημειώσεις:
- Δουλεύει για οποιαδήποτε στήλη ανάθεσης (π.χ. 'ΠΡΟΤΕΙΝΟΜΕΝΟ_ΤΜΗΜΑ' ή 'ΒΗΜΑ1_ΣΕΝΑΡΙΟ_1' κλπ).
- Το όρισμα 'names' μπορεί να είναι η λίστα μαθητών που θες να ελέγξεις (π.χ. μόνο παιδιά εκπαιδευτικών).
"""

import re, ast
import pandas as pd

# ---------- Parsing ΦΙΛΟΙ με ασφάλεια ----------

def parse_friends_cell(x):
    """Επιστρέφει λίστα ονομάτων από κελί 'ΦΙΛΟΙ' με ασφάλεια (χωρίς substring pitfalls)."""
    if isinstance(x, list):
        return [str(s).strip() for s in x if str(s).strip()]
    if pd.isna(x):
        return []
    s = str(x).strip()
    if not s:
        return []
    # 1) Προσπάθησε να το ερμηνεύσεις ως Python list (π.χ. "['Α', 'Β']")
    try:
        v = ast.literal_eval(s)
        if isinstance(v, list):
            return [str(t).strip() for t in v if str(t).strip()]
    except Exception:
        pass
    # 2) Αλλιώς χώρισε με ασφαλές regex σε οριοθέτες
    parts = re.split(r"[,\|\;/·\n]+", s)
    return [p.strip() for p in parts if p.strip() and p.strip().lower() != "nan"]

# ---------- Ανίχνευση αμοιβαίας φιλίας ----------

def are_friends_fixed(df, name1, name2):
    """Αληθές όταν ΟΝΟΜΑ1 έχει τον ΟΝΟΜΑ2 στους 'ΦΙΛΟΙ' ΚΑΙ το αντίστροφο (πλήρως αμοιβαία)."""
    r1 = df[df["ΟΝΟΜΑ"].astype(str) == str(name1)]
    r2 = df[df["ΟΝΟΜΑ"].astype(str) == str(name2)]
    if r1.empty or r2.empty:
        return False
    f1 = parse_friends_cell(r1.iloc[0].get("ΦΙΛΟΙ", ""))
    f2 = parse_friends_cell(r2.iloc[0].get("ΦΙΛΟΙ", ""))
    # σύγκριση με exact tokens (όχι substring)
    s1 = {str(x).strip() for x in f1}
    s2 = {str(x).strip() for x in f2}
    return (str(name2).strip() in s1) and (str(name1).strip() in s2)

# ---------- Μέτρηση «σπασμένων» φιλιών χωρίς διπλομέτρηση ----------

def count_broken_friendships_fixed(df, assigned_col, names=None):
    """
    Μετρά πόσες ΠΛΗΡΩΣ αμοιβαίες φιλίες (μέσα στο 'names') «σπάνε» (δηλ. διαφορετικό τμήμα).
    Δεν διπλομετρά (ζεύγος Α-Β μετράει 1 φορά).
    """
    if names is None:
        names = df["ΟΝΟΜΑ"].astype(str).tolist()

    # Προετοίμασε map: όνομα -> τάξη (από τη στήλη assigned_col)
    asg = df.set_index("ΟΝΟΜΑ")[assigned_col].to_dict()

    broken = 0
    checked = set()  # frozenset({a,b})
    for i, a in enumerate(names):
        for b in names[i+1:]:
            pair = frozenset({a, b})
            if pair in checked:
                continue
            checked.add(pair)
            if are_friends_fixed(df, a, b):
                if asg.get(a) != asg.get(b):
                    broken += 1
    return broken

# ---------- Επιλογή top-5 σεναρίων βάσει σπασμένων φιλιών ----------

def filter_scenarios_fixed(valid_scenarios, assigned_col, names=None, top_k=5):
    """
    valid_scenarios: iterable από DataFrame (ή αντικείμενα που υποστηρίζουν df[assigned_col])
    Επιστρέφει έως top_k σενάρια, προτιμώντας:
      1) Όσα έχουν 0 σπασμένες φιλίες (αν είναι ≥top_k, κρατά τα πρώτα top_k)
      2) Αλλιώς ταξινομεί κατά αύξοντα # σπασμένων και κρατά τα πρώτα top_k
    Υπολογίζει τα «σπασμένα» ΜΙΑ φορά ανά σενάριο.
    """
    scored = []
    for scen in valid_scenarios:
        try:
            df = scen  # αναμένουμε DataFrame
            broken = count_broken_friendships_fixed(df, assigned_col, names=names)
        except Exception:
            # Αν κάτι δεν πάει καλά, θεωρούμε «χειρότερο»
            broken = float("inf")
        scored.append((broken, scen))

    # 1) Δες αν υπάρχουν αρκετά με μηδενικά σπασίματα
    zero = [s for b, s in scored if b == 0]
    if len(zero) >= top_k:
        return zero[:top_k]

    # 2) Αλλιώς, πάρε όσα έχεις με μηδέν και συμπλήρωσε με τα επόμενα καλύτερα
    scored.sort(key=lambda x: x[0])  # αύξοντα broken
    return [s for _, s in scored[:top_k]]

# ---------- Βοηθητικό: εύρεση στήλης ανάθεσης όταν δεν δίνεται ----------

def infer_assignment_column(df, preferred=None):
    """
    Βρίσκει στήλη ανάθεσης:
    - Αν δοθεί preferred και υπάρχει, τη χρησιμοποιεί
    - Αλλιώς ψάχνει για ονόματα τύπου 'ΒΗΜΑ*_ΣΕΝΑΡΙΟ_*' ή 'ΠΡΟΤΕΙΝΟΜΕΝΟ_ΤΜΗΜΑ'
    """
    if preferred and preferred in df.columns:
        return preferred
    patt = re.compile(r"^ΒΗΜΑ\d+_ΣΕΝΑΡΙΟ_\d+$", re.IGNORECASE)
    for c in df.columns:
        if patt.match(str(c)):
            return c
    if "ΠΡΟΤΕΙΝΟΜΕΝΟ_ΤΜΗΜΑ" in df.columns:
        return "ΠΡΟΤΕΙΝΟΜΕΝΟ_ΤΜΗΜΑ"
    # fallback: τελευταία στήλη
    return df.columns[-1]
