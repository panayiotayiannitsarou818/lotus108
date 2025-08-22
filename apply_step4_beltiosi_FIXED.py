# -*- coding: utf-8 -*-
"""
Driver (BELTIOSI, FIXED import)
Same as your apply_step4_beltiosi, but imports the FIXED module.
"""
import pandas as pd, math, re
from pathlib import Path
from step4_filikoi_omades_beltiosi_FIXED import apply_step4_strict
import zipfile

src = Path("/mnt/data/VIMA3_Scenarios.xlsx")
xls = pd.ExcelFile(src)

def infer_col_and_classes(df, preferred):
    col = preferred if preferred in df.columns else None
    if col is None:
        cand = [c for c in df.columns if str(c).startswith("ΒΗΜΑ3_ΣΕΝΑΡΙΟ_")]
        col = cand[0] if cand else df.columns[-1]
    vals = df[col].dropna().astype(str).unique().tolist()
    classes = sorted([v for v in vals if re.match(r"^Α\d+$", v)])
    if not classes:
        n = max(2, math.ceil(len(df)/25))
        classes = [f"Α{i+1}" for i in range(n)]
    return col, classes

def apply_assignment(df3, step3_col, placement_dict):
    col4 = step3_col.replace("ΒΗΜΑ3","ΒΗΜΑ4")
    out = df3.copy()
    out[col4] = out[step3_col]
    name2cls = {name: cls for g, cls in placement_dict.items() for name in g}
    mask = out[step3_col].isna() & out["ΟΝΟΜΑ"].astype(str).isin(name2cls.keys())
    out.loc[mask, col4] = out.loc[mask, "ΟΝΟΜΑ"].map(name2cls)
    return out, col4

out_xlsx = Path("/mnt/data/VIMA4_Scenarios_BELTIOSI_FIXED.xlsx")
out_cmp  = Path("/mnt/data/VIMA4_Comparison_Tables_BELTIOSI_FIXED.xlsx")

summary_rows = []

with pd.ExcelWriter(out_xlsx, engine="openpyxl") as writer_steps, \
     pd.ExcelWriter(out_cmp,  engine="openpyxl") as writer_cmp:

    for i in (1,2,3):
        sheet = f"ΒΗΜΑ3_ΣΕΝΑΡΙΟ_{i}"
        if sheet not in xls.sheet_names:
            continue
        df3 = pd.read_excel(src, sheet_name=sheet)
        step3_col, classes = infer_col_and_classes(df3, sheet)
        results = apply_step4_strict(df3, assigned_column=step3_col, num_classes=len(classes), max_results=5, max_nodes=120000)
        if results:
            (best_placement, best_penalty) = results[0]
            best_df, best_col = apply_assignment(df3, step3_col, best_placement)
            best_df.to_excel(writer_steps, index=False, sheet_name=f"ΒΗΜΑ4_ΣΕΝΑΡΙΟ_{i}_BEST")
            assigned = best_df[~best_df[best_col].isna()].copy()
            classes_best = sorted(assigned[best_col].dropna().astype(str).unique())
            lbl = {c: f"Τμήμα {k+1}" for k,c in enumerate(classes_best)}
            rows=[]
            for c in classes_best:
                sub = assigned[assigned[best_col].astype(str)==c]
                rows.append({"ΤΜΗΜΑ": lbl[c],
                             "ΑΓΟΡΙΑ": int((sub["ΦΥΛΟ"]=="Α").sum()),
                             "ΚΟΡΙΤΣΙΑ": int((sub["ΦΥΛΟ"]=="Κ").sum()),
                             "ΓΝΩΣΗ ΕΛΛ. (Ν)": int((sub["ΚΑΛΗ_ΓΝΩΣΗ_ΕΛΛΗΝΙΚΩΝ"]=="Ν").sum()),
                             "ΣΥΝΟΛΟ": len(sub)})
            pd.DataFrame(rows).to_excel(writer_cmp, index=False, sheet_name=f"S{i}_Σύγκριση_BEST")
        else:
            base = df3.copy()
            base[step3_col.replace("ΒΗΜΑ3","ΒΗΜΑ4")] = base[step3_col]
            base.to_excel(writer_steps, index=False, sheet_name=f"ΒΗΜΑ4_ΣΕΝΑΡΙΟ_{i}_BEST")

# zip bundle
zip_path = Path("/mnt/data/VIMA4_BELTIOSI_FIXED_bundle.zip")
with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
    z.write(out_xlsx, arcname=out_xlsx.name)
    z.write(out_cmp,  arcname=out_cmp.name)

print(out_xlsx.as_posix())
print(out_cmp.as_posix())
print(zip_path.as_posix())
