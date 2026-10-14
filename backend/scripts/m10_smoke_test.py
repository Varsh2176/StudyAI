"""
M10 Step 3 — local API smoke tests. Prints statuses only; never prints secrets/tokens.
Run: python scripts/m10_smoke_test.py
"""

from __future__ import annotations

import io
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = "http://127.0.0.1:8000"
RESULTS = []


def record(stage: str, name: str, ok: bool, detail: str = ""):
    status = "PASS" if ok else "FAIL"
    RESULTS.append((stage, name, status, detail))
    print(f"[{status}] {stage} :: {name}" + (f" — {detail}" if detail else ""))


def req(method: str, path: str, body=None, token: str | None = None, form=None, files=None):
    url = BASE + path
    headers = {}
    data = None
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if form is not None or files is not None:
        # multipart via urllib is awkward; use requests-like manual for simple form fields
        # Prefer json for most; for upload use a separate helper
        raise NotImplementedError("use upload_pdf helper")
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=60) as resp:
            raw = resp.read().decode("utf-8")
            payload = json.loads(raw) if raw else {}
            return resp.status, payload, None
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw) if raw else {}
        except Exception:
            payload = {"detail": raw[:200]}
        return e.code, payload, None
    except Exception as e:
        return 0, {}, f"{type(e).__name__}: {e}"


def upload_pdf(token: str, email: str, pdf_bytes: bytes, filename: str = "smoke.pdf"):
    import uuid

    boundary = f"----SmokeBoundary{uuid.uuid4().hex}"
    parts = []
    for name, value in (("email", email), ("subject", "SmokeTest")):
        parts.append(
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode()
        )
    parts.append(
        (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
            f"Content-Type: application/pdf\r\n\r\n"
        ).encode()
        + pdf_bytes
        + b"\r\n"
    )
    parts.append(f"--{boundary}--\r\n".encode())
    body = b"".join(parts)
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": f"multipart/form-data; boundary={boundary}",
    }
    request = urllib.request.Request(
        BASE + "/documents/upload", data=body, headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw)
        except Exception:
            payload = {"detail": raw[:200]}
        return e.code, payload


def make_pdf(text: str) -> bytes:
    safe = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = f"BT /F1 12 Tf 10 50 Td ({safe}) Tj ET\n".encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 144] "
            b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>"
        ),
        b"<< /Length "
        + str(len(stream)).encode("ascii")
        + b" >>\nstream\n"
        + stream
        + b"endstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out.extend(f"{i} 0 obj\n".encode("ascii"))
        out.extend(obj)
        out.extend(b"\nendobj\n")
    xref_pos = len(out)
    out.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    out.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        out.extend(f"{off:010d} 00000 n \n".encode("ascii"))
    out.extend(
        f"trailer<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode(
            "ascii"
        )
    )
    return bytes(out)


def token_shape_ok(payload: dict) -> bool:
    t = payload.get("access_token")
    return isinstance(t, str) and "." in t and len(t) > 20


def main():
    stamp = int(time.time())
    email_a = f"smoke.a.{stamp}@example.edu"
    email_b = f"smoke.b.{stamp}@example.edu"
    password = f"Sm0keTest!{stamp % 10000}"
    # never print password

    # Stage 1 quick re-check
    code, data, err = req("GET", "/health")
    record("S1", "GET /health", code == 200 and data.get("status") == "healthy", f"http={code}")
    code, data, err = req("GET", "/health/database")
    record(
        "S1",
        "GET /health/database",
        code == 200 and data.get("status") == "connected",
        f"http={code} db={data.get('status')} name={data.get('database_name')}",
    )

    # Stage 2 auth
    code, data, err = req(
        "POST",
        "/auth/register",
        {"name": "Smoke A", "email": email_a, "password": password},
    )
    tok_a = data.get("access_token") if code in (200, 201) else None
    record(
        "S2",
        "register Student A",
        code == 200 and token_shape_ok(data) and data.get("persistence") == "mongo",
        f"http={code} persistence={data.get('persistence')}",
    )

    code, data, err = req(
        "POST",
        "/auth/register",
        {"name": "Smoke A", "email": email_a, "password": password},
    )
    record("S2", "duplicate register rejected", code == 409, f"http={code}")

    code, data, err = req(
        "POST", "/auth/login", {"email": email_a, "password": password}
    )
    if code == 200 and token_shape_ok(data):
        tok_a = data.get("access_token")
    record("S2", "login correct password", code == 200 and token_shape_ok(data), f"http={code}")

    code, data, err = req(
        "POST", "/auth/login", {"email": email_a, "password": "WrongPass!!!"}
    )
    record("S2", "login wrong password", code == 401, f"http={code}")

    code, data, err = req("POST", "/auth/register", {"name": "", "email": "bad", "password": "x"})
    record("S2", "register invalid input", code in (422, 400), f"http={code}")

    code, data, err = req("GET", f"/student/{email_a}")
    record("S2", "protected without token", code == 401, f"http={code}")

    code, data, err = req("GET", f"/student/{email_a}", token="not.a.valid.token")
    record("S2", "protected with invalid token", code == 401, f"http={code}")

    code, data, err = req("GET", "/auth/me", token=tok_a)
    record(
        "S2",
        "GET /auth/me",
        code == 200 and data.get("email") == email_a,
        f"http={code}",
    )

    code, data, err = req("POST", "/auth/logout", token=tok_a)
    record(
        "S2",
        "logout acknowledges client discard",
        code == 200 and "Discard" in str(data.get("message", "")),
        f"http={code}",
    )
    # token still works until expiry (stateless) — document that
    code, data, err = req("GET", "/auth/me", token=tok_a)
    record(
        "S2",
        "logout does NOT revoke server-side (stateless)",
        code == 200,
        f"http={code} (expected still valid until expiry)",
    )

    # Stage 3 persistence
    profile = {
        "email": email_a,
        "age": 20,
        "course": "BTech",
        "branch": "CSE",
        "year": 3,
        "subjects": ["ML", "OS"],
        "study_hours": 4.0,
        "attendance": 85.0,
        "previous_cgpa": 8.2,
    }
    code, data, err = req("POST", "/student/profile", profile, token=tok_a)
    record(
        "S3",
        "save profile",
        code == 200 and data.get("persistence") == "mongo",
        f"http={code} persistence={data.get('persistence')}",
    )
    code, data, err = req("GET", f"/student/{email_a}", token=tok_a)
    record(
        "S3",
        "reload profile",
        code == 200 and data.get("course") == "BTech" and data.get("email") == email_a,
        f"http={code}",
    )

    # Stage 4 ownership — create B
    code, data, err = req(
        "POST",
        "/auth/register",
        {"name": "Smoke B", "email": email_b, "password": password},
    )
    tok_b = data.get("access_token") if code == 200 else None
    record("S4", "register Student B", code == 200 and bool(tok_b), f"http={code}")

    # A creates plan/prediction/progress/doc
    pred_payload = {
        "email": email_a,
        "Hours_Studied": 20.0,
        "Attendance": 85.0,
        "Previous_Scores": 78.0,
        "Sleep_Hours": 7.0,
        "Tutoring_Sessions": 2.0,
        "Physical_Activity": 3.0,
        "Parental_Involvement": "Medium",
        "Access_to_Resources": "Medium",
        "Extracurricular_Activities": "Yes",
        "Motivation_Level": "Medium",
        "Internet_Access": "Yes",
        "Family_Income": "Medium",
        "Teacher_Quality": "Medium",
        "School_Type": "Public",
        "Peer_Influence": "Positive",
        "Learning_Disabilities": "No",
        "Parental_Education_Level": "College",
        "Distance_from_Home": "Near",
        "Gender": "Female",
    }
    code, data, err = req("POST", "/predict/exam-score", pred_payload, token=tok_a)
    record("S4", "A prediction", code == 200 and "predicted_exam_score" in data, f"http={code}")

    plan_body = {
        "email": email_a,
        "daily_study_hours": 3.0,
        "daily_available_hours": 4.0,
        "preferred_start_time": "09:00",
        "days_to_plan": 3,
        "subjects": [
            {
                "name": "Machine Learning",
                "difficulty": "High",
                "current_score": 60.0,
                "target_score": 85.0,
            }
        ],
        "risk_category": "Moderate Risk",
    }
    code, data, err = req("POST", "/study-plan/generate", plan_body, token=tok_a)
    record("S4", "A study plan", code == 200 and "timetable" in data, f"http={code}")

    code, data, err = req(
        "POST",
        "/performance/session",
        {
            "email": email_a,
            "subject": "Machine Learning",
            "topic": "Regression",
            "status": "completed",
            "planned_minutes": 50,
            "actual_minutes": 45,
            "date": "2026-10-12",
        },
        token=tok_a,
    )
    record("S4", "A progress session", code == 200 and data.get("persistence") == "mongo", f"http={code}")

    pdf = make_pdf("Gradient descent minimizes the loss function using learning rate.")
    code, data = upload_pdf(tok_a, email_a, pdf)
    doc_id = data.get("document_id") if code == 200 else None
    record("S4", "A PDF upload", code == 200 and bool(doc_id), f"http={code}")

    # B attempts on A's resources
    checks = [
        ("GET", f"/student/{email_a}", None, "B GET A profile"),
        ("GET", f"/predict/history/{email_a}", None, "B GET A predictions"),
        ("GET", f"/study-plan/{email_a}", None, "B GET A study plan"),
        ("GET", f"/performance/{email_a}", None, "B GET A performance"),
        ("GET", f"/documents?email={email_a}", None, "B LIST A documents via query"),
    ]
    for method, path, body, label in checks:
        code, data, err = req(method, path, body, token=tok_b)
        ok = code == 403
        record("S4", label, ok, f"http={code}")

    # B spoofing body email as A on profile update
    spoof = dict(profile)
    spoof["email"] = email_a
    spoof["name"] = "Hacked"
    code, data, err = req("POST", "/student/profile", spoof, token=tok_b)
    record("S4", "B spoof profile email as A", code == 403, f"http={code}")

    if doc_id:
        code, data, err = req(
            "GET", f"/documents/{doc_id}?email={email_a}", token=tok_b
        )
        record("S4", "B GET A document metadata", code in (403, 404), f"http={code}")
        code, data = upload_pdf(tok_b, email_a, pdf, "intrude.pdf")
        record("S4", "B upload claiming A email", code == 403, f"http={code}")

    # Stage 5 features (API-level)
    code, data, err = req("GET", f"/student/{email_a}", token=tok_a)
    record("S5", "Profile reload", code == 200 and data.get("branch") == "CSE", f"http={code}")

    code, data, err = req("POST", "/predict/exam-score", pred_payload, token=tok_a)
    record(
        "S5",
        "ML prediction",
        code == 200 and isinstance(data.get("predicted_exam_score"), (int, float)),
        f"http={code} score={data.get('predicted_exam_score')}",
    )

    code, data, err = req("GET", f"/study-plan/{email_a}", token=tok_a)
    record(
        "S5",
        "Study plan load",
        code == 200 and (data.get("plan") is not None or data.get("timetable") is not None or "plan" in data),
        f"http={code} keys={list(data.keys())[:6]}",
    )

    code, data, err = req("GET", f"/performance/{email_a}", token=tok_a)
    record(
        "S5",
        "Progress load",
        code == 200 and data.get("total_sessions", 0) >= 1,
        f"http={code} sessions={data.get('total_sessions')}",
    )

    if doc_id:
        code, data, err = req(
            "POST",
            f"/documents/{doc_id}/index?email={email_a}",
            token=tok_a,
        )
        record("S5", "PDF index", code == 200 and data.get("status") in ("indexed", "unchanged"), f"http={code} status={data.get('status')}")

        code, data, err = req(
            "POST",
            "/documents/rag/ask",
            {
                "email": email_a,
                "question": "What does gradient descent minimize?",
                "document_id": doc_id,
                "top_k": 3,
            },
            token=tok_a,
        )
        answer = str(data.get("answer") or "").lower()
        record(
            "S5",
            "PDF/RAG ask",
            code == 200 and data.get("grounded") is not False and ("loss" in answer or "gradient" in answer or data.get("mode") in ("retrieval_only", "llm")),
            f"http={code} mode={data.get('mode')} grounded={data.get('grounded')}",
        )

    code, data, err = req(
        "POST",
        "/ai/tutor",
        {"question": "Explain polymorphism in one sentence.", "email": email_a},
        token=tok_a,
    )
    record(
        "S5",
        "Gemini study generation",
        code == 200 and len(str(data.get("answer") or "")) > 10,
        f"http={code} provider={data.get('provider')} model={data.get('model_used')}",
    )

    # Flashcards via tutor JSON prompt (same API hub uses)
    fc_q = (
        'Create 3 study flashcards for: Binary search trees.\n'
        'Return ONLY valid JSON (no markdown prose outside JSON) in this shape:\n'
        '{"cards":[{"front":"...","back":"..."}]}'
    )
    code, data, err = req(
        "POST",
        "/ai/tutor",
        {"question": fc_q, "email": email_a, "subject": "Binary search trees"},
        token=tok_a,
    )
    answer = data.get("answer") or ""
    parsed_ok = '"cards"' in answer or '"front"' in answer
    record(
        "S5",
        "Flashcards generation (tutor JSON)",
        code == 200 and parsed_ok,
        f"http={code} has_cards_json={parsed_ok}",
    )

    # Summary
    failed = [r for r in RESULTS if r[2] == "FAIL"]
    print("\n=== SUMMARY ===")
    print(f"total={len(RESULTS)} pass={len(RESULTS)-len(failed)} fail={len(failed)}")
    print(f"student_a={email_a}")
    print(f"student_b={email_b}")
    # Write machine-readable results without tokens
    out = Path(__file__).resolve().parent / "m10_smoke_results.json"
    out.write_text(
        json.dumps(
            {
                "email_a": email_a,
                "email_b": email_b,
                "results": [
                    {"stage": a, "name": b, "status": c, "detail": d} for a, b, c, d in RESULTS
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"results_file={out}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
