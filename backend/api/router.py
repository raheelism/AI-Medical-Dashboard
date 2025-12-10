from fastapi import APIRouter
from backend.db.connection import get_db_connection

router = APIRouter()

@router.get("/patients")
def get_patients():
    conn = get_db_connection()
    patients = conn.execute("SELECT * FROM patients").fetchall()
    conn.close()
    return [dict(p) for p in patients]

@router.get("/visits")
def get_visits():
    conn = get_db_connection()
    visits = conn.execute("SELECT * FROM visits").fetchall()
    conn.close()
    return [dict(v) for v in visits]

@router.get("/prescriptions")
def get_prescriptions():
    conn = get_db_connection()
    prescriptions = conn.execute("SELECT * FROM prescriptions").fetchall()
    conn.close()
    return [dict(p) for p in prescriptions]

@router.get("/billing")
def get_billing():
    conn = get_db_connection()
    billing = conn.execute("SELECT * FROM billing").fetchall()
    conn.close()
    return [dict(b) for b in billing]

@router.get("/audit_log")
def get_audit_log():
    conn = get_db_connection()
    logs = conn.execute("SELECT * FROM audit_log ORDER BY time DESC").fetchall()
    conn.close()
    return [dict(l) for l in logs]
