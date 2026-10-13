import atexit
import os
import re
import socket
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI")
DATABASE_NAME = os.getenv("DATABASE_NAME", "studyai")

# Optional CA bundle path (verification stays enabled). Does not disable TLS.
try:
    import certifi

    _TLS_CA_FILE: Optional[str] = certifi.where()
except Exception:
    _TLS_CA_FILE = None


def _client_kwargs() -> Dict[str, Any]:
    kwargs: Dict[str, Any] = {
        "serverSelectionTimeoutMS": 5000,
        "connectTimeoutMS": 5000,
        "socketTimeoutMS": 10000,
    }
    if _TLS_CA_FILE:
        kwargs["tlsCAFile"] = _TLS_CA_FILE
    return kwargs


try:
    if not MONGODB_URI or not str(MONGODB_URI).strip():
        raise ValueError("MONGODB_URI is missing or empty")

    client = MongoClient(MONGODB_URI, **_client_kwargs())
    db = client[DATABASE_NAME]
    users_collection = db["users"]
    students_collection = db["students"]
    predictions_collection = db["predictions"]
    study_plans_collection = db["study_plans"]
    sessions_collection = db["sessions"]
    quizzes_collection = db["quizzes"]
    notes_collection = db["notes"]
    documents_collection = db["documents"]
except Exception as e:
    print(f"Warning: MongoDB client initialization error: {type(e).__name__}")
    client = None
    db = None
    users_collection = None
    students_collection = None
    predictions_collection = None
    study_plans_collection = None
    sessions_collection = None
    quizzes_collection = None
    notes_collection = None
    documents_collection = None


def close_mongo_client() -> None:
    """Idempotent MongoClient shutdown (lifespan + atexit / unittest process exit)."""
    global client
    if client is None:
        return
    try:
        client.close()
    except Exception as exc:
        print(f"Warning: MongoClient close failed: {type(exc).__name__}")
    finally:
        # Keep module-level `client` as the closed instance for status introspection;
        # do not recreate here.
        pass


if client is not None:
    atexit.register(close_mongo_client)


def _redact_error_message(message: str) -> str:
    """Strip credentials / URI-like secrets from diagnostic messages."""
    text = str(message or "")
    text = re.sub(r"mongodb(\+srv)?://[^\s\"']+", "mongodb://***", text, flags=re.IGNORECASE)
    text = re.sub(r"(?i)(password|pwd|pass)=([^,\s&]+)", r"\1=***", text)
    text = re.sub(r"(?i)//([^:@/]+):([^@/]+)@", "//***:***@", text)
    return text[:240]


def _extract_srv_hostname(uri: str) -> Optional[str]:
    if not uri:
        return None
    match = re.match(r"mongodb\+srv://([^@]+@)?([^/?]+)", uri.strip())
    if match:
        return match.group(2)
    # Standard mongodb:// may include host:port list — take first host
    try:
        parsed = urlparse(uri.replace("mongodb://", "http://", 1))
        return parsed.hostname
    except Exception:
        return None


def diagnose_mongodb_connectivity() -> Dict[str, Any]:
    """
    Staged connectivity report for operators.
    Never returns the URI, username, or password.
    """
    stages = []
    summary_status = "failed"
    failure_stage = None
    recommendations = []

    def add_stage(name: str, status: str, detail: str = "") -> None:
        nonlocal failure_stage, summary_status
        entry = {"stage": name, "status": status}
        if detail:
            entry["detail"] = _redact_error_message(detail)
        stages.append(entry)
        if status == "failed" and failure_stage is None:
            failure_stage = name
            summary_status = "failed"

    # Stage 1: env / URI presence
    uri = (MONGODB_URI or "").strip()
    if not uri:
        add_stage("uri_loaded", "failed", "MONGODB_URI is missing from environment/.env")
        recommendations.append("Set MONGODB_URI in backend/.env (do not commit secrets).")
        return _finalize_diagnosis(stages, summary_status, failure_stage, recommendations)

    is_srv = uri.startswith("mongodb+srv://")
    host = _extract_srv_hostname(uri)
    add_stage(
        "uri_loaded",
        "ok",
        f"scheme={'mongodb+srv' if is_srv else 'mongodb'}; host_configured={bool(host)}; "
        f"atlas_hostname={'yes' if host and 'mongodb.net' in host else 'unknown'}",
    )

    # Stage 2: client object
    if client is None:
        add_stage("client_initialized", "failed", "MongoClient was not created at import time")
        recommendations.append("Check backend startup logs for MongoDB client initialization errors.")
        return _finalize_diagnosis(stages, summary_status, failure_stage, recommendations)
    add_stage("client_initialized", "ok", "MongoClient object exists (lazy connect)")

    # Stage 3: DNS SRV (Atlas)
    srv_targets = []
    if is_srv and host:
        try:
            import dns.resolver

            answers = dns.resolver.resolve(f"_mongodb._tcp.{host}", "SRV")
            srv_targets = [(str(r.target).rstrip("."), int(r.port)) for r in answers]
            add_stage("dns_srv", "ok", f"resolved {len(srv_targets)} SRV target(s)")
        except Exception as exc:
            add_stage("dns_srv", "failed", f"{type(exc).__name__}: {exc}")
            recommendations.append(
                "DNS SRV lookup failed. Check local DNS/VPN and that the Atlas cluster hostname is correct."
            )
            return _finalize_diagnosis(stages, summary_status, failure_stage, recommendations)
    else:
        add_stage("dns_srv", "skipped", "Not an SRV URI or host unavailable")

    # Stage 4: TCP reachability
    tcp_ok = 0
    tcp_errors = []
    targets = srv_targets[:3] if srv_targets else []
    if not targets and host:
        targets = [(host, 27017)]
    for target_host, port in targets:
        try:
            sock = socket.create_connection((target_host, port), timeout=5)
            sock.close()
            tcp_ok += 1
        except Exception as exc:
            tcp_errors.append(f"{type(exc).__name__}")
    if targets and tcp_ok == 0:
        add_stage("tcp_connect", "failed", ", ".join(tcp_errors) or "all TCP connect attempts failed")
        recommendations.append(
            "TCP to Atlas port 27017 is blocked. Check firewall/VPN/proxy and Atlas Network Access IP allowlist."
        )
        return _finalize_diagnosis(stages, summary_status, failure_stage, recommendations)
    if targets:
        add_stage("tcp_connect", "ok", f"{tcp_ok}/{len(targets)} target(s) reachable on TCP")
    else:
        add_stage("tcp_connect", "skipped", "No TCP targets to probe")

    # Stage 5: TLS handshake (verification enabled)
    tls_ok = False
    tls_detail = ""
    if targets:
        try:
            import ssl

            probe_host, probe_port = targets[0]
            context = (
                ssl.create_default_context(cafile=_TLS_CA_FILE)
                if _TLS_CA_FILE
                else ssl.create_default_context()
            )
            raw = socket.create_connection((probe_host, probe_port), timeout=8)
            with context.wrap_socket(raw, server_hostname=probe_host) as tls_sock:
                tls_ok = True
                tls_detail = f"negotiated {tls_sock.version()}"
        except Exception as exc:
            tls_detail = f"{type(exc).__name__}: {exc}"

    if targets and not tls_ok:
        add_stage("tls_handshake", "failed", tls_detail)
        recommendations.extend(
            [
                "TLS handshake fails before MongoDB authentication. This is usually network/runtime related, not bad app credentials.",
                "In Atlas: confirm Network Access allows your current public IP (or temporarily 0.0.0.0/0 for a controlled test).",
                "Check for VPN, corporate proxy, antivirus HTTPS scanning, or firewall TLS interception.",
                "Try another network (phone hotspot) to rule out local middleboxes.",
                "If using Python 3.13 + OpenSSL 3.5, test the same URI with MongoDB Compass or mongosh on this machine.",
                "Atlas cluster must be running (not paused) and support modern TLS.",
            ]
        )
        return _finalize_diagnosis(stages, summary_status, failure_stage, recommendations)
    if targets:
        add_stage("tls_handshake", "ok", tls_detail or "TLS handshake succeeded")

    # Stage 6: PyMongo server selection + ping (auth implied by successful ping on Atlas)
    try:
        client.admin.command("ping")
        add_stage("server_selection_ping", "ok", "ping succeeded")
        summary_status = "connected"
        failure_stage = None
        recommendations.append("MongoDB connectivity looks healthy.")
    except Exception as exc:
        err_name = type(exc).__name__
        err_text = _redact_error_message(str(exc))
        add_stage("server_selection_ping", "failed", f"{err_name}: {err_text}")
        if "AuthenticationFailed" in err_name or "auth" in err_text.lower():
            recommendations.append(
                "Server was reachable but authentication failed. Rotate/update the DB user password in Atlas and .env."
            )
        elif "TLS" in err_text or "SSL" in err_text:
            recommendations.append(
                "PyMongo still fails during TLS/server selection. Prefer Compass/mongosh connectivity tests and Atlas Network Access checks."
            )
        else:
            recommendations.append(
                "PyMongo could not select a primary. Confirm the cluster is not paused and the connection string matches the cluster."
            )

    return _finalize_diagnosis(stages, summary_status, failure_stage, recommendations)


def _finalize_diagnosis(stages, summary_status, failure_stage, recommendations) -> Dict[str, Any]:
    return {
        "status": summary_status,
        "failure_stage": failure_stage,
        "database_name": DATABASE_NAME,
        "client_present": client is not None,
        "tls_ca_file_configured": bool(_TLS_CA_FILE),
        "stages": stages,
        "recommendations": recommendations,
        "persistence_note": (
            "When status is not 'connected', most MongoDB-backed features return errors (503). "
            "Registration alone may use a temporary in-memory fallback that is NOT durable "
            "across server restarts and must not be treated as production persistence."
        ),
    }


def get_database_status_summary() -> Dict[str, Any]:
    """Compact status for /health (no secrets)."""
    if client is None:
        return {
            "database": "disconnected",
            "failure_stage": "client_initialized",
            "detail": "MongoClient was not created",
        }
    try:
        client.admin.command("ping")
        return {"database": "connected", "failure_stage": None, "detail": "ping ok"}
    except Exception as exc:
        message = _redact_error_message(str(exc))
        stage = "tls_handshake" if ("SSL" in message or "TLS" in message) else "server_selection_ping"
        return {
            "database": "unreachable",
            "failure_stage": stage,
            "detail": f"{type(exc).__name__}: {message}",
        }
