
# steps_export.py
# --------------------------------------------------------------
# Drop-in helper για λήψη Excel με ΒΗΜΑΤΑ 1–6 ανά Σενάριο.
# Περιλαμβάνει:
#   - create_steps_excel_file(final_results: dict) -> bytes
#   - create_steps_excel_download_ui(step_results: dict) -> None
# --------------------------------------------------------------

from __future__ import annotations
import io
from typing import Dict, Any
import pandas as pd

try:
    import streamlit as st  # μόνο για το UI helper
except Exception:
    st = None

BASE_COLS = [
    "ΟΝΟΜΑ","ΦΥΛΟ","ΠΑΙΔΙ_ΕΚΠΑΙΔΕΥΤΙΚΟΥ","ΖΩΗΡΟΣ","ΙΔΙΑΙΤΕΡΟΤΗΤΑ",
    "ΚΑΛΗ_ΓΝΩΣΗ_ΕΛΛΗΝΙΚΩΝ","ΦΙΛΟΙ","ΣΥΓΚΡΟΥΣΗ","ΠΡΟΤΕΙΝΟΜΕΝΟ_ΤΜΗΜΑ","ΤΜΗΜΑ"
]

def _scenario_number(scenario_name: str) -> str:
    digits = "".join(ch for ch in scenario_name if ch.isdigit())
    return digits or "1"

def _ensure_alias_step6(df: pd.DataFrame, scen_num: str, final_col: str | None) -> pd.DataFrame:
    df = df.copy()
    alias6 = f"ΒΗΜΑ6_ΣΕΝΑΡΙΟ_{scen_num}"
    if final_col and final_col in df.columns and alias6 not in df.columns:
        df[alias6] = df[final_col]
    return df

def create_steps_excel_file(final_results: Dict[str, Dict[str, Any]]) -> bytes:
    '''
    Δημιουργεί Excel με ένα sheet ανά ΣΕΝΑΡΙΟ.
    Κάθε sheet έχει: βασικές στήλες + ΒΗΜΑ1_ΣΕΝΑΡΙΟ_Ν ... ΒΗΜΑ6_ΣΕΝΑΡΙΟ_Ν.
    Αν δεν υπάρχει ρητά η ΒΗΜΑ6_ΣΕΝΑΡΙΟ_Ν, δημιουργείται ως alias από την
    τελική στήλη (final_column) του αντίστοιχου σεναρίου.
    '''
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        used_sheet_names = set()
        for scenario_key, payload in final_results.items():
            if not isinstance(payload, dict) or "df" not in payload:
                # Αγνόησε μη αναμενόμενη δομή
                continue

            scen_num = _scenario_number(str(scenario_key))
            df = payload["df"].copy()
            final_col = payload.get("final_column")

            # Δημιούργησε/εξασφάλισε alias για ΒΗΜΑ6_ΣΕΝΑΡΙΟ_Ν
            df = _ensure_alias_step6(df, scen_num, final_col)

            # Στήσιμο σωστής σειράς στηλών
            out_cols = [c for c in BASE_COLS if c in df.columns]
            for step in range(1, 7):
                col = f"ΒΗΜΑ{step}_ΣΕΝΑΡΙΟ_{scen_num}"
                if col in df.columns and col not in out_cols:
                    out_cols.append(col)

            if not out_cols:
                out_cols = df.columns.tolist()

            # Όνομα φύλλου (μοναδικό)
            sheet_name = f"ΣΕΝΑΡΙΟ_{scen_num}"
            ix = 2
            while sheet_name in used_sheet_names:
                sheet_name = f"ΣΕΝΑΡΙΟ_{scen_num} ({ix})"
                ix += 1
            used_sheet_names.add(sheet_name)

            df[out_cols].to_excel(writer, sheet_name=sheet_name, index=False)

    return buffer.getvalue()

def create_steps_excel_download_ui(step_results: Dict[str, Any]) -> None:
    '''
    Sidebar UI κουμπί για λήψη του Excel.
    Περιμένει δομή st.session_state.step_results["final"] == dict με
    {scenario_name: {"df": DataFrame, "final_column": str, ...}, ...}
    '''
    if st is None:
        raise RuntimeError("Το Streamlit δεν είναι διαθέσιμο. Εισάγετε/τρέξτε σε περιβάλλον Streamlit.")
    if not isinstance(step_results, dict) or "final" not in step_results or not step_results["final"]:
        st.sidebar.info("Δεν υπάρχουν τελικά αποτελέσματα σεναρίων για εξαγωγή (βήματα 1–6).")
        return

    st.sidebar.subheader("💾 Λήψη Αποτελεσμάτων")
    if st.sidebar.button("📥 Excel: Βήματα 1–6 (ανά Σενάριο)"):
        with st.spinner("Ετοιμάζω το Excel..."):
            xlsx_bytes = create_steps_excel_file(step_results["final"])
        st.sidebar.download_button(
            label="⬇️ Λήψη Excel Βημάτων",
            data=xlsx_bytes,
            file_name="ΒΗΜΑΤΑ_1-6_ΑΝΑ_ΣΕΝΑΡΙΟ.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
