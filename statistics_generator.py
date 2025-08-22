import pandas as pd
from io import BytesIO


def generate_statistics_table(df):
    """
    Δημιουργεί ενιαίο πίνακα στατιστικών ανά τμήμα.
    Περιλαμβάνει μόνο όσους έχουν Ν ή Α/Κ στα αντίστοιχα πεδία.
    """
    df = df.copy()

    # Κανονικοποίηση φύλου: Α / Κ
    boys = df[df["ΦΥΛΟ"] == "Α"].groupby("ΤΜΗΜΑ").size()
    girls = df[df["ΦΥΛΟ"] == "Κ"].groupby("ΤΜΗΜΑ").size()

    # Ναι = Ν για τα υπόλοιπα χαρακτηριστικά
    educators = df[df["ΠΑΙΔΙ_ΕΚΠΑΙΔΕΥΤΙΚΟΥ"] == "Ν"].groupby("ΤΜΗΜΑ").size()
    energetic = df[df["ΖΩΗΡΟΣ"] == "Ν"].groupby("ΤΜΗΜΑ").size()
    special = df[df["ΙΔΙΑΙΤΕΡΟΤΗΤΑ"] == "Ν"].groupby("ΤΜΗΜΑ").size()
    greek = df[df["ΚΑΛΗ_ΓΝΩΣΗ_ΕΛΛΗΝΙΚΩΝ"] == "Ν"].groupby("ΤΜΗΜΑ").size()
    total = df.groupby("ΤΜΗΜΑ").size()

    # Ενοποίηση
    stats = pd.DataFrame({
        "ΑΓΟΡΙΑ": boys,
        "ΚΟΡΙΤΣΙΑ": girls,
        "ΕΚΠΑΙΔΕΥΤΙΚΟΙ": educators,
        "ΖΩΗΡΟΙ": energetic,
        "ΙΔΙΑΙΤΕΡΟΤΗΤΑ": special,
        "ΓΝΩΣΗ ΕΛΛ.": greek,
        "ΣΥΝΟΛΟ": total
    }).fillna(0).astype(int)

    # Ταξινόμηση ΤΜΗΜΑτων αν είναι Α1, Α2, ...
    stats = stats.sort_index(key=lambda x: x.str.extract(r'(\d+)').astype(float))

    return stats


def export_statistics_to_excel(stats_df):
    """
    Επιστρέφει BytesIO αντικείμενο με τα στατιστικά σε μορφή Excel.
    """
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        stats_df.to_excel(writer, index=True, sheet_name='Στατιστικά')
    output.seek(0)
    return output
