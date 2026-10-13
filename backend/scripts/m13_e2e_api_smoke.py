"""
M13 API smoke against live local API + MongoDB.
Uses unique m13-* emails; does not delete existing student data.
Does not modify backend/.env or print secrets.
"""
from __future__ import annotations

import io
import json
import sys
import time
import uuid
from pathlib import Path

import requests

BASE = "http://127.0.0.1:8000"
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "scripts" / "m13_e2e_results.json"
results: list[dict] = []


def record(name: str, status: str, detail: str = "") -> None:
    results.append({"feature": name, "status": status, "detail": detail[:500]})
    print(f"[{status}] {name} :: {detail[:220]}")


def make_pdf_bytes(lines: list[str]) -> bytes:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    y = 750
    for line in lines:
        c.drawString(72, y, line[:110])
        y -= 18
        if y < 72:
            c.showPage()
            y = 750
    c.save()
    return buf.getvalue()


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def main() -> int:
    stamp = time.strftime("%Y%m%d%H%M%S")
    uid = uuid.uuid4().hex[:8]
    email_a = f"m13a.{stamp}.{uid}@example.edu"
    email_b = f"m13b.{stamp}.{uid}@example.edu"
    password = "TestPass123"

    try:
        health = requests.get(f"{BASE}/health", timeout=10)
        db = requests.get(f"{BASE}/health/database", timeout=20)
        db_json = db.json() if db.status_code == 200 else {}
        db_status = db_json.get("status")
        ok = health.status_code == 200 and db_status == "connected"
        record("Health/DB", "PASS" if ok else "FAIL", f"health={health.status_code} db={db_status}")
        if not ok:
            OUT.write_text(json.dumps({"results": results}, indent=2), encoding="utf-8")
            return 1
    except Exception as e:
        record("Health/DB", "BLOCKED", f"{type(e).__name__}: {e}")
        OUT.write_text(json.dumps({"results": results}, indent=2), encoding="utf-8")
        return 1

    # Register A
    r = requests.post(
        f"{BASE}/auth/register",
        json={"email": email_a, "password": password, "name": "M13 Student A"},
        timeout=30,
    )
    data = r.json() if r.content else {}
    if r.status_code not in (200, 201) or not data.get("access_token"):
        record("Register A (Mongo)", "FAIL", f"status={r.status_code} {str(data)[:200]}")
        OUT.write_text(json.dumps({"results": results}, indent=2), encoding="utf-8")
        return 1
    persistence = data.get("persistence")
    token_a = data["access_token"]
    record(
        "Register A (Mongo)",
        "PASS" if persistence == "mongo" else "FAIL",
        f"persistence={persistence}",
    )

    # Login A
    r = requests.post(
        f"{BASE}/auth/login",
        json={"email": email_a, "password": password},
        timeout=30,
    )
    data = r.json() if r.content else {}
    if r.status_code == 200 and data.get("access_token"):
        token_a = data["access_token"]
        record("Login A", "PASS", "token issued")
    else:
        record("Login A", "FAIL", f"status={r.status_code}")
        OUT.write_text(json.dumps({"email_a": email_a, "results": results}, indent=2), encoding="utf-8")
        return 1

    # Unauthenticated
    r = requests.get(f"{BASE}/student/{email_a}", timeout=15)
    record(
        "Unauthenticated API denied",
        "PASS" if r.status_code in (401, 403) else "FAIL",
        f"status={r.status_code}",
    )

    # Profile
    profile = {
        "email": email_a,
        "age": 20,
        "course": "B.Tech",
        "year": 2,
        "branch": "CSE",
        "study_hours": 4.0,
        "attendance": 88.0,
        "previous_cgpa": 3.4,
        "subjects": ["Networks", "ML"],
    }
    r = requests.post(f"{BASE}/student/profile", json=profile, headers=auth_headers(token_a), timeout=30)
    if r.status_code in (200, 201):
        g = requests.get(f"{BASE}/student/{email_a}", headers=auth_headers(token_a), timeout=15)
        body = g.json() if g.content else {}
        record(
            "Profile save/reload",
            "PASS" if g.status_code == 200 and (body.get("email") or "").lower() == email_a.lower() else "FAIL",
            f"get={g.status_code}",
        )
    else:
        record("Profile save/reload", "FAIL", f"save={r.status_code} {r.text[:180]}")

    # Prediction
    pred = {
        "Hours_Studied": 6.0,
        "Attendance": 88.0,
        "Sleep_Hours": 7.0,
        "Previous_Scores": 72.0,
        "Tutoring_Sessions": 2,
        "Physical_Activity": 3.0,
        "Parental_Involvement": "Medium",
        "Access_to_Resources": "High",
        "Extracurricular_Activities": "Yes",
        "Motivation_Level": "High",
        "Internet_Access": "Yes",
        "Family_Income": "Medium",
        "Teacher_Quality": "High",
        "School_Type": "Private",
        "Peer_Influence": "Positive",
        "Learning_Disabilities": "No",
        "Parental_Education_Level": "College",
        "Distance_from_Home": "Near",
        "Gender": "Female",
        "email": email_a,
    }
    r = requests.post(f"{BASE}/predict/exam-score", json=pred, headers=auth_headers(token_a), timeout=30)
    body = r.json() if r.content else {}
    record(
        "Score prediction",
        "PASS" if r.status_code == 200 and "predicted_exam_score" in body else "FAIL",
        f"status={r.status_code} score={body.get('predicted_exam_score')}",
    )

    # Study plan
    plan_req = {
        "email": email_a,
        "daily_study_hours": 3.0,
        "preferred_start_time": "09:00",
        "days_to_plan": 3,
        "subjects": [
            {"name": "Networks", "difficulty": "High", "current_score": 60.0, "target_score": 85.0}
        ],
        "risk_category": "Low Risk",
    }
    r = requests.post(f"{BASE}/study-plan/generate", json=plan_req, headers=auth_headers(token_a), timeout=45)
    if r.status_code == 200:
        g = requests.get(f"{BASE}/study-plan/{email_a}", headers=auth_headers(token_a), timeout=20)
        record(
            "Study plan generate/persist",
            "PASS" if g.status_code == 200 else "FAIL",
            f"generate=200 get={g.status_code}",
        )
    else:
        record("Study plan generate/persist", "FAIL", f"status={r.status_code} {r.text[:180]}")

    # PDF upload
    lines = [
        "Physical Layer is the lowest layer of the OSI model and moves raw bits over a medium.",
        "Data Link Layer means framing and error detection on a single link.",
        "Network Layer: routing packets between networks across hops.",
        "Introduction to Networking",
        "Transport Concepts",
        "TCP provides reliable ordered delivery for applications that need it.",
        "UDP is a connectionless transport protocol used for low-latency applications.",
        "Congestion control reduces sending rate when the network is overloaded.",
    ]
    pdf_bytes = make_pdf_bytes(lines)
    files = {"file": ("m13_networks.pdf", pdf_bytes, "application/pdf")}
    r = requests.post(
        f"{BASE}/documents/upload",
        data={"email": email_a},
        files=files,
        headers=auth_headers(token_a),
        timeout=90,
    )
    body = r.json() if r.content else {}
    doc_id = body.get("document_id")
    record(
        "PDF upload/extract",
        "PASS" if r.status_code in (200, 201) and doc_id else "FAIL",
        f"status={r.status_code} text_available={body.get('text_available')} pages={body.get('page_count') or body.get('pages')}",
    )

    if doc_id:
        r = requests.post(
            f"{BASE}/documents/{doc_id}/index",
            params={"email": email_a},
            headers=auth_headers(token_a),
            timeout=90,
        )
        record("RAG index", "PASS" if r.status_code == 200 else "FAIL", f"status={r.status_code} {r.text[:120]}")

        r = requests.post(
            f"{BASE}/documents/rag/ask",
            json={"email": email_a, "question": "What is the Physical Layer?", "document_id": doc_id},
            headers=auth_headers(token_a),
            timeout=90,
        )
        body = r.json() if r.content else {}
        mode = body.get("mode")
        record(
            "Ask Your Notes",
            "PASS" if r.status_code == 200 and mode in {"retrieval_only", "llm"} and body.get("answer") else "FAIL",
            f"status={r.status_code} mode={mode} provider={body.get('provider')}",
        )

    for tool, label in [
        ("summary", "Summary Notes"),
        ("flashcards", "Flashcards"),
        ("mindmap", "Mind Maps"),
        ("practice", "Practice Questions"),
        ("mock_exam", "Mock Exams"),
    ]:
        r = requests.post(
            f"{BASE}/ai/hub/local",
            json={"email": email_a, "tool": tool, "count": 4},
            headers=auth_headers(token_a),
            timeout=60,
        )
        body = r.json() if r.content else {}
        if r.status_code == 200 and body.get("mode") == "local":
            record(label, "PASS", f"provider={body.get('provider')}")
        elif r.status_code == 409:
            record(label, "PASS", f"honest insufficient-text 409 (no fabricate)")
        else:
            record(label, "FAIL", f"status={r.status_code} {str(body)[:160]}")

    # Student B + empty docs + ownership
    r = requests.post(
        f"{BASE}/auth/register",
        json={"email": email_b, "password": password, "name": "M13 Student B"},
        timeout=30,
    )
    data_b = r.json() if r.content else {}
    token_b = data_b.get("access_token")
    if not token_b:
        record("Register B", "FAIL", f"status={r.status_code}")
    else:
        record("Register B", "PASS", f"persistence={data_b.get('persistence')}")
        r = requests.post(
            f"{BASE}/ai/hub/local",
            json={"email": email_b, "tool": "flashcards", "count": 4},
            headers=auth_headers(token_b),
            timeout=30,
        )
        body = r.json() if r.content else {}
        detail = str(body.get("detail") or body).lower()
        record(
            "Empty docs no fabricate",
            "PASS" if r.status_code == 409 and "fabricat" not in detail else "FAIL",
            f"status={r.status_code}",
        )

        checks = []
        for label, call in [
            ("profile", lambda: requests.get(f"{BASE}/student/{email_a}", headers=auth_headers(token_b), timeout=20)),
            ("plan", lambda: requests.get(f"{BASE}/study-plan/{email_a}", headers=auth_headers(token_b), timeout=20)),
            ("docs", lambda: requests.get(f"{BASE}/documents", params={"email": email_a}, headers=auth_headers(token_b), timeout=20)),
            ("perf", lambda: requests.get(f"{BASE}/performance/{email_a}", headers=auth_headers(token_b), timeout=20)),
        ]:
            rr = call()
            checks.append((label, rr.status_code))
        bad = [c for c in checks if c[1] not in (401, 403)]
        record(
            "Cross-account ownership",
            "PASS" if not bad else "FAIL",
            f"checks={checks}",
        )

    # Progress
    r = requests.post(
        f"{BASE}/performance/session",
        json={
            "email": email_a,
            "subject": "Networks",
            "topic": "OSI",
            "status": "completed",
            "planned_minutes": 45,
            "actual_minutes": 40,
            "date": time.strftime("%Y-%m-%d"),
        },
        headers=auth_headers(token_a),
        timeout=30,
    )
    s = requests.get(f"{BASE}/performance/{email_a}", headers=auth_headers(token_a), timeout=20)
    record(
        "Progress tracking",
        "PASS" if r.status_code in (200, 201) and s.status_code == 200 else "FAIL",
        f"log={r.status_code} summary={s.status_code}",
    )

    payload = {"email_a": email_a, "email_b": email_b, "results": results}
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    fails = [x for x in results if x["status"] == "FAIL"]
    blocked = [x for x in results if x["status"] == "BLOCKED"]
    print(f"\nWrote {OUT} fails={len(fails)} blocked={len(blocked)}")
    return 1 if fails or blocked else 0


if __name__ == "__main__":
    raise SystemExit(main())
