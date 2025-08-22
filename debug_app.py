# -*- coding: utf-8 -*-
"""
Debug version - Ελάχιστος κώδικας για εντοπισμό προβλήματος
"""

import streamlit as st
import pandas as pd
import numpy as np

# Streamlit configuration
st.set_page_config(
    page_title="Debug - Σύστημα Ανάθεσης",
    page_icon="🔧",
    layout="wide"
)

def main():
    st.title("🔧 Debug Mode - Σύστημα Ανάθεσης Μαθητών")
    st.write("Ελάχιστη έκδοση για εντοπισμό προβλημάτων")
    
    # Test file upload
    uploaded_file = st.file_uploader(
        "Upload test file",
        type=['xlsx', 'csv']
    )
    
    if uploaded_file is not None:
        try:
            st.success("✅ Αρχείο φορτώθηκε επιτυχώς!")
            
            # Try to read file
            if uploaded_file.name.endswith('.xlsx'):
                df = pd.read_excel(uploaded_file)
            else:
                df = pd.read_csv(uploaded_file)
            
            st.success(f"✅ Δεδομένα διαβάστηκαν: {len(df)} γραμμές, {len(df.columns)} στήλες")
            
            # Show basic info
            st.write("**Στήλες:**", list(df.columns))
            st.write("**Πρώτες 5 γραμμές:**")
            st.dataframe(df.head())
            
            # Safe metrics calculation
            total = len(df)
            st.metric("Συνολικές γραμμές", total)
            
            # Test specific columns
            if 'ΦΥΛΟ' in df.columns:
                boys = int((df['ΦΥΛΟ'] == 'Α').sum())
                girls = int((df['ΦΥΛΟ'] == 'Κ').sum())
                st.write(f"Αγόρια: {boys}, Κορίτσια: {girls}")
            else:
                st.warning("Δεν βρέθηκε στήλη ΦΥΛΟ")
            
            if 'ΠΑΙΔΙ_ΕΚΠΑΙΔΕΥΤΙΚΟΥ' in df.columns:
                teachers = int((df['ΠΑΙΔΙ_ΕΚΠΑΙΔΕΥΤΙΚΟΥ'] == 'Ν').sum())
                st.write(f"Παιδιά εκπαιδευτικών: {teachers}")
            else:
                st.warning("Δεν βρέθηκε στήλη ΠΑΙΔΙ_ΕΚΠΑΙΔΕΥΤΙΚΟΥ")
                
        except Exception as e:
            st.error(f"❌ Σφάλμα: {e}")
            import traceback
            st.code(traceback.format_exc())
    
    else:
        st.info("👆 Ανεβάστε ένα αρχείο για test")

if __name__ == "__main__":
    main()
