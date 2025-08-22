# -*- coding: utf-8 -*-
"""
ΑΠΛΗ ΕΚΔΟΣΗ - Χωρίς session state και περίπλοκη λογική
"""

import streamlit as st
import pandas as pd

# Streamlit configuration
st.set_page_config(
    page_title="Απλό Σύστημα Ανάθεσης",
    page_icon="🎓",
    layout="wide"
)

def safe_load_data(uploaded_file):
    """Ασφαλής φόρτωση δεδομένων"""
    try:
        if uploaded_file.name.endswith('.xlsx'):
            df = pd.read_excel(uploaded_file)
        elif uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            return None, "Μη υποστηριζόμενο format αρχείου"
        
        return df, None
    except Exception as e:
        return None, f"Σφάλμα φόρτωσης: {str(e)}"

def display_basic_info(df):
    """Βασικές πληροφορίες χωρίς περίπλοκα γραφήματα"""
    st.subheader("📊 Βασικές Πληροφορίες")
    
    # Μετρικές με ασφαλή τρόπο
    total_students = len(df)
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Συνολικοί Μαθητές", total_students)
    
    with col2:
        try:
            if 'ΦΥΛΟ' in df.columns:
                boys_count = len(df[df['ΦΥΛΟ'] == 'Α'])
                st.metric("Αγόρια", boys_count)
            else:
                st.metric("Αγόρια", "N/A")
        except:
            st.metric("Αγόρια", "Error")
    
    with col3:
        try:
            if 'ΦΥΛΟ' in df.columns:
                girls_count = len(df[df['ΦΥΛΟ'] == 'Κ'])
                st.metric("Κορίτσια", girls_count)
            else:
                st.metric("Κορίτσια", "N/A")
        except:
            st.metric("Κορίτσια", "Error")
    
    with col4:
        try:
            if 'ΠΑΙΔΙ_ΕΚΠΑΙΔΕΥΤΙΚΟΥ' in df.columns:
                teachers_count = len(df[df['ΠΑΙΔΙ_ΕΚΠΑΙΔΕΥΤΙΚΟΥ'] == 'Ν'])
                st.metric("Παιδιά Εκπαιδευτικών", teachers_count)
            else:
                st.metric("Παιδιά Εκπαιδευτικών", "N/A")
        except:
            st.metric("Παιδιά Εκπαιδευτικών", "Error")

def main():
    """Κύρια συνάρτηση - ΑΠΛΗ έκδοση"""
    
    st.title("🎓 Απλό Σύστημα Ανάθεσης Μαθητών")
    st.markdown("*Βασική έκδοση χωρίς περίπλοκη λογική*")
    
    # File upload
    st.sidebar.header("📁 Φόρτωση Αρχείου")
    uploaded_file = st.sidebar.file_uploader(
        "Επιλέξτε Excel ή CSV",
        type=['xlsx', 'csv'],
        help="Ανεβάστε το αρχείο με τα στοιχεία των μαθητών"
    )
    
    if uploaded_file is not None:
        # Φόρτωση δεδομένων
        st.info("🔄 Φόρτωση αρχείου...")
        
        df, error = safe_load_data(uploaded_file)
        
        if error:
            st.error(f"❌ {error}")
            return
        
        if df is None:
            st.error("❌ Δεν ήταν δυνατή η φόρτωση του αρχείου")
            return
            
        st.success("✅ Αρχείο φορτώθηκε επιτυχώς!")
        
        # Εμφάνιση βασικών στοιχείων
        display_basic_info(df)
        
        # Εμφάνιση στηλών
        st.subheader("📋 Στήλες Δεδομένων")
        st.write("**Διαθέσιμες στήλες:**", list(df.columns))
        
        # Εμφάνιση δείγματος δεδομένων
        st.subheader("👀 Δείγμα Δεδομένων")
        st.dataframe(df.head(10), use_container_width=True)
        
        # Πληροφορίες τύπων δεδομένων
        st.subheader("🔍 Ανάλυση Δεδομένων")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**Τύποι δεδομένων:**")
            types_df = pd.DataFrame({
                'Στήλη': df.dtypes.index,
                'Τύπος': df.dtypes.values
            })
            st.dataframe(types_df, use_container_width=True)
        
        with col2:
            st.write("**Κενές τιμές:**")
            nulls_df = pd.DataFrame({
                'Στήλη': df.isnull().sum().index,
                'Κενές': df.isnull().sum().values
            })
            st.dataframe(nulls_df, use_container_width=True)
        
        # Κατάλογος αναγνωρισμένων στηλών
        st.subheader("✅ Αναγνώριση Στηλών")
        
        recognized_cols = []
        if 'ΟΝΟΜΑ' in df.columns or any('ΟΝΟΜΑ' in str(col).upper() for col in df.columns):
            recognized_cols.append("✅ Ονόματα μαθητών")
        else:
            recognized_cols.append("❌ Ονόματα μαθητών")
            
        if 'ΦΥΛΟ' in df.columns or any('ΦΥΛΟ' in str(col).upper() for col in df.columns):
            recognized_cols.append("✅ Φύλο")
        else:
            recognized_cols.append("❌ Φύλο")
            
        if any('ΓΝΩΣΗ' in str(col).upper() and 'ΕΛΛΗΝΙΚ' in str(col).upper() for col in df.columns):
            recognized_cols.append("✅ Γνώση Ελληνικών")
        else:
            recognized_cols.append("❌ Γνώση Ελληνικών")
            
        if any('ΠΑΙΔΙ' in str(col).upper() and 'ΕΚΠΑΙΔΕΥΤΙΚ' in str(col).upper() for col in df.columns):
            recognized_cols.append("✅ Παιδιά Εκπαιδευτικών")
        else:
            recognized_cols.append("❌ Παιδιά Εκπαιδευτικών")
        
        for item in recognized_cols:
            st.write(item)
        
        # Download processed data
        st.subheader("💾 Εξαγωγή Δεδομένων")
        
        # Convert to Excel
        output = pd.ExcelWriter("processed_data.xlsx", engine='xlsxwriter')
        df.to_excel(output, sheet_name='Δεδομένα', index=False)
        output.close()
        
        with open("processed_data.xlsx", "rb") as file:
            st.download_button(
                label="📥 Λήψη Excel",
                data=file,
                file_name="processed_data.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        
        # Οδηγίες επόμενων βημάτων
        st.subheader("🔄 Επόμενα Βήματα")
        st.info("""
        **Για να συνεχίσετε με την ανάθεση:**
        1. Βεβαιωθείτε ότι τα δεδομένα σας είναι σωστά
        2. Οι στήλες πρέπει να ονομάζονται: ΟΝΟΜΑ, ΦΥΛΟ, ΚΑΛΗ_ΓΝΩΣΗ_ΕΛΛΗΝΙΚΩΝ, ΠΑΙΔΙ_ΕΚΠΑΙΔΕΥΤΙΚΟΥ
        3. Χρησιμοποιήστε την πλήρη έκδοση του συστήματος για την ανάθεση
        """)
        
    else:
        # Οδηγίες χρήσης
        st.info("👆 Παρακαλώ ανεβάστε ένα αρχείο Excel ή CSV για να ξεκινήσετε")
        
        st.subheader("📖 Οδηγίες Προετοιμασίας Αρχείου")
        
        st.markdown("""
        ### Απαιτούμενες Στήλες:
        - **ΟΝΟΜΑ**: Ονοματεπώνυμο μαθητή
        - **ΦΥΛΟ**: Α (Αγόρι) ή Κ (Κορίτσι)  
        - **ΚΑΛΗ_ΓΝΩΣΗ_ΕΛΛΗΝΙΚΩΝ**: Ν (Ναι) ή Ο (Όχι)
        - **ΠΑΙΔΙ_ΕΚΠΑΙΔΕΥΤΙΚΟΥ**: Ν (Ναι) ή Ο (Όχι)
        
        ### Προαιρετικές Στήλες:
        - **ΦΙΛΟΙ**: Λίστα ονομάτων φίλων
        - **ΖΩΗΡΟΣ**: Ν (Ναι) ή Ο (Όχι)
        - **ΙΔΙΑΙΤΕΡΟΤΗΤΑ**: Ν (Ναι) ή Ο (Όχι)
        - **ΣΥΓΚΡΟΥΣΗ**: Λίστα ονομάτων συγκρουόμενων μαθητών
        
        ### Παράδειγμα Δεδομένων:
        ```
        ΟΝΟΜΑ                | ΦΥΛΟ | ΚΑΛΗ_ΓΝΩΣΗ_ΕΛΛΗΝΙΚΩΝ | ΠΑΙΔΙ_ΕΚΠΑΙΔΕΥΤΙΚΟΥ
        Μαρία Παπαδοπούλου   | Κ    | Ν                    | Ο
        Γιάννης Αντωνίου     | Α    | Ο                    | Ν
        Άννα Γεωργίου        | Κ    | Ν                    | Ο
        ```
        """)

if __name__ == "__main__":
    main()
