# -*- coding: utf-8 -*-
"""
Step 4 — Fully mutual groups placement (BELTIOSI, FIXED)
Change: gender_diff_max default from 3 → 4 (reject only if gender diff > 4)
"""

import itertools
from collections import defaultdict
from copy import deepcopy
import pandas as pd

# -------------------- Utilities --------------------

def is_fully_mutual(group, df):
    """Return True if every pair in 'group' are mutual friends in df['ΦΙΛΟΙ'] (list of names per row)."""
    for name in group:
        friends = set(df.loc[df['ΟΝΟΜΑ'] == name, 'ΦΙΛΟΙ'].values[0])
        for other in group:
            if other == name:
                continue
            if other not in friends:
                return False
    # also check symmetry
    for a, b in itertools.permutations(group, 2):
        fa = set(df.loc[df['ΟΝΟΜΑ'] == a, 'ΦΙΛΟΙ'].values[0])
        if b not in fa:
            return False
    return True

def create_fully_mutual_groups(df, assigned_column):
    """Build disjoint triads first, then pairs, only among unassigned students with non-empty friend lists."""
    unassigned = df[df[assigned_column].isna()].copy()
    unassigned = unassigned[unassigned['ΦΙΛΟΙ'].map(lambda x: isinstance(x, list) and len(x) > 0)]
    names = list(unassigned['ΟΝΟΜΑ'].astype(str).unique())

    used = set()
    groups = []

    # 1) triads
    for g in itertools.combinations(names, 3):
        if set(g) & used:
            continue
        if is_fully_mutual(g, df):
            groups.append(list(g))
            used |= set(g)

    # 2) pairs
    for g in itertools.combinations(names, 2):
        if set(g) & used:
            continue
        if is_fully_mutual(g, df):
            groups.append(list(g))
            used |= set(g)

    return groups

def get_group_characteristics(group, df):
    sub = df[df['ΟΝΟΜΑ'].isin(group)]
    genders = set(sub['ΦΥΛΟ'])
    lang = set(sub['ΚΑΛΗ_ΓΝΩΣΗ_ΕΛΛΗΝΙΚΩΝ'])
    if len(genders) == 1:
        gtxt = 'Αγόρια' if 'Α' in genders else 'Κορίτσια'
    else:
        gtxt = 'Μικτό Φύλο'
    if len(lang) == 1:
        ltxt = 'Καλή Γνώση' if 'Ν' in lang else 'Όχι Καλή Γνώση'
    else:
        ltxt = 'Μικτής Γνώσης'
    return f'{ltxt} ({gtxt})'

def categorize_groups(groups, df):
    cat = defaultdict(list)
    for g in groups:
        cat[get_group_characteristics(g, df)].append(g)
    return cat

# -------------------- Scoring & acceptance --------------------

def _counts_from(df, placed_dict, assigned_column, classes):
    cnt = {c: int((df[assigned_column] == c).sum()) for c in classes}
    good= {c: int(((df[assigned_column] == c) & (df['ΚΑΛΗ_ΓΝΩΣΗ_ΕΛΛΗΝΙΚΩΝ']=='Ν')).sum()) for c in classes}
    boys= {c: int(((df[assigned_column] == c) & (df['ΦΥΛΟ']=='Α')).sum()) for c in classes}
    girls={c: int(((df[assigned_column] == c) & (df['ΦΥΛΟ']=='Κ')).sum()) for c in classes}
    # apply placed
    for g, c in placed_dict.items():
        size = len(g)
        sub = df[df['ΟΝΟΜΑ'].isin(g)]
        cnt[c]   += size
        good[c]  += int((sub['ΚΑΛΗ_ΓΝΩΣΗ_ΕΛΛΗΝΙΚΩΝ']=='Ν').sum())
        boys[c]  += int((sub['ΦΥΛΟ']=='Α').sum())
        girls[c] += int((sub['ΦΥΛΟ']=='Κ').sum())
    return cnt, good, boys, girls

def accept(cnt, good, boys, girls, cap=25, pop_diff_max=2, good_diff_max=4, gender_diff_max=4):
    """
    Accept if:
      - no class exceeds cap
      - population diff <= pop_diff_max
      - greek knowledge diff <= good_diff_max
      - boys diff <= gender_diff_max AND girls diff <= gender_diff_max
    NOTE: gender_diff_max default is 4 (reject only when diff > 4).
    """
    if any(v>cap for v in cnt.values()): return False
    if max(cnt.values()) - min(cnt.values()) > pop_diff_max: return False
    if max(good.values()) - min(good.values()) > good_diff_max: return False
    if max(boys.values()) - min(boys.values()) > gender_diff_max: return False
    if max(girls.values()) - min(girls.values()) > gender_diff_max: return False
    return True

def penalty(cnt, good, boys, girls, classes):
    # penalties only beyond (1,2,1,1)
    p  = max(0, abs(cnt[classes[0]] - cnt[classes[1]]) - 1)
    p += max(0, abs(good[classes[0]] - good[classes[1]]) - 2)
    p += max(0, abs(boys[classes[0]] - boys[classes[1]]) - 1)
    p += max(0, abs(girls[classes[0]] - girls[classes[1]]) - 1)
    return p

# -------------------- Main: improved exhaustive with strong pruning --------------------

def apply_step4_strict(df, assigned_column='ΒΗΜΑ3_ΣΕΝΑΡΙΟ_1', num_classes=2, max_results=5, max_nodes=200000):
    """
    Exhaustively enumerate placements of fully mutual groups, but with strict acceptance and pruning.
    Returns a list of tuples: (placed_dict, penalty_score)
    """
    classes = [f'Α{i+1}' for i in range(num_classes)]
    base_cnt = {c: int((df[assigned_column]==c).sum()) for c in classes}
    base_good= {c: int(((df[assigned_column]==c) & (df['ΚΑΛΗ_ΓΝΩΣΗ_ΕΛΛΗΝΙΚΩΝ']=='Ν')).sum()) for c in classes}
    base_boys= {c: int(((df[assigned_column]==c) & (df['ΦΥΛΟ']=='Α')).sum()) for c in classes}
    base_girls={c: int(((df[assigned_column]==c) & (df['ΦΥΛΟ']=='Κ')).sum()) for c in classes}

    groups = create_fully_mutual_groups(df, assigned_column)
    if not groups:
        return []

    # Heuristic order: larger & more "informative" groups first
    def gkey(g):
        sub = df[df['ΟΝΟΜΑ'].isin(g)]
        good = int((sub['ΚΑΛΗ_ΓΝΩΣΗ_ΕΛΛΗΝΙΚΩΝ']=='Ν').sum())
        boys = int((sub['ΦΥΛΟ']=='Α').sum())
        girls= int((sub['ΦΥΛΟ']=='Κ').sum())
        # prioritize: size desc, |boys-girls| desc, good desc
        return (-len(g), -abs(boys-girls), -good)
    groups = sorted(groups, key=gkey)

    results = []
    nodes = 0

    placed = {}

    def dfs(idx, cnt, good, boys, girls):
        nonlocal nodes
        nodes += 1
        if nodes > max_nodes:
            return
        # quick cap check
        if any(v>25 for v in cnt.values()):
            return

        if idx == len(groups):
            if accept(cnt, good, boys, girls):
                p = penalty(cnt, good, boys, girls, classes)
                results.append((deepcopy(placed), p))
            return

        g = groups[idx]
        sub = df[df['ΟΝΟΜΑ'].isin(g)]
        gsize = len(g)
        ggood = int((sub['ΚΑΛΗ_ΓΝΩΣΗ_ΕΛΛΗΝΙΚΩΝ']=='Ν').sum())
        gboys = int((sub['ΦΥΛΟ']=='Α').sum())
        ggirls= int((sub['ΦΥΛΟ']=='Κ').sum())

        # Try target class with lower current population first
        order = sorted(classes, key=lambda c: (cnt[c], good[c], boys[c]+girls[c]))

        for c in order:
            # simulate
            cnt[c]   += gsize
            good[c]  += ggood
            boys[c]  += gboys
            girls[c] += ggirls
            placed[tuple(g)] = c

            # fast pre-prune: if pop diff already >2 discard branch
            if (max(cnt.values()) - min(cnt.values())) <= 2:
                dfs(idx+1, cnt, good, boys, girls)

            # revert
            placed.pop(tuple(g), None)
            cnt[c]   -= gsize
            good[c]  -= ggood
            boys[c]  -= gboys
            girls[c] -= ggirls

            if len(results) >= max_results:
                return

    dfs(0, base_cnt.copy(), base_good.copy(), base_boys.copy(), base_girls.copy())

    results_sorted = sorted(results, key=lambda t: t[1])[:max_results]
    return results_sorted
