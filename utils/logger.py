"""
Audit logging for generated emails and dry-run send simulation.
Sensitive fields are masked by default.
"""

from __future__ import annotations

import csv
import json
import os
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"


def mask_email(email: str) -> str:
    """Mask email for audit logs (privacy)."""
    email = (email or "").strip()
    if "@" not in email:
        return "***"
    local, _, domain = email.partition("@")
    if len(local) <= 1:
        return f"*@{domain}"
    return f"{local[0]}***@{domain}"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class AuditRecord:
    timestamp: str
    client_name: str
    invoice_number: str
    escalation_stage: int | None
    tone: str
    subject: str
    send_status: str
    overdue_days: int
    dry_run: bool
    contact_email_masked: str
    model: str


def append_audit_csv(record: AuditRecord, path: Path | None = None) -> Path:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = path or (LOG_DIR / "audit_log.csv")
    new_file = not csv_path.exists()
    row = asdict(record)
    with csv_path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(row.keys()))
        if new_file:
            writer.writeheader()
        writer.writerow(row)
    return csv_path


def append_audit_jsonl(record: AuditRecord, path: Path | None = None) -> Path:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    jsonl_path = path or (LOG_DIR / "audit_log.jsonl")
    payload = asdict(record)
    with jsonl_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    return jsonl_path


def log_generation_event(
    *,
    client_name: str,
    invoice_number: str,
    escalation_stage: int | None,
    tone: str,
    subject: str,
    send_status: str,
    overdue_days: int,
    contact_email: str,
    dry_run: bool = True,
    model: str = "",
    formats: tuple[str, ...] = ("csv", "jsonl"),
) -> dict[str, str]:
    """
    Persist an audit record. Returns paths written.

    NOTE: We intentionally do not log full email bodies in CSV/JSONL to reduce sensitive data retention.
    Subject line is logged as a business audit artifact; keep it professional and non-sensitive.
    """
    record = AuditRecord(
        timestamp=utc_now_iso(),
        client_name=client_name,
        invoice_number=invoice_number,
        escalation_stage=escalation_stage,
        tone=tone,
        subject=_scrub_subject_for_log(subject),
        send_status=send_status,
        overdue_days=int(overdue_days),
        dry_run=bool(dry_run),
        contact_email_masked=mask_email(contact_email),
        model=model or os.getenv("GEMINI_MODEL", "gemini-1.5-flash"),
    )

    out: dict[str, str] = {}
    if "csv" in formats:
        p = append_audit_csv(record)
        out["csv"] = str(p)
    if "jsonl" in formats:
        p = append_audit_jsonl(record)
        out["jsonl"] = str(p)
    return out


def _scrub_subject_for_log(subject: str) -> str:
    """Remove likely token-like secrets from subjects if users paste them."""
    text = re.sub(r"(?i)(api[_-]?key|token|password)\s*[:=]\s*\S+", "[redacted]", subject or "")
    return text[:300]


def export_generated_emails_json(rows: list[dict[str, Any]], path: Path | None = None) -> Path:
    """Export full generated email content for download (user-controlled local file)."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    out_path = path or (LOG_DIR / "generated_emails_export.json")
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
    return out_path
