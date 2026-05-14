"""Reusable Streamlit column configs for professional data tables."""

from __future__ import annotations

from typing import Any

import streamlit as st


def queue_table_column_config() -> dict[str, Any]:
    """Column configuration for the overdue invoice queue."""
    return {
        "invoice_number": st.column_config.TextColumn("Invoice", width="small", help="Unique invoice identifier"),
        "client_name": st.column_config.TextColumn("Client", width="medium"),
        "amount_due": st.column_config.NumberColumn("Amount (USD)", format="%.2f", help="Outstanding balance"),
        "due_date": st.column_config.DatetimeColumn("Due date", format="YYYY-MM-DD", width="small"),
        "days_overdue": st.column_config.NumberColumn("Days overdue", format="%d", width="small"),
        "escalation_stage": st.column_config.NumberColumn("Stage", format="%d", width="small", help="1–4 auto-email; 5 manual"),
        "tone": st.column_config.TextColumn("Policy tone", width="medium"),
        "follow_up_count": st.column_config.NumberColumn("Prior follow-ups", format="%d", width="small"),
        "flagged_legal_review": st.column_config.CheckboxColumn("Legal flag", width="small"),
        "generate_email": st.column_config.CheckboxColumn("Draft email", width="small"),
        "contact_email": st.column_config.TextColumn("Contact", width="medium"),
    }
