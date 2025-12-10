import sqlite3
import os

DB_PATH = "backend/medical.db"
SCHEMA_PATH = "backend/db/schema.sql"

def get_db_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def seed_realistic_data():
    """Seeds the database with realistic dummy data across all tables."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Realistic Patients
    patients = [
        ("Emma Thompson", 28, "Female", "142 Riverside Dr, Boston, MA", "617-555-0123", "No known allergies"),
        ("James Wilson", 45, "Male", "89 Oak Avenue, Cambridge, MA", "617-555-0456", "History of hypertension, takes Lisinopril"),
        ("Maria Garcia", 52, "Female", "301 Pine Street, Somerville, MA", "617-555-0789", "Type 2 diabetes, allergic to sulfa drugs"),
        ("Robert Chen", 34, "Male", "567 Elm Road, Brookline, MA", "617-555-1012", "Asthma, uses rescue inhaler"),
        ("Jennifer Adams", 61, "Female", "234 Maple Lane, Newton, MA", "617-555-1345", "Arthritis, high cholesterol"),
        ("Michael Brown", 39, "Male", "876 Cedar Court, Quincy, MA", "617-555-1678", "Seasonal allergies"),
        ("Lisa Patel", 47, "Female", "445 Birch Way, Medford, MA", "617-555-1901", "Migraine history, anxiety"),
        ("David Kim", 55, "Male", "112 Spruce Blvd, Malden, MA", "617-555-2234", "Heart disease, pacemaker installed 2020"),
        ("Sarah Johnson", 31, "Female", "789 Willow St, Arlington, MA", "617-555-2567", "Pregnant - 2nd trimester"),
        ("Thomas Martinez", 42, "Male", "654 Ash Drive, Watertown, MA", "617-555-2890", "Back pain, physical therapy ongoing")
    ]
    cursor.executemany("INSERT INTO patients (name, age, gender, address, phone, notes) VALUES (?, ?, ?, ?, ?, ?)", patients)
    
    # Get the inserted patient IDs
    cursor.execute("SELECT id FROM patients ORDER BY id DESC LIMIT 10")
    patient_ids = [row[0] for row in cursor.fetchall()][::-1]
    
    # Realistic Visits
    visits = [
        (patient_ids[0], "2025-11-15", "Annual physical exam - all vitals normal", "Dr. Sarah Mitchell"),
        (patient_ids[0], "2025-12-02", "Follow-up for flu symptoms", "Dr. Sarah Mitchell"),
        (patient_ids[1], "2025-10-20", "Blood pressure check - elevated, adjusted medication", "Dr. James Harper"),
        (patient_ids[1], "2025-11-18", "Hypertension follow-up - BP improved", "Dr. James Harper"),
        (patient_ids[1], "2025-12-05", "Routine checkup", "Dr. James Harper"),
        (patient_ids[2], "2025-11-01", "Diabetes management review", "Dr. Emily Rodriguez"),
        (patient_ids[2], "2025-12-08", "A1C test results review - levels stable", "Dr. Emily Rodriguez"),
        (patient_ids[3], "2025-11-22", "Asthma exacerbation - prescribed prednisone", "Dr. Michael Chang"),
        (patient_ids[4], "2025-10-15", "Joint pain evaluation", "Dr. Lisa Wong"),
        (patient_ids[4], "2025-11-28", "Arthritis medication adjustment", "Dr. Lisa Wong"),
        (patient_ids[5], "2025-12-01", "Allergy consultation", "Dr. Sarah Mitchell"),
        (patient_ids[6], "2025-11-10", "Migraine management", "Dr. Robert Kim"),
        (patient_ids[6], "2025-12-06", "Anxiety follow-up - improving with therapy", "Dr. Robert Kim"),
        (patient_ids[7], "2025-11-05", "Cardiac checkup - pacemaker functioning normally", "Dr. James Harper"),
        (patient_ids[8], "2025-11-20", "Prenatal checkup - 24 weeks", "Dr. Emily Rodriguez"),
        (patient_ids[8], "2025-12-04", "Prenatal checkup - 26 weeks, all normal", "Dr. Emily Rodriguez"),
        (patient_ids[9], "2025-11-12", "Back pain assessment", "Dr. Michael Chang"),
        (patient_ids[9], "2025-12-03", "Physical therapy progress review", "Dr. Michael Chang")
    ]
    cursor.executemany("INSERT INTO visits (patient_id, date, diagnosis, doctor) VALUES (?, ?, ?, ?)", visits)
    
    # Get visit IDs
    cursor.execute("SELECT id FROM visits ORDER BY id DESC LIMIT 18")
    visit_ids = [row[0] for row in cursor.fetchall()][::-1]
    
    # Realistic Prescriptions
    prescriptions = [
        (visit_ids[1], "Oseltamivir", "75mg twice daily for 5 days"),
        (visit_ids[2], "Lisinopril", "20mg once daily"),
        (visit_ids[3], "Lisinopril", "10mg once daily - reduced dose"),
        (visit_ids[5], "Metformin", "500mg twice daily"),
        (visit_ids[6], "Metformin", "500mg twice daily - continue"),
        (visit_ids[7], "Prednisone", "40mg daily for 5 days, then taper"),
        (visit_ids[7], "Albuterol inhaler", "2 puffs every 4-6 hours as needed"),
        (visit_ids[8], "Ibuprofen", "400mg three times daily with food"),
        (visit_ids[9], "Meloxicam", "15mg once daily"),
        (visit_ids[10], "Cetirizine", "10mg once daily"),
        (visit_ids[11], "Sumatriptan", "50mg as needed for migraine"),
        (visit_ids[12], "Sertraline", "50mg once daily"),
        (visit_ids[14], "Prenatal vitamins", "1 tablet daily"),
        (visit_ids[15], "Prenatal vitamins", "1 tablet daily - continue"),
        (visit_ids[16], "Cyclobenzaprine", "10mg three times daily"),
        (visit_ids[17], "Physical therapy", "2 sessions per week")
    ]
    cursor.executemany("INSERT INTO prescriptions (visit_id, medication, dosage) VALUES (?, ?, ?)", prescriptions)
    
    # Realistic Billing
    billing = [
        (patient_ids[0], 175.00, "Paid", "2025-11-15"),
        (patient_ids[0], 125.00, "Pending", "2025-12-02"),
        (patient_ids[1], 150.00, "Paid", "2025-10-20"),
        (patient_ids[1], 150.00, "Paid", "2025-11-18"),
        (patient_ids[1], 175.00, "Pending", "2025-12-05"),
        (patient_ids[2], 250.00, "Paid", "2025-11-01"),
        (patient_ids[2], 200.00, "Pending", "2025-12-08"),
        (patient_ids[3], 185.00, "Overdue", "2025-11-22"),
        (patient_ids[4], 225.00, "Paid", "2025-10-15"),
        (patient_ids[4], 175.00, "Pending", "2025-11-28"),
        (patient_ids[5], 150.00, "Paid", "2025-12-01"),
        (patient_ids[6], 200.00, "Paid", "2025-11-10"),
        (patient_ids[6], 175.00, "Pending", "2025-12-06"),
        (patient_ids[7], 450.00, "Paid", "2025-11-05"),
        (patient_ids[8], 300.00, "Paid", "2025-11-20"),
        (patient_ids[8], 300.00, "Pending", "2025-12-04"),
        (patient_ids[9], 225.00, "Overdue", "2025-11-12"),
        (patient_ids[9], 175.00, "Pending", "2025-12-03")
    ]
    cursor.executemany("INSERT INTO billing (patient_id, amount, status, date) VALUES (?, ?, ?, ?)", billing)
    
    conn.commit()
    conn.close()
    
    return {
        "patients": len(patients),
        "visits": len(visits),
        "prescriptions": len(prescriptions),
        "billing": len(billing)
    }

def init_db():
    if not os.path.exists(DB_PATH):
        print("Initializing database...")
        conn = get_db_connection()
        with open(SCHEMA_PATH, 'r') as f:
            schema = f.read()
        conn.executescript(schema)
        
        # Seed data
        cursor = conn.cursor()
        
        # Seed Patients
        patients = [
            ("John Doe", 45, "Male", "123 Maple St", "555-0101", "Hypertension history"),
            ("Sarah Ali", 35, "Female", "456 Oak St", "555-0102", "Allergy to penicillin"),
            ("Bob Smith", 60, "Male", "789 Pine St", "555-0103", "Diabetic")
        ]
        cursor.executemany("INSERT INTO patients (name, age, gender, address, phone, notes) VALUES (?, ?, ?, ?, ?, ?)", patients)
        
        # Seed Visits (Assuming IDs 1, 2, 3)
        visits = [
            (1, "2023-10-01", "Routine Checkup", "Dr. House"),
            (2, "2023-10-05", "Flu Symptoms", "Dr. Wilson"),
            (1, "2023-11-15", "Blood Pressure Follow-up", "Dr. House")
        ]
        cursor.executemany("INSERT INTO visits (patient_id, date, diagnosis, doctor) VALUES (?, ?, ?, ?)", visits)
        
        # Seed Prescriptions (Assuming Visit IDs 1, 2, 3)
        prescriptions = [
            (3, "Lisinopril", "10mg daily"),
            (2, "Tamiflu", "75mg twice daily")
        ]
        cursor.executemany("INSERT INTO prescriptions (visit_id, medication, dosage) VALUES (?, ?, ?)", prescriptions)
        
        # Seed Billing
        billing = [
            (1, 150.00, "Paid", "2023-10-01"),
            (2, 200.00, "Pending", "2023-10-05"),
            (1, 100.00, "Paid", "2023-11-15")
        ]
        cursor.executemany("INSERT INTO billing (patient_id, amount, status, date) VALUES (?, ?, ?, ?)", billing)
        
        conn.commit()
        conn.close()
        print("Database initialized and seeded.")
    else:
        print("Database already exists.")

if __name__ == "__main__":
    init_db()
