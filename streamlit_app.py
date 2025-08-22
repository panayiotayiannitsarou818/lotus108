# -*- coding: utf-8 -*-
"""
Streamlit App - Σύστημα Ανάθεσης Μαθητών σε Τμήματα
Ολοκληρωμένη εφαρμογή για τα 7 βήματα ανάθεσης
"""

import streamlit as st
import pandas as pd
import numpy as np
import zipfile
import io
import tempfile
import os
from pathlib import Path
from typing import Dict, List, Tuple, Any
import traceback

# Προαιρετικά imports για γραφήματα
try:
    import plotly.express as px
    import plotly.graph_objects as go
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False
    st.warning("⚠️ Plotly δεν είναι διαθέσιμο. Τα γραφήματα θα είναι απενεργοποιημένα.")

# Εναλλακτικά γραφήματα με matplotlib
try:
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

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
    from steps_export import create_steps_excel_download_ui
except ImportError as e:
    st.error(f"Σφάλμα εισαγωγής modules: {e}")
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

def display_scenario_statistics(df, scenario_col, scenario_name):
    """Εμφάνιση στατιστικών για ένα σενάριο"""
    try:
        # Έλεγχος ότι η στήλη υπάρχει
        if scenario_col not in df.columns:
            st.warning(f"Η στήλη {scenario_col} δεν βρέθηκε στα δεδομένα")
            return None
            
        # Φιλτράρισμα μόνο των τοποθετημένων μαθητών
        df_assigned = df[df[scenario_col].notna()].copy()
        
        if len(df_assigned) == 0:
            st.warning(f"Δεν βρέθηκαν τοποθετημένοι μαθητές στο {scenario_name}")
            return None
            
        df_assigned['ΤΜΗΜΑ'] = df_assigned[scenario_col]
        
        # Έλεγχος ότι το statistics_generator module είναι διαθέσιμο
        try:
            from statistics_generator import generate_statistics_table
        except ImportError:
            st.error("Το module statistics_generator δεν είναι διαθέσιμο")
            return None
        
        # Δημιουργία στατιστικών
        stats_df = generate_statistics_table(df_assigned)
        
        st.subheader(f"📊 Στατιστικά {scenario_name}")
        st.dataframe(stats_df, use_container_width=True)
        
        # Γραφήματα αν είναι διαθέσιμα και υπάρχουν δεδομένα
        if len(stats_df) > 0:
            col1, col2 = st.columns(2)
            
            with col1:
                # Γράφημα πληθυσμού
                if PLOTLY_AVAILABLE:
                    try:
                        fig_pop = px.bar(
                            x=stats_df.index, 
                            y=stats_df['ΣΥΝΟΛΟ'],
                            title=f"{scenario_name} - Πληθυσμός ανά Τμήμα"
                        )
                        st.plotly_chart(fig_pop, use_container_width=True)
                    except Exception as e:
                        st.warning(f"Σφάλμα γραφήματος plotly: {e}")
                        # Fallback σε πίνακα
                        pop_data = pd.DataFrame({
                            'Τμήμα': stats_df.index,
                            'Πληθυσμός': stats_df['ΣΥΝΟΛΟ']
                        })
                        st.dataframe(pop_data, use_container_width=True)
                elif MATPLOTLIB_AVAILABLE:
                    try:
                        import matplotlib.pyplot as plt
                        fig, ax = plt.subplots()
                        ax.bar(stats_df.index, stats_df['ΣΥΝΟΛΟ'])
                        ax.set_title(f"{scenario_name} - Πληθυσμός ανά Τμήμα")
                        ax.set_xlabel("Τμήμα")
                        ax.set_ylabel("Πληθυσμός")
                        st.pyplot(fig)
                        plt.close(fig)  # Απελευθέρωση μνήμης
                    except Exception as e:
                        st.warning(f"Σφάλμα γραφήματος matplotlib: {e}")
                        # Fallback σε πίνακα
                        pop_data = pd.DataFrame({
                            'Τμήμα': stats_df.index,
                            'Πληθυσμός': stats_df['ΣΥΝΟΛΟ']
                        })
                        st.dataframe(pop_data, use_container_width=True)
                else:
                    st.write("**Πληθυσμός ανά Τμήμα:**")
                    pop_data = pd.DataFrame({
                        'Τμήμα': stats_df.index,
                        'Πληθυσμός': stats_df['ΣΥΝΟΛΟ']
                    })
                    st.dataframe(pop_data, use_container_width=True)
            
            with col2:
                # Γράφημα φύλου
                if PLOTLY_AVAILABLE:
                    try:
                        fig_gender = go.Figure()
                        fig_gender.add_trace(go.Bar(name='Αγόρια', x=stats_df.index, y=stats_df['ΑΓΟΡΙΑ']))
                        fig_gender.add_trace(go.Bar(name='Κορίτσια', x=stats_df.index, y=stats_df['ΚΟΡΙΤΣΙΑ']))
                        fig_gender.update_layout(
                            title=f"{scenario_name} - Κατανομή Φύλου",
                            barmode='group'
                        )
                        st.plotly_chart(fig_gender, use_container_width=True)
                    except Exception as e:
                        st.warning(f"Σφάλμα γραφήματος φύλου: {e}")
                        # Fallback σε πίνακα
                        gender_data = pd.DataFrame({
                            'Τμήμα': stats_df.index,
                            'Αγόρια': stats_df['ΑΓΟΡΙΑ'],
                            'Κορίτσια': stats_df['ΚΟΡΙΤΣΙΑ']
                        })
                        st.dataframe(gender_data, use_container_width=True)
                elif MATPLOTLIB_AVAILABLE:
                    try:
                        import matplotlib.pyplot as plt
                        fig, ax = plt.subplots()
                        x = np.arange(len(stats_df.index))
                        width = 0.35
                        ax.bar(x - width/2, stats_df['ΑΓΟΡΙΑ'], width, label='Αγόρια')
                        ax.bar(x + width/2, stats_df['ΚΟΡΙΤΣΙΑ'], width, label='Κορίτσια')
                        ax.set_title(f"{scenario_name} - Κατανομή Φύλου")
                        ax.set_xlabel("Τμήμα")
                        ax.set_ylabel("Πλήθος")
                        ax.set_xticks(x)
                        ax.set_xticklabels(stats_df.index)
                        ax.legend()
                        st.pyplot(fig)
                        plt.close(fig)  # Απελευθέρωση μνήμης
                    except Exception as e:
                        st.warning(f"Σφάλμα γραφήματος matplotlib: {e}")
                        # Fallback σε πίνακα
                        gender_data = pd.DataFrame({
                            'Τμήμα': stats_df.index,
                            'Αγόρια': stats_df['ΑΓΟΡΙΑ'],
                            'Κορίτσια': stats_df['ΚΟΡΙΤΣΙΑ']
                        })
                        st.dataframe(gender_data, use_container_width=True)
                else:
                    st.write("**Κατανομή Φύλου:**")
                    gender_data = pd.DataFrame({
                        'Τμήμα': stats_df.index,
                        'Αγόρια': stats_df['ΑΓΟΡΙΑ'],
                        'Κορίτσια': stats_df['ΚΟΡΙΤΣΙΑ']
                    })
                    st.dataframe(gender_data, use_container_width=True)
        
        return stats_df
        
    except Exception as e:
        st.error(f"Σφάλμα στα στατιστικά {scenario_name}: {e}")
        st.code(traceback.format_exc())
        return None
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
    
    # Γράφημα κατανομής φύλου
    if 'ΦΥΛΟ' in df.columns:
        fig = px.pie(
            values=[boys, girls], 
            names=['Αγόρια', 'Κορίτσια'],
            title="Κατανομή Φύλου"
        )
        st.plotly_chart(fig, use_container_width=True)

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
        st.subheader("📈 Αναλυτικά Στατιστικά Σεναρίων")
        for name, result in step1_results.items():
            display_scenario_statistics(result['df'], result['column'], name)
        
        return step1_results
        
    except Exception as e:
        st.error(f"Σφάλμα στο Βήμα 1: {e}")
        st.code(traceback.format_exc())
        return None

def run_step2(step1_results):
    """Εκτέλεση Βήματος 2 - Ζωηροί & Ιδιαιτερότητες"""
    st.subheader("⚡ Βήμα 2: Ανάθεση Ζωηρών & Ιδιαιτεροτήτων")
    
    step2_results = {}
    
    for scenario_name, step1_data in step1_results.items():
        st.write(f"**Επεξεργασία {scenario_name}**")
        
        progress_bar = st.progress(0)
        
        try:
            df = step1_data['df']
            step1_col = step1_data['column']
            
            progress_bar.progress(50)
            
            # Εκτέλεση Step 2
            results = step2_apply_FIXED_v3(
                df, 
                num_classes=2, 
                step1_col_name=step1_col,
                max_results=5
            )
            
            progress_bar.progress(100)
            
            if results:
                # Επιλογή καλύτερου αποτελέσματος
                best_result = results[0]  # Το πρώτο είναι συνήθως το καλύτερο
                step2_results[scenario_name] = {
                    'df': best_result[1],
                    'metrics': best_result[2],
                    'column': best_result[1].columns[-1]  # Η νέα στήλη
                }
                
                st.success(f"✅ {scenario_name}: {len(results)} αποτελέσματα")
                st.json(best_result[2])
            else:
                st.warning(f"⚠️ {scenario_name}: Δεν βρέθηκαν λύσεις")
                
        except Exception as e:
            st.error(f"Σφάλμα στο {scenario_name}: {e}")
    
    return step2_results

def run_step3(step2_results):
    """Εκτέλεση Βήματος 3 - Αμοιβαία Φιλία"""
    st.subheader("👫 Βήμα 3: Ανάθεση Αμοιβαίων Φιλιών")
    
    step3_results = {}
    
    for scenario_name, step2_data in step2_results.items():
        st.write(f"**Επεξεργασία {scenario_name}**")
        
        try:
            df = step2_data['df']
            step2_col = step2_data['column']
            
            # Προσομοίωση Step 3 (χρήση του υπάρχοντος module)
            from step_3_helpers_FIXED import apply_step3_on_sheet
            

            df_step3, metrics = apply_step3_on_sheet(df, step2_col, num_classes=2)
            
            step3_results[scenario_name] = {
                'df': df_step3,
                'metrics': metrics,
                'column': step2_col.replace('ΒΗΜΑ2', 'ΒΗΜΑ3')
            }
            
            st.success(f"✅ {scenario_name} ολοκληρώθηκε")
            st.json(metrics)
            
        except Exception as e:
            st.error(f"Σφάλμα στο {scenario_name}: {e}")
    
    return step3_results

def run_step4(step3_results):
    """Εκτέλεση Βήματος 4 - Φιλικές Ομάδες"""
    st.subheader("👥 Βήμα 4: Ανάθεση Φιλικών Ομάδων")
    
    step4_results = {}
    
    for scenario_name, step3_data in step3_results.items():
        st.write(f"**Επεξεργασία {scenario_name}**")
        
        try:
            df = step3_data['df']
            step3_col = step3_data['column']
            
            progress_bar = st.progress(0)
            
            # Εκτέλεση Step 4
            results = apply_step4_strict(
                df, 
                assigned_column=step3_col, 
                num_classes=2,
                max_results=3,
                max_nodes=50000
            )
            
            progress_bar.progress(100)
            
            if results:
                best_placement, best_penalty = results[0]
                
                # Εφαρμογή ανάθεσης
                df_step4 = df.copy()
                step4_col = step3_col.replace('ΒΗΜΑ3', 'ΒΗΜΑ4')
                df_step4[step4_col] = df_step4[step3_col]
                
                # Ανάθεση ομάδων
                for group, class_assigned in best_placement.items():
                    for student in group:
                        mask = df_step4['ΟΝΟΜΑ'] == student
                        df_step4.loc[mask, step4_col] = class_assigned
                
                step4_results[scenario_name] = {
                    'df': df_step4,
                    'penalty': best_penalty,
                    'column': step4_col
                }
                
                st.success(f"✅ {scenario_name}: Penalty = {best_penalty}")
            else:
                st.warning(f"⚠️ {scenario_name}: Δεν βρέθηκαν λύσεις")
                
        except Exception as e:
            st.error(f"Σφάλμα στο {scenario_name}: {e}")
    
    return step4_results

def run_steps_5_6_7(step4_results):
    """Εκτέλεση Βημάτων 5, 6, 7 - Τελικοποίηση"""
    st.subheader("🏁 Βήματα 5-7: Τελικοποίηση Ανάθεσης")
    
    final_results = {}
    
    for scenario_name, step4_data in step4_results.items():
        st.write(f"**Τελικοποίηση {scenario_name}**")
        
        try:
            df = step4_data['df']
            step4_col = step4_data['column']
            
            # Step 5: Υπόλοιποι μαθητές
            df_step5, penalty5 = apply_step5_to_all_scenarios(
                {scenario_name: df}, 
                step4_col, 
                num_classes=2
            )
            if df_step5 is not None:
                df = df_step5
            
            # Step 6: Τελικός έλεγχος
            step5_col = step4_col.replace('ΒΗΜΑ4', 'ΒΗΜΑ5')
            if step5_col not in df.columns:
                df[step5_col] = df[step4_col]
            
            step6_output = apply_step6_to_step5_scenarios(
                {scenario_name: df},
                class_col=step5_col
            )
            
            if scenario_name in step6_output:
                df_final = step6_output[scenario_name]['df']
                summary6 = step6_output[scenario_name]['summary']
            else:
                df_final = df
                summary6 = {}
            
            # Step 7: Τελικό σκορ
            step6_col = 'ΒΗΜΑ6_ΤΜΗΜΑ'
            if step6_col not in df_final.columns:
                step6_col = step5_col
            
            final_score = score_one_scenario_auto(df_final, step6_col)
            
            final_results[scenario_name] = {
                'df': df_final,
                'step5_penalty': penalty5 if 'penalty5' in locals() else 0,
                'step6_summary': summary6,
                'final_score': final_score,
                'final_column': step6_col
            }
            
            st.success(f"✅ {scenario_name} ολοκληρώθηκε")
            st.write(f"**Τελικό Score:** {final_score['total_score']}")
            
        except Exception as e:
            st.error(f"Σφάλμα στην τελικοποίηση {scenario_name}: {e}")
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
    
    # Γράφημα σύγκρισης
    if PLOTLY_AVAILABLE:
        fig = px.bar(
            comparison_df, 
            x='Σενάριο', 
            y='Συνολικό Score',
            title='Σύγκριση Σεναρίων - Συνολικό Score'
        )
        st.plotly_chart(fig, use_container_width=True)
    elif MATPLOTLIB_AVAILABLE:
        fig, ax = plt.subplots()
        ax.bar(comparison_df['Σενάριο'], comparison_df['Συνολικό Score'])
        ax.set_title('Σύγκριση Σεναρίων - Συνολικό Score')
        ax.set_xlabel('Σενάριο')
        ax.set_ylabel('Συνολικό Score')
        plt.xticks(rotation=45)
        st.pyplot(fig)
    else:
        st.write("**Σύγκριση Score ανά Σενάριο:**")
        score_data = comparison_df[['Σενάριο', 'Συνολικό Score']].copy()
        st.dataframe(score_data, use_container_width=True)
    
    # Αναλυτικά στατιστικά για κάθε σενάριο
    st.subheader("📊 Αναλυτικά Στατιστικά Τελικών Σεναρίων")
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
                except Exception as e:
                    print(f"Σφάλμα στα στατιστικά {scenario_name}: {e}")
                
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
            
            # Βήμα 2
            if st.sidebar.button("▶️ Εκτέλεση Βήματος 2", disabled=st.session_state.current_step != 2):
                if 'step1' in st.session_state.step_results:
                    with st.spinner("Εκτέλεση Βήματος 2..."):
                        result = run_step2(st.session_state.step_results['step1'])
                        if result:
                            st.session_state.step_results['step2'] = result
                            st.session_state.current_step = 3
            
            # Βήμα 3
            if st.sidebar.button("▶️ Εκτέλεση Βήματος 3", disabled=st.session_state.current_step != 3):
                if 'step2' in st.session_state.step_results:
                    with st.spinner("Εκτέλεση Βήματος 3..."):
                        result = run_step3(st.session_state.step_results['step2'])
                        if result:
                            st.session_state.step_results['step3'] = result
                            st.session_state.current_step = 4
            
            # Βήμα 4
            if st.sidebar.button("▶️ Εκτέλεση Βήματος 4", disabled=st.session_state.current_step != 4):
                if 'step3' in st.session_state.step_results:
                    with st.spinner("Εκτέλεση Βήματος 4..."):
                        result = run_step4(st.session_state.step_results['step3'])
                        if result:
                            st.session_state.step_results['step4'] = result
                            st.session_state.current_step = 5
            
            # Βήματα 5-7
            if st.sidebar.button("▶️ Εκτέλεση Βημάτων 5-7", disabled=st.session_state.current_step != 5):
                if 'step4' in st.session_state.step_results:
                    with st.spinner("Εκτέλεση Βημάτων 5-7..."):
                        result = run_steps_5_6_7(st.session_state.step_results['step4'])
                        if result:
                            st.session_state.step_results['final'] = result
                            st.session_state.current_step = 6
            
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
                st.rerun()  # Χρήση st.rerun() αντί για st.experimental_rerun()
    
    else:
        st.info("👆 Παρακαλώ ανεβάστε ένα αρχείο Excel ή CSV για να ξεκινήσετε")

if __name__ == "__main__":
    main()

# --- Export Excel: Βήματα 1–6 ανά Σενάριο ---
try:
    import streamlit as st
    if 'step_results' in st.session_state:
        create_steps_excel_download_ui(st.session_state.step_results)
except Exception:
    pass