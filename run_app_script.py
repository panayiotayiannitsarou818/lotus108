#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Quick setup and run script για το Streamlit app
Ελέγχει dependencies και τρέχει την εφαρμογή
"""

import subprocess
import sys
import os
from pathlib import Path

def check_python_version():
    """Έλεγχος έκδοσης Python"""
    if sys.version_info < (3, 8):
        print("❌ Χρειάζεται Python 3.8 ή νεότερο")
        print(f"Τρέχουσα έκδοση: {sys.version}")
        return False
    print(f"✅ Python έκδοση: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    return True

def check_requirements():
    """Έλεγχος και εγκατάσταση requirements"""
    requirements_file = Path("requirements.txt")
    if not requirements_file.exists():
        print("❌ Δεν βρέθηκε το αρχείο requirements.txt")
        return False
    
    print("📦 Έλεγχος dependencies...")
    try:
        # Έλεγχος αν υπάρχει το streamlit
        import streamlit
        print("✅ Streamlit ήδη εγκατεστημένο")
    except ImportError:
        print("📥 Εγκατάσταση dependencies...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
            print("✅ Dependencies εγκαταστάθηκαν επιτυχώς")
        except subprocess.CalledProcessError:
            print("❌ Σφάλμα εγκατάστασης dependencies")
            return False
    return True

def check_modules():
    """Έλεγχος ύπαρξης απαιτούμενων modules"""
    required_modules = [
        "streamlit_app.py",
        "streamlit_app_minimal.py", 
        "statistics_generator.py",
        "friendship_filters_fixed.py",
        "step_2_zoiroi_idiaterotites_FIXED_v3_PATCHED.py",
        "step3_amivaia_filia_FIXED.py",
        "step4_filikoi_omades_beltiosi_FIXED.py",
        "step_5_ypoloipoi_mathites_FIXED_compat.py",
        "step_6_final_check_and_fix_PATCHED.py",
        "step_7_final_score_FIXED_PATCHED.py"
    ]
    
    missing = []
    for module in required_modules:
        if not Path(module).exists():
            missing.append(module)
    
    if missing:
        print("❌ Λείπουν τα εξής modules:")
        for m in missing:
            print(f"   - {m}")
        print("\nΠαρακαλώ βεβαιωθείτε ότι όλα τα αρχεία είναι στον ίδιο φάκελο.")
        return False
    
    print("✅ Όλα τα απαιτούμενα modules βρέθηκαν")
    return True

def run_streamlit():
    """Εκκίνηση Streamlit app"""
    print("🚀 Εκκίνηση Streamlit app...")
    
    # Επιλογή έκδοσης app
    choice = input("Επιλέξτε έκδοση:\n1. Πλήρης (με γραφήματα)\n2. Minimal (χωρίς γραφήματα)\nΕπιλογή (1/2): ").strip()
    
    if choice == "2":
        app_file = "streamlit_app_minimal.py"
        if not Path(app_file).exists():
            print(f"❌ Δεν βρέθηκε το {app_file}")
            return False
        print("📱 Εκκίνηση minimal έκδοσης...")
    else:
        app_file = "streamlit_app.py"
        if not Path(app_file).exists():
            print(f"❌ Δεν βρέθηκε το {app_file}")
            return False
        print("📱 Εκκίνηση πλήρους έκδοσης...")
    
    print("📱 Η εφαρμογή θα ανοίξει στο browser σας")
    print("🔗 URL: http://localhost:8501")
    print("⏹️  Για τερματισμό: Ctrl+C\n")
    
    try:
        subprocess.run([sys.executable, "-m", "streamlit", "run", app_file])
    except KeyboardInterrupt:
        print("\n👋 Η εφαρμογή τερματίστηκε")
    except FileNotFoundError:
        print(f"❌ Δεν βρέθηκε το {app_file}")
        return False
    except Exception as e:
        print(f"❌ Σφάλμα εκκίνησης: {e}")
        return False
    
    return True

def main():
    """Κύρια συνάρτηση"""
    print("🎓 Σύστημα Ανάθεσης Μαθητών - Setup & Run")
    print("=" * 50)
    
    # Έλεγχοι
    if not check_python_version():
        return 1
    
    if not check_requirements():
        return 1
    
    if not check_modules():
        return 1
    
    # Εκκίνηση
    if not run_streamlit():
        return 1
    
    return 0

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
