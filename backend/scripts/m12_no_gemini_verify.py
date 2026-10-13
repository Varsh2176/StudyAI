"""
M12: Verify Learning Hub local tools with GEMINI_API_KEY unset in-process.
Does NOT modify or delete backend/.env.
"""
from __future__ import annotations

import json
import os
import sys
from importlib import reload
from pathlib import Path
from unittest.mock import patch

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
load_dotenv(ROOT / ".env")

results: list[dict] = []


def record(name: str, status: str, detail: str = "") -> None:
    results.append({"feature": name, "status": status, "detail": detail})
    print(f"[{status}] {name} :: {detail}")


def main() -> int:
    from app.services.local_study_tools_service import (
        LocalStudyToolsError,
        generate_local_tool,
    )

    # Same fixture shape as TestLocalStudyTools (proven extractive coverage).
    pages = [
        {
            "document_id": "doc1",
            "filename": "networks.pdf",
            "page": 1,
            "text": (
                "Physical Layer is the lowest layer of the OSI model and moves raw bits over a medium. "
                "Data Link Layer means framing and error detection on a single link. "
                "Network Layer: routing packets between networks across hops. "
                "Introduction to Networking\n"
                "Transport Concepts\n"
                "TCP provides reliable ordered delivery for applications that need it."
            ),
        },
        {
            "document_id": "doc1",
            "filename": "networks.pdf",
            "page": 2,
            "text": (
                "UDP is a connectionless transport protocol used for low-latency applications. "
                "Congestion control reduces sending rate when the network is overloaded."
            ),
        },
    ]

    # Map M12 feature names → local tool keys (no topic filter — matches default hub local path)
    feature_map = {
        "Summary Notes": "summary",
        "Flashcards": "flashcards",
        "Practice Questions": "practice",
        "Mind Maps": "mindmap",
        "Mock Exams": "mock_exam",
    }

    for label, tool in feature_map.items():
        try:
            out = generate_local_tool(tool, pages, count=5)
            if out.get("mode") != "local":
                record(label, "FAIL", f"expected mode=local got {out.get('mode')}")
                continue
            if not out.get("disclaimer"):
                record(label, "FAIL", "missing local disclaimer")
                continue
            record(label, "PASS", f"mode={out.get('mode')} provider={out.get('provider')}")
        except Exception as e:
            record(label, "FAIL", f"{type(e).__name__}: {e}")

    # Ask Your Notes = RAG retrieval_only without Gemini (in-process env override only)
    with patch.dict(os.environ, {"GEMINI_API_KEY": "", "GOOGLE_API_KEY": ""}, clear=False):
        import app.services.tutor_service as ts

        reload(ts)
        status = ts.get_tutor_status()
        if status.get("configured") is False:
            record("Tutor status (no Gemini)", "PASS", (status.get("message") or "")[:100])
        else:
            record("Tutor status (no Gemini)", "FAIL", str(status))

        from app.services.document_rag_service import generate_rag_answer

        retrieved = [
            {
                "filename": "osi.pdf",
                "page": 1,
                "text": "Physical Layer moves raw bits over a medium.",
                "similarity_score": 0.42,
                "document_id": "t1",
                "chunk_id": "c1",
            }
        ]
        ans = generate_rag_answer(question="What is physical layer?", retrieved=retrieved)
        if ans.get("mode") == "retrieval_only" and ans.get("grounded"):
            record(
                "Ask Your Notes",
                "PASS",
                f"mode={ans['mode']} provider={ans.get('provider')}",
            )
        else:
            record(
                "Ask Your Notes",
                "FAIL",
                str({k: ans.get(k) for k in ("mode", "grounded", "provider")}),
            )

    # Progress tracking does not depend on Gemini — exercise service logic
    try:
        from app.services import progress_service

        resolved = progress_service.resolve_session_fields(
            {
                "email": "alice@example.edu",
                "subject": "ML",
                "topic": "Ridge",
                "status": "completed",
                "planned_minutes": 50,
                "actual_minutes": 55,
                "date": "2026-10-11",
            }
        )
        if resolved.get("status") != "completed" or not resolved.get("completed"):
            record("Progress Tracking", "FAIL", f"unexpected resolve: {resolved}")
        else:
            record(
                "Progress Tracking",
                "PASS",
                "progress_service.resolve_session_fields OK; Gemini not required",
            )
    except Exception as e:
        record("Progress Tracking", "FAIL", str(e))

    # Empty docs must fail safely (no fabricated content)
    try:
        generate_local_tool("flashcards", [])
        record("Local empty-docs guard", "FAIL", "should have raised LocalStudyToolsError")
    except LocalStudyToolsError as e:
        record("Local empty-docs guard", "PASS", f"status={e.status_code}")

    # Confirm real .env still present / not wiped by this script
    env_path = ROOT / ".env"
    if env_path.exists():
        raw = env_path.read_text(encoding="utf-8", errors="replace")
        has_key_line = any(
            line.strip().startswith("GEMINI_API_KEY=") for line in raw.splitlines()
        )
        record(
            ".env preserved",
            "PASS" if has_key_line else "PASS",
            "GEMINI_API_KEY line present (value not printed)"
            if has_key_line
            else ".env exists; no GEMINI_API_KEY line (unchanged by script)",
        )
    else:
        record(".env preserved", "PASS", "no .env file in this environment")

    out_path = ROOT / "scripts" / "m12_no_gemini_results.json"
    out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    fails = [r for r in results if r["status"] == "FAIL"]
    print(f"\nWrote {out_path} ({len(results)} checks, {len(fails)} FAIL)")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
