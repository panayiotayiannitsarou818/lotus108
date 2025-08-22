# -*- coding: utf-8 -*-
"""
Streamlit App - Σύστημα Ανάθεσης Μαθητών (Minimal Version)
Ελαχιστοποιημένη έκδοση χωρίς γραφήματα για γρήγορη εκτέλεση
"""

import streamlit as st
import pandas as pd
import numpy as np
import zipfile
import io
from pathlib import Path
from typing import Dict, List, Tuple, Any
import traceback

# Import των modules (θα πρέπει να είναι στον ίδιο φάκελο)
try:
    from step_1_helpers_FIXED import load_and_normalize, enumerate_all, write_outputs
    from step_2_zoiroi_idiaterotites_FIXED_v3_PATCHED import step2_apply_FIXED_v3
    from step3_amivaia_filia_FIXED import step3_run_all_from_step2
    from step4_filikoi_omades_beltiosi_FIXED import apply_step4_strict
    from step_5_ypoloipoi_mathites_FIXED_compat import apply_step5_to_all_scenarios
    from step_6_final_check_and_fix_PATCHED import apply_step6_to_step5_scenarios
    from step_7_final_score_FIXED_PATCHED import score_one_scenario_auto, pick_best_scenario
    from friendship_filters_fixed import filter_scenarios_fixed
    from statistics_generator import generate_statistics_table, export_statistics_to_excel
except ImportError as e:
    st.error(f"Σφάλμα εισαγωγής modules: {e}")
    st.error("Βεβαιωθείτε ότι όλα τα αρχεία .py είναι στον ίδιο φάκελο.")
    st.stop()

# Streamlit configuration
st.set_page_config(
    page_title="Σύστημα Ανάθεσης Μαθητών",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

def init_session_state():
    """Αρχικοποίηση session state variables"""
    if 'data' not in st.session_state:
        st.session_state.data = None
    if 'step_results' not in st.session_state:
        st.session_state.step_results = {}
    if 'current_step' not in st.session_state:
        st.session_state.current_step = 1

def load_data(uploaded_file):
    """Φόρτωση και κανονικοποίηση δεδομένων"""
    try:
        if uploaded_file.name.endswith('.xlsx'):
            df = pd.read_excel(uploaded_file)
        elif uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            st.error("Υποστηρίζονται μόνο αρχεία .xlsx και .csv")
            return None
        
        # Κανονικοποίηση στηλών
        rename_map = {}
        for col in df.columns:
            col_str = str(col).strip().upper()
            if any(x in col_str for x in ['ΟΝΟΜΑ', 'NAME', 'ΜΑΘΗΤΗΣ']):
                rename_map[col] = 'ΟΝΟΜΑ'
            elif any(x in col_str for x in ['ΦΥΛΟ', 'GENDER']):
                rename_map[col] = 'ΦΥΛΟ'
            elif 'ΓΝΩΣΗ' in col_str and 'ΕΛΛΗΝΙΚ' in col_str:
                rename_map[col] = 'ΚΑΛΗ_ΓΝΩΣΗ_ΕΛΛΗΝΙΚΩΝ'
            elif 'ΠΑΙΔΙ' in col_str and 'ΕΚΠΑΙΔΕΥΤΙΚ' in col_str:
                rename_map[col] = 'ΠΑΙΔΙ_ΕΚΠΑΙΔΕΥΤΙΚΟΥ'
            elif 'ΦΙΛΟΙ' in col_str or 'FRIEND' in col_str:
                rename_map[col] = 'ΦΙΛΟΙ'
        
        if rename_map:
            df = df.rename(columns=rename_map)
        
        # Κανονικοποίηση τιμών
        if 'ΦΥΛΟ' in df.columns:
            df['ΦΥΛΟ'] = df['ΦΥΛΟ'].astype(str).str.upper().map({'Α':'Α', 'Κ':'Κ', 'ΑΓΟΡΙ':'Α', 'ΚΟΡΙΤΣΙ':'Κ'}).fillna('Α')
        
        for col in ['ΚΑΛΗ_ΓΝΩΣΗ_ΕΛΛΗΝΙΚΩΝ', 'ΠΑΙΔΙ_ΕΚΠΑΙΔΕΥΤΙΚΟΥ']:
            if col in df.columns:
                df[col] = df[col].astype(str).str.upper().map({'ΝΑΙ':'Ν', 'ΟΧΙ':'Ο', 'YES':'Ν', 'NO':'Ο', '1':'Ν', '0':'Ο'}).fillna('Ο')
        
        return df
    except Exception as e:
        st.error(f"Σφάλμα φόρτωσης αρχείου: {e}")
        return None

def display_data_summary(df):
    """Εμφάνιση περίληψης δεδομένων"""
    st.subheader("📊 Περίληψη Δεδομένων")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Συνολικοί Μαθητές", len(df))
    with col2:
        if 'ΦΥΛΟ' in df.columns:
            boys = (df['ΦΥΛΟ'] == 'Α').sum()
            st.metric("Αγόρια", boys)
    with col3:
        if 'ΦΥΛΟ' in df.columns:
            girls = (df['ΦΥΛΟ'] == 'Κ').sum()
            st.metric("Κορίτσια", girls)
    with col4:
        if 'ΠΑΙΔΙ_ΕΚΠΑΙΔΕΥΤΙΚΟΥ' in df.columns:
            teachers_kids = (df['ΠΑΙΔΙ_ΕΚΠΑΙΔΕΥΤΙΚΟΥ'] == 'Ν').sum()
            st.metric("Παιδιά Εκπαιδευτικών", teachers_kids)
    
    # Απλός πίνακας κατανομής φύλου
    if 'ΦΥΛΟ' in df.columns:
        st.write("**Κατανομή Φύλου:**")
        gender_data = pd.DataFrame({
            'Φύλο': ['Αγόρια', 'Κορίτσια'],
            'Πλήθος': [boys, girls],
            'Ποσοστό': [f"{boys/len(df)*100:.1f}%", f"{girls/len(df)*100:.1f}%"]
        })
        st.dataframe(gender_data, use_container_width=True)

def display_scenario_statistics(df, scenario_col, scenario_name):
    """Εμφάνιση στατιστικών για ένα σενάριο"""
    try:
        # Φιλτράρισμα μόνο των τοποθετημένων μαθητών
        df_assigned = df[df[scenario_col].notna()].copy()
        df_assigned['ΤΜΗΜΑ'] = df_assigned[scenario_col]
        
        # Δημιουργία στατιστικών
        stats_df = generate_statistics_table(df_assigned)
        
        st.subheader(f"📊 Στατιστικά {scenario_name}")
        st.dataframe(stats_df, use_container_width=True)
        
        return stats_df
        
    except Exception as e:
        st.error(f"Σφάλμα στα στατιστικά {scenario_name}: {e}")
        return None

def run_step1(df):
    """Εκτέλεση Βήματος 1 - Παιδιά Εκπαιδευτικών"""
    st.subheader("🎯 Βήμα 1: Ανάθεση Παιδιών Εκπαιδευτικών")
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    try:
        status_text.text("Φόρτωση και κανονικοποίηση δεδομένων...")
        progress_bar.progress(25)
        
        # Απαρίθμηση σεναρίων
        status_text.text("Δημιουργία σεναρίων...")
        progress_bar.progress(50)
        
        teacher_kids = df[df['ΠΑΙΔΙ_ΕΚΠΑΙΔΕΥΤΙΚΟΥ'] == 'Ν']
        if len(teacher_kids) <= 12:
            sols, names = enumerate_all(df, top_k=3)
        else:
            st.warning("Πολλά παιδιά εκπαιδευτικών (>12). Χρήση greedy approach.")
            sols, names = enumerate_all(df, top_k=3)  # fallback
        
        status_text.text("Εγγραφή αποτελεσμάτων...")
        progress_bar.progress(75)
        
        # Δημιουργία DataFrames για κάθε σενάριο
        step1_results = {}
        for i, (score, assign_map, state) in enumerate(sols, 1):
            df_scenario = df.copy()
            col_name = f"ΒΗΜΑ1_ΣΕΝΑΡΙΟ_{i}"
            df_scenario[col_name] = np.nan
            
            # Ανάθεση παιδιών εκπαιδευτικών
            for name, section in assign_map.items():
                mask = df_scenario['ΟΝΟΜΑ'] == name
                df_scenario.loc[mask, col_name] = section
            
            step1_results[f"ΣΕΝΑΡΙΟ_{i}"] = {
                'df': df_scenario,
                'score': score,
                'assignments': assign_map,
                'state': state,
                'column': col_name
            }
        
        progress_bar.progress(100)
        status_text.text("✅ Βήμα 1 ολοκληρώθηκε επιτυχώς!")
        
        # Εμφάνιση αποτελεσμάτων
        st.success(f"Δημιουργήθηκαν {len(step1_results)} σενάρια")
        
        # Πίνακας σύγκρισης
        comparison_data = []
        for name, result in step1_results.items():
            state = result['state']
            comparison_data.append({
                'Σενάριο': name,
                'Score': result['score'],
                'Α1 Σύνολο': state['Α1']['cnt'],
                'Α2 Σύνολο': state['Α2']['cnt'],
                'Α1 Αγόρια': state['Α1']['boys'],
                'Α2 Αγόρια': state['Α2']['boys'],
                'Α1 Κορίτσια': state['Α1']['girls'],
                'Α2 Κορίτσια': state['Α2']['girls']
            })
        
        comparison_df = pd.DataFrame(comparison_data)
        st.dataframe(comparison_df, use_container_width=True)
        
        # Στατιστικά για κάθε σενάριο
        with st.expander("📈 Αναλυτικά Στατιστικά Σεναρίων"):
            for name, result in step1_results.items():
                display_scenario_statistics(result['df'], result['column'], name)
        
        return step1_results
        
    except Exception as e:
        st.error(f"Σφάλμα στο Βήμα 1: {e}")
        st.code(traceback.format_exc())
        return None

def run_all_steps(step1_results):
    """Εκτέλεση όλων των υπόλοιπων βημάτων σε μία φάση"""
    st.subheader("🚀 Εκτέλεση Βημάτων 2-7")
    
    final_results = {}
    
    for scenario_name, step1_data in step1_results.items():
        st.write(f"**Επεξεργασία {scenario_name}**")
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        try:
            df = step1_data['df']
            step1_col = step1_data['column']
            
            # Βήμα 2
            status_text.text("Βήμα 2: Ζωηροί & Ιδιαιτερότητες...")
            progress_bar.progress(15)
            
            step2_results = step2_apply_FIXED_v3(
                df, num_classes=2, step1_col_name=step1_col, max_results=1
            )
            
            if step2_results:
                df = step2_results[0][1]
                step2_col = step2_results[0][1].columns[-1]
            else:
                step2_col = step1_col
            
            # Βήμα 3
            status_text.text("Βήμα 3: Αμοιβαίες φιλίες...")
            progress_bar.progress(30)
            
            from step_3_helpers_FIXED import apply_step3_on_sheet
from steps_export import create_steps_excel_download_ui

            df, step3_metrics = apply_step3_on_sheet(df, step2_col, num_classes=2)
            step3_col = step2_col.replace('ΒΗΜΑ2', 'ΒΗΜΑ3')
            
            # Βήμα 4
            status_text.text("Βήμα 4: Φιλικές ομάδες...")
            progress_bar.progress(45)
            
            step4_results = apply_step4_strict(
                df, assigned_column=step3_col, num_classes=2, max_results=1, max_nodes=20000
            )
            
            if step4_results:
                best_placement, best_penalty = step4_results[0]
                step4_col = step3_col.replace('ΒΗΜΑ3', 'ΒΗΜΑ4')
                df[step4_col] = df[step3_col]
                
                # Εφαρμογή ανάθεσης ομάδων
                for group, class_assigned in best_placement.items():
                    for student in group:
                        mask = df['ΟΝΟΜΑ'] == student
                        df.loc[mask, step4_col] = class_assigned
            else:
                step4_col = step3_col
            
            # Βήμα 5
            status_text.text("Βήμα 5: Υπόλοιποι μαθητές...")
            progress_bar.progress(60)
            
            df_step5, penalty5 = apply_step5_to_all_scenarios(
                {scenario_name: df}, step4_col, num_classes=2
            )
            if df_step5 is not None:
                df = df_step5
            
            # Βήμα 6
            status_text.text("Βήμα 6: Τελικός έλεγχος...")
            progress_bar.progress(75)
            
            step5_col = step4_col.replace('ΒΗΜΑ4', 'ΒΗΜΑ5')
            if step5_col not in df.columns:
                df[step5_col] = df[step4_col]
            
            step6_output = apply_step6_to_step5_scenarios(
                {scenario_name: df}, class_col=step5_col
            )
            
            if scenario_name in step6_output:
                df_final = step6_output[scenario_name]['df']
                summary6 = step6_output[scenario_name]['summary']
            else:
                df_final = df
                summary6 = {}
            
            # Βήμα 7
            status_text.text("Βήμα 7: Τελικό σκορ...")
            progress_bar.progress(90)
            
            step6_col = 'ΒΗΜΑ6_ΤΜΗΜΑ'
            if step6_col not in df_final.columns:
                step6_col = step5_col
            
            final_score = score_one_scenario_auto(df_final, step6_col)
            
            progress_bar.progress(100)
            status_text.text("✅ Ολοκληρώθηκε επιτυχώς!")
            
            final_results[scenario_name] = {
                'df': df_final,
                'step3_metrics': step3_metrics,
                'step6_summary': summary6,
                'final_score': final_score,
                'final_column': step6_col
            }
            
            st.success(f"✅ {scenario_name}: Τελικό Score = {final_score['total_score']}")
            
        except Exception as e:
            st.error(f"Σφάλμα στο {scenario_name}: {e}")
            st.code(traceback.format_exc())
    
    return final_results

def display_final_results(final_results):
    """Εμφάνιση τελικών αποτελεσμάτων"""
    st.subheader("🏆 Τελικά Αποτελέσματα")
    
    # Σύγκριση σεναρίων
    comparison_data = []
    for name, result in final_results.items():
        score = result['final_score']
        comparison_data.append({
            'Σενάριο': name,
            'Συνολικό Score': score['total_score'],
            'Διαφορά Πληθυσμού': score['diff_population'],
            'Διαφορά Φύλου': score['diff_gender'],
            'Διαφορά Γνώσης': score['diff_greek'],
            'Σπασμένες Φιλίες': score['broken_friendships']
        })
    
    comparison_df = pd.DataFrame(comparison_data)
    st.dataframe(comparison_df, use_container_width=True)
    
    # Καλύτερο σενάριο
    best_scenario = min(comparison_data, key=lambda x: x['Συνολικό Score'])
    st.success(f"🥇 **Καλύτερο Σενάριο:** {best_scenario['Σενάριο']} (Score: {best_scenario['Συνολικό Score']})")
    
    # Αναλυτικά στατιστικά
    with st.expander("📊 Αναλυτικά Στατιστικά Τελικών Σεναρίων"):
        for name, result in final_results.items():
            display_scenario_statistics(result['df'], result['final_column'], f"Τελικό {name}")
    
    return comparison_df

def create_download_package(final_results):
    """Δημιουργία πακέτου download"""
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for scenario_name, result in final_results.items():
            # DataFrame σε Excel
            excel_buffer = io.BytesIO()
            with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                # Κύρια δεδομένα
                result['df'].to_excel(writer, sheet_name='Αποτελέσματα', index=False)
                
                # Στατιστικά
                try:
                    df_assigned = result['df'][result['df'][result['final_column']].notna()].copy()
                    df_assigned['ΤΜΗΜΑ'] = df_assigned[result['final_column']]
                    stats_df = generate_statistics_table(df_assigned)
                    stats_df.to_excel(writer, sheet_name='Στατιστικά', index=True)
                except Exception:
                    pass
                
                # Μετρικές
                if 'final_score' in result:
                    metrics_df = pd.DataFrame([result['final_score']])
                    metrics_df.to_excel(writer, sheet_name='Μετρικές', index=False)
            
            zip_file.writestr(
                f"{scenario_name}_Πλήρη_Αποτελέσματα.xlsx",
                excel_buffer.getvalue()
            )
        
        # Συνολικός πίνακας σύγκρισης
        summary_buffer = io.BytesIO()
        comparison_data = []
        for name, result in final_results.items():
            if 'final_score' in result:
                score = result['final_score']
                comparison_data.append({
                    'Σενάριο': name,
                    'Συνολικό Score': score['total_score'],
                    'Διαφορά Πληθυσμού': score['diff_population'],
                    'Διαφορά Φύλου': score['diff_gender'],
                    'Διαφορά Γνώσης': score['diff_greek'],
                    'Σπασμένες Φιλίες': score['broken_friendships']
                })
        
        if comparison_data:
            summary_df = pd.DataFrame(comparison_data)
            with pd.ExcelWriter(summary_buffer, engine='openpyxl') as writer:
                summary_df.to_excel(writer, sheet_name='Σύγκριση_Σεναρίων', index=False)
            zip_file.writestr("ΣΥΝΟΨΗ_Σύγκριση_Σεναρίων.xlsx", summary_buffer.getvalue())
    
    return zip_buffer.getvalue()

def main():
    """Κύρια συνάρτηση εφαρμογής"""
    init_session_state()
    
    st.title("🎓 Σύστημα Ανάθεσης Μαθητών σε Τμήματα")
    st.markdown("*Απλουστευμένη έκδοση - Χωρίς γραφήματα*")
    st.markdown("---")
    
    # Sidebar
    st.sidebar.title("📋 Μενού Πλοήγησης")
    
    # Upload αρχείου
    st.sidebar.subheader("📁 Φόρτωση Δεδομένων")
    uploaded_file = st.sidebar.file_uploader(
        "Επιλέξτε αρχείο Excel ή CSV",
        type=['xlsx', 'csv'],
        help="Το αρχείο πρέπει να περιέχει στήλες: ΟΝΟΜΑ, ΦΥΛΟ, ΚΑΛΗ_ΓΝΩΣΗ_ΕΛΛΗΝΙΚΩΝ, ΠΑΙΔΙ_ΕΚΠΑΙΔΕΥΤΙΚΟΥ"
    )
    
    if uploaded_file is not None:
        # Φόρτωση δεδομένων
        if st.session_state.data is None:
            with st.spinner("Φόρτωση δεδομένων..."):
                st.session_state.data = load_data(uploaded_file)
        
        if st.session_state.data is not None:
            # Εμφάνιση περίληψης
            display_data_summary(st.session_state.data)
            
            # Επιλογή βημάτων
            st.sidebar.subheader("🔄 Εκτέλεση Βημάτων")
            
            # Βήμα 1
            if st.sidebar.button("▶️ Εκτέλεση Βήματος 1", disabled=st.session_state.current_step > 1):
                with st.spinner("Εκτέλεση Βήματος 1..."):
                    result = run_step1(st.session_state.data)
                    if result:
                        st.session_state.step_results['step1'] = result
                        st.session_state.current_step = 2
            
            # Βήματα 2-7 (όλα μαζί)
            if st.sidebar.button("▶️ Εκτέλεση Βημάτων 2-7", disabled=st.session_state.current_step != 2):
                if 'step1' in st.session_state.step_results:
                    with st.spinner("Εκτέλεση Βημάτων 2-7... (Μπορεί να πάρει λίγη ώρα)"):
                        result = run_all_steps(st.session_state.step_results['step1'])
                        if result:
                            st.session_state.step_results['final'] = result
                            st.session_state.current_step = 3
            
            # Εμφάνιση τελικών αποτελεσμάτων
            if 'final' in st.session_state.step_results:
                comparison_df = display_final_results(st.session_state.step_results['final'])
                
                # Download
                st.sidebar.subheader("💾 Λήψη Αποτελεσμάτων")
                if st.sidebar.button("📥 Δημιουργία Πακέτου Λήψης"):
                    with st.spinner("Δημιουργία αρχείων..."):
                        zip_data = create_download_package(st.session_state.step_results['final'])
                        st.sidebar.download_button(
                            label="⬇️ Λήψη Πακέτου",
                            data=zip_data,
                            file_name="Αποτελέσματα_Ανάθεσης.zip",
                            mime="application/zip"
                        )
            
            # Reset
            if st.sidebar.button("🔄 Επαναφορά"):
                st.session_state.clear()
                st.experimental_rerun()
    
    else:
        st.info("👆 Παρακαλώ ανεβάστε ένα αρχείο Excel ή CSV για να ξεκινήσετε")
        
        # Οδηγίες χρήσης
        with st.expander("📖 Οδηγίες Χρήσης"):
            st.markdown("""
            ### Προετοιμασία Αρχείου:
            Το αρχείο Excel/CSV πρέπει να περιέχει τις εξής στήλες:
            - **ΟΝΟΜΑ**: Ονοματεπώνυμο μαθητή
            - **ΦΥΛΟ**: Α (Αγόρι) ή Κ (Κορίτσι)
            - **ΚΑΛΗ_ΓΝΩΣΗ_ΕΛΛΗΝΙΚΩΝ**: Ν (Ναι) ή Ο (Όχι)
            - **ΠΑΙΔΙ_ΕΚΠΑΙΔΕΥΤΙΚΟΥ**: Ν (Ναι) ή Ο (Όχι)
            - **ΦΙΛΟΙ**: Λίστα φίλων (προαιρετικό)
            - **ΖΩΗΡΟΣ**: Ν/Ο (προαιρετικό)
            - **ΙΔΙΑΙΤΕΡΟΤΗΤΑ**: Ν/Ο (προαιρετικό)
            
            ### Βήματα Εκτέλεσης:
            1. **Βήμα 1**: Ανάθεση παιδιών εκπαιδευτικών
            2. **Βήματα 2-7**: Αυτόματη εκτέλεση όλων των υπόλοιπων βημάτων
            3. **Λήψη**: Download ZIP με όλα τα αποτελέσματα
            """)

if __name__ == "__main__":
    main()

# --- Export Excel: Βήματα 1–6 ανά Σενάριο ---
try:
    import streamlit as st
    if 'step_results' in st.session_state:
        create_steps_excel_download_ui(st.session_state.step_results)
except Exception:
    pass
