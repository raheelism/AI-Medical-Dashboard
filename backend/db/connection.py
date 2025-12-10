import sqlite3
import os

DB_PATH = "backend/medical.db"
SCHEMA_PATH = "backend/db/schema.sql"

def get_db_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

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
