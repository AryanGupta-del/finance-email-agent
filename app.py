"""
Finance Credit Follow-Up Email Agent — Streamlit UI.

Run: streamlit run app.py
"""

from __future__ import annotations

import json
import os
from datetime import date
from io import BytesIO
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from utils.email_generator import generate_follow_up_email
from utils.escalation import apply_escalation_columns
from utils.logger import LOG_DIR, export_generated_emails_json, log_generation_event
from utils.parser import add_days_overdue, load_invoice_file
from utils.ui_helpers import queue_table_column_config

load_dotenv()

SAMPLE_PATH = Path(__file__).resolve().parent / "sample_data" / "invoices.csv"


def _inject_streamlit_secrets_into_env() -> None:
    """
    Streamlit Community Cloud (and `streamlit run`) expose Deploy secrets via `st.secrets`.
    Copy into os.environ so `utils/email_generator.py` and LangChain see GEMINI_API_KEY.
    Local `.env` still works via load_dotenv() above.
    """
    try:
        sec = st.secrets
    except Exception:
        return
    for key in ("GEMINI_API_KEY", "GEMINI_MODEL", "USE_LANGCHAIN"):
        if os.getenv(key):
            continue
        try:
            if key in sec and str(sec[key]).strip():
                os.environ[key] = str(sec[key]).strip()
        except Exception:
            continue


def _inject_css() -> None:
    st.markdown(
        """
        <style>
          @import url('https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700;1,9..40,400&family=IBM+Plex+Mono:wght@400;500&display=swap');

          html, body, [class*="css"]  {
            font-family: "DM Sans", system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
          }

          :root {
            --ink: #0b1220;
            --muted: #5c6578;
            --line: rgba(15, 23, 42, 0.10);
            --card: rgba(255, 255, 255, 0.86);
            --card2: rgba(248, 250, 252, 0.92);
            --shadow: 0 14px 40px rgba(2, 6, 23, 0.10);
            --accent: #2563eb;
            --accent2: #7c3aed;
            --good: #059669;
            --warn: #d97706;
            --bad: #dc2626;
          }

          .stApp {
            background:
              radial-gradient(1200px 600px at 10% -10%, rgba(37, 99, 235, 0.18), transparent 55%),
              radial-gradient(900px 500px at 90% 0%, rgba(124, 58, 237, 0.16), transparent 50%),
              linear-gradient(180deg, #f6f8fc 0%, #eef2f7 55%, #e9eef6 100%);
          }

          .block-container {
            padding-top: 0.85rem;
            padding-bottom: 3rem;
            max-width: 1200px;
          }

          .top-brand {
            display: flex;
            align-items: center;
            gap: 0.65rem;
            margin: 0 0 0.85rem 0;
            padding: 0.35rem 0 0.15rem 0;
          }
          .top-brand-mark {
            width: 2.2rem;
            height: 2.2rem;
            border-radius: 10px;
            background: linear-gradient(135deg, #1d4ed8, #6d28d9);
            color: #fff;
            font-weight: 800;
            font-size: 0.72rem;
            display: flex;
            align-items: center;
            justify-content: center;
            letter-spacing: 0.04em;
            box-shadow: 0 8px 20px rgba(29, 78, 216, 0.35);
          }
          .top-brand-text {
            font-size: 0.78rem;
            color: #475569;
            font-weight: 700;
            letter-spacing: 0.12em;
            text-transform: uppercase;
          }
          .top-brand-sub {
            font-size: 0.82rem;
            color: #64748b;
            font-weight: 500;
            margin-left: 0.15rem;
          }

          h1, h2, h3 {
            letter-spacing: -0.02em;
            color: var(--ink);
          }

          /* Sidebar polish (avoid `*` text color — it makes white inputs show “blank”) */
          [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #0b1220 0%, #0f1a33 55%, #0b1220 100%);
            border-right: 1px solid rgba(255,255,255,0.08);
          }
          [data-testid="stSidebar"] h1,
          [data-testid="stSidebar"] h2,
          [data-testid="stSidebar"] h3,
          [data-testid="stSidebar"] h4,
          [data-testid="stSidebar"] .stMarkdown p,
          [data-testid="stSidebar"] .stMarkdown li,
          [data-testid="stSidebar"] [data-testid="stCaption"] {
            color: rgba(255,255,255,0.88) !important;
          }
          [data-testid="stSidebar"] .stMarkdown a { color: #93c5fd !important; }
          [data-testid="stSidebar"] label,
          [data-testid="stSidebar"] [data-testid="stWidgetLabel"] p,
          [data-testid="stSidebar"] [data-testid="stWidgetLabel"] span {
            color: rgba(255,255,255,0.78) !important;
          }
          [data-testid="stSidebar"] hr {
            border-color: rgba(255,255,255,0.12);
          }
          /* Inputs must stay dark-on-light so date + model values remain visible */
          [data-testid="stSidebar"] input,
          [data-testid="stSidebar"] textarea,
          [data-testid="stSidebar"] [data-baseweb="input"] input {
            background-color: #ffffff !important;
            color: #0f172a !important;
            -webkit-text-fill-color: #0f172a !important;
            caret-color: #0f172a !important;
            border: 1px solid rgba(15, 23, 42, 0.18) !important;
          }
          [data-testid="stSidebar"] [data-baseweb="input"] {
            background-color: #ffffff !important;
          }
          [data-testid="stSidebar"] [data-baseweb="radio"] label {
            color: rgba(255,255,255,0.88) !important;
          }
          [data-testid="stSidebar"] [data-baseweb="select"] > div {
            background-color: #ffffff !important;
            color: #0f172a !important;
            border: 1px solid rgba(15, 23, 42, 0.18) !important;
          }

          /* Hero */
          .hero {
            position: relative;
            overflow: hidden;
            border: 1px solid var(--line);
            background: linear-gradient(145deg, rgba(255,255,255,0.97), rgba(248,250,252,0.88));
            box-shadow: 0 18px 48px rgba(15, 23, 42, 0.08);
            border-radius: 20px;
            padding: 0;
            margin: 0.15rem 0 1.25rem 0;
          }
          .hero::before {
            content: "";
            position: absolute;
            left: 0;
            top: 0;
            bottom: 0;
            width: 5px;
            background: linear-gradient(180deg, #1d4ed8, #6d28d9);
            border-radius: 20px 0 0 20px;
          }
          .hero-inner { padding: 1.35rem 1.4rem 1.25rem 1.5rem; }
          .hero-kicker {
            font-size: 0.78rem;
            color: #64748b;
            font-weight: 700;
            letter-spacing: 0.11em;
            text-transform: uppercase;
          }
          .hero-title {
            margin: 0.4rem 0 0.4rem 0;
            font-size: 2.15rem;
            line-height: 1.08;
            font-weight: 800;
            letter-spacing: -0.03em;
            color: #0f172a;
          }
          .hero-title span {
            background: linear-gradient(90deg, #1e3a8a, #5b21b6);
            -webkit-background-clip: text;
            background-clip: text;
            color: transparent;
          }
          .hero-sub {
            margin: 0;
            color: #475569;
            font-size: 1.03rem;
            line-height: 1.55;
            max-width: 76ch;
          }
          .hero-badges { display:flex; flex-wrap:wrap; gap:0.5rem; margin-top:0.85rem; }
          .badge {
            display:inline-flex;
            align-items:center;
            gap:0.45rem;
            padding: 0.35rem 0.65rem;
            border-radius: 999px;
            border: 1px solid var(--line);
            background: rgba(255,255,255,0.75);
            font-size: 0.86rem;
            color: #0f172a;
            font-weight: 600;
          }
          .dot { width:8px; height:8px; border-radius:999px; display:inline-block; }
          .dot.ok { background: var(--good); }
          .dot.bad { background: var(--bad); }
          .dot.neu { background: #64748b; }

          /* Metric cards */
          .metric-grid { display:grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 0.75rem; }
          @media (max-width: 1100px) { .metric-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
          @media (max-width: 640px) { .metric-grid { grid-template-columns: 1fr; } }

          .metric-card {
            border: 1px solid var(--line);
            background: linear-gradient(145deg, rgba(255,255,255,0.95), rgba(248,250,252,0.92));
            border-radius: 16px;
            padding: 1rem 1.05rem;
            box-shadow: 0 10px 26px rgba(2, 6, 23, 0.07);
            min-height: 104px;
          }
          .metric-label {
            font-size: 0.74rem;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            color: #64748b;
            font-weight: 700;
          }
          .metric-value {
            margin-top: 0.35rem;
            font-size: 1.85rem;
            font-weight: 800;
            color: #0f172a;
            line-height: 1.05;
          }
          .metric-hint { margin-top: 0.35rem; color: #64748b; font-size: 0.86rem; line-height: 1.25; }

          .section-title {
            display:flex;
            align-items: baseline;
            justify-content: space-between;
            gap: 1rem;
            margin: 0.25rem 0 0.65rem 0;
          }
          .section-title h3 { margin: 0; font-size: 1.12rem; font-weight: 700; color: #0f172a; }
          .section-title span { color: #64748b; font-size: 0.9rem; font-weight: 500; }

          .app-footer {
            text-align: center;
            color: #64748b;
            font-size: 0.8rem;
            padding: 2.25rem 0.5rem 0.75rem 0.5rem;
            margin-top: 1.5rem;
            border-top: 1px solid rgba(15, 23, 42, 0.08);
            letter-spacing: 0.02em;
          }
          .app-footer strong { color: #334155; font-weight: 600; }

          .panel {
            border: 1px solid var(--line);
            background: rgba(255,255,255,0.78);
            border-radius: 16px;
            padding: 1rem 1rem;
            box-shadow: 0 10px 26px rgba(2, 6, 23, 0.05);
          }

          /* Primary buttons */
          div.stButton > button[kind="primary"] {
            border: none !important;
            background: linear-gradient(135deg, #2563eb, #4f46e5) !important;
            box-shadow: 0 12px 26px rgba(37, 99, 235, 0.28);
            font-weight: 700 !important;
          }
          div.stButton > button[kind="primary"]:hover {
            filter: brightness(1.03);
            transform: translateY(-1px);
          }

          /* Secondary buttons */
          div.stButton > button[kind="secondary"] {
            border: 1px solid var(--line) !important;
            background: rgba(255,255,255,0.85) !important;
            font-weight: 650 !important;
          }

          /* Tabs */
          .stTabs [data-baseweb="tab-list"] {
            gap: 8px;
            background: rgba(255,255,255,0.55);
            border: 1px solid var(--line);
            border-radius: 14px;
            padding: 6px;
          }
          .stTabs [data-baseweb="tab"] {
            border-radius: 12px;
            padding: 0.55rem 0.85rem;
            font-weight: 700;
          }

          /* Dataframe container */
          div[data-testid="stDataFrame"] { border-radius: 14px; overflow: hidden; }

          /* Expander */
          details { border-radius: 14px !important; border: 1px solid var(--line) !important; }
          summary { font-weight: 700 !important; }

          /* Mono bits */
          code, textarea {
            font-family: "IBM Plex Mono", ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace !important;
          }

          /* Hide Streamlit menu + footer for a cleaner portfolio look */
          #MainMenu {visibility: hidden;}
          footer {visibility: hidden;}
          header[data-testid="stHeader"] {background: transparent;}
        </style>
        """,
        unsafe_allow_html=True,
    )


def _api_key_configured() -> bool:
    return bool(os.getenv("GEMINI_API_KEY", "").strip())


def _prepare_df(raw: pd.DataFrame, as_of: date) -> pd.DataFrame:
    df = add_days_overdue(raw, as_of=as_of)
    df = apply_escalation_columns(df)
    return df


def _hero(*, key_ok: bool, dry_run: bool, page: str) -> None:
    if page == "Audit & exports":
        sub = "Immutable audit trail, exports, and compliance-friendly previews."
    else:
        sub = (
            "Deterministic collections policy engine with AI-assisted drafting. "
            "Stages 1–4 use Gemini (via LangChain); stage 5 routes to manual / legal review."
        )
    st.markdown(
        f"""
        <div class="hero">
          <div class="hero-inner">
            <div class="hero-kicker">Accounts receivable · collections copilot</div>
            <div class="hero-title"><span>Finance Credit Follow-Up</span> Email Agent</div>
            <p class="hero-sub">{sub}</p>
            <div class="hero-badges">
              <span class="badge"><span class="dot {'ok' if dry_run else 'neu'}"></span>Dispatch mode: {'dry run (simulated)' if dry_run else 'live send off (demo)'}</span>
              <span class="badge"><span class="dot {'ok' if key_ok else 'bad'}"></span>LLM credentials: {'operational' if key_ok else 'not configured'}</span>
              <span class="badge"><span class="dot neu"></span>PII-aware logging · masked contacts in audit files</span>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _metric_cards(*, total: int, overdue: int, eligible: int, flagged: int) -> None:
    st.markdown(
        f"""
        <div class="metric-grid">
          <div class="metric-card">
            <div class="metric-label">Dataset</div>
            <div class="metric-value">{total:,}</div>
            <div class="metric-hint">Total invoice rows loaded</div>
          </div>
          <div class="metric-card">
            <div class="metric-label">Overdue</div>
            <div class="metric-value">{overdue:,}</div>
            <div class="metric-hint">Past due as of selected date</div>
          </div>
          <div class="metric-card">
            <div class="metric-label">AI drafts</div>
            <div class="metric-value">{eligible:,}</div>
            <div class="metric-hint">Stages 1–4 eligible for Gemini</div>
          </div>
          <div class="metric-card">
            <div class="metric-label">Flagged</div>
            <div class="metric-value">{flagged:,}</div>
            <div class="metric-hint">Stage 5 · manual / legal review</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _section_title(title: str, subtitle: str = "") -> None:
    sub = f"<span>{subtitle}</span>" if subtitle else "<span></span>"
    st.markdown(
        f'<div class="section-title"><h3>{title}</h3>{sub}</div>',
        unsafe_allow_html=True,
    )


def _app_footer() -> None:
    st.markdown(
        """
        <div class="app-footer">
          <strong>Finance Credit Follow-Up Email Agent</strong> · Portfolio prototype v1.0 ·
          Rule-based escalation · Gemini + LangChain · Dry-run by default · Not for production legal use
        </div>
        """,
        unsafe_allow_html=True,
    )


def _top_brand_strip() -> None:
    st.markdown(
        """
        <div class="top-brand">
          <div class="top-brand-mark">AR</div>
          <div>
            <span class="top-brand-text">Receivables console</span>
            <span class="top-brand-sub">Invoice queue · policy · audit</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    st.set_page_config(
        page_title="Receivables Follow-Up Agent",
        layout="wide",
        initial_sidebar_state="expanded",
        page_icon="📊",
    )
    _inject_streamlit_secrets_into_env()
    _inject_css()

    with st.sidebar:
        st.markdown(
            """
            <div style="margin-bottom:0.75rem;">
              <div style="font-size:1.05rem;font-weight:800;color:#f8fafc;letter-spacing:-0.02em;">Receivables</div>
              <div style="font-size:0.78rem;color:rgba(248,250,252,0.65);font-weight:600;text-transform:uppercase;letter-spacing:0.14em;">Control tower</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.caption("Collections queue · policy · audit exports")
        page = st.radio(
            "Navigation",
            ["Workbench", "Audit & exports"],
            label_visibility="collapsed",
        )

        st.divider()
        st.markdown("#### Run settings")
        as_of = st.date_input("As-of date (for days overdue)", value=date.today())
        dry_run = st.toggle(
            "Dry run (simulate sends)",
            value=True,
            help="When enabled, no real email is sent. This is the safe default.",
        )
        st.caption(
            "Production should gate real sending behind approvals plus SMTP or a transactional email API."
        )

        st.divider()
        st.markdown("#### Model")
        model_default = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
        model = st.text_input("Gemini model id", value=model_default, label_visibility="visible")

        st.divider()
        st.markdown("#### Security status")
        key_ok = _api_key_configured()
        st.markdown(
            f'<span class="badge" style="background: rgba(255,255,255,0.10); border-color: rgba(255,255,255,0.16); color: rgba(255,255,255,0.92);">'
            f'<span class="dot {"ok" if key_ok else "bad"}"></span>API key: {"configured" if key_ok else "missing"}</span>',
            unsafe_allow_html=True,
        )
        if not key_ok:
            st.warning("Create `.env` from `.env.example` and set `GEMINI_API_KEY`.")

    _top_brand_strip()
    _hero(key_ok=key_ok, dry_run=dry_run, page=page)

    if page == "Audit & exports":
        _section_title("Audit & exports", "Download artifacts generated on this machine")
        col1, col2 = st.columns(2)
        audit_csv = LOG_DIR / "audit_log.csv"
        audit_jsonl = LOG_DIR / "audit_log.jsonl"
        export_json = LOG_DIR / "generated_emails_export.json"

        with col1:
            with st.container(border=True):
                st.markdown("**Audit log (CSV)**")
                st.caption("Masked emails · no bodies · append-only trail")
                if audit_csv.exists():
                    st.download_button(
                        "Download CSV",
                        data=audit_csv.read_bytes(),
                        file_name="audit_log.csv",
                        mime="text/csv",
                        use_container_width=True,
                        type="primary",
                    )
                else:
                    st.info("No `logs/audit_log.csv` yet — generate emails on Workbench first.")

        with col2:
            with st.container(border=True):
                st.markdown("**Audit log (JSONL)**")
                st.caption("One JSON object per line · easy pipelines")
                if audit_jsonl.exists():
                    st.download_button(
                        "Download JSONL",
                        data=audit_jsonl.read_bytes(),
                        file_name="audit_log.jsonl",
                        mime="application/json",
                        use_container_width=True,
                    )
                else:
                    st.info("No `logs/audit_log.jsonl` yet — generate emails on Workbench first.")

        st.divider()
        with st.container(border=True):
            st.markdown("**Generated emails export (JSON)**")
            st.caption("Includes full bodies from the most recent generation batch")
            if export_json.exists():
                st.download_button(
                    "Download JSON export",
                    data=export_json.read_bytes(),
                    file_name="generated_emails_export.json",
                    mime="application/json",
                    use_container_width=True,
                )
            else:
                st.info("No export yet — run generation on Workbench.")

        if audit_csv.exists():
            st.divider()
            _section_title("Audit preview", "Latest 50 rows · masked identifiers")
            st.dataframe(pd.read_csv(audit_csv).tail(50), use_container_width=True, hide_index=True)

        _app_footer()
        return

    # Workbench
    _section_title("Pipeline", "Load → review escalation → generate")
    colu, cold = st.columns([1.12, 0.88], gap="large")

    with colu:
        with st.container(border=True):
            st.markdown("#### 1 · Ingest invoices")
            st.caption("CSV / Excel with required columns (see README).")
            up = st.file_uploader("Upload file", type=["csv", "xlsx", "xls"], label_visibility="collapsed")
            b1, b2 = st.columns([1, 1], gap="small")
            with b1:
                if st.button("Load sample dataset", use_container_width=True, type="secondary"):
                    raw = load_invoice_file(BytesIO(SAMPLE_PATH.read_bytes()), SAMPLE_PATH.name)
                    st.session_state["raw_df"] = raw
                    st.session_state["source_name"] = str(SAMPLE_PATH.name)
                    st.toast("Sample invoices loaded", icon="✅")
            with b2:
                st.caption("Uses `sample_data/invoices.csv`")

            if up is not None:
                raw = load_invoice_file(BytesIO(up.getvalue()), up.name)
                st.session_state["raw_df"] = raw
                st.session_state["source_name"] = up.name
                st.success(f"Loaded **{up.name}**.")

    with cold:
        with st.container(border=True):
            st.markdown("#### 2 · Escalation filter")
            st.caption("Rule-based stages (the model does not choose the stage).")
            stage_opts = st.multiselect(
                "Stages to show",
                options=[1, 2, 3, 4, 5],
                default=[1, 2, 3, 4, 5],
                label_visibility="collapsed",
            )

    if "raw_df" not in st.session_state:
        with st.container(border=True):
            st.info("Upload a CSV or Excel file, or use **Load sample dataset** to load the built-in portfolio sample.")
        _app_footer()
        return

    df = _prepare_df(st.session_state["raw_df"], as_of=as_of)
    st.session_state["proc_df"] = df

    overdue_df = df[df["is_overdue"]].copy()
    flagged_df = overdue_df[overdue_df["flagged_legal_review"]].copy()
    gen_df = overdue_df[overdue_df["generate_email"]].copy()

    st.divider()
    _section_title("Executive summary", "Counts update with as-of date and filters")
    _metric_cards(total=len(df), overdue=len(overdue_df), eligible=len(gen_df), flagged=len(flagged_df))

    st.divider()
    _section_title("Escalation mix", "Distribution across overdue invoices")
    with st.container(border=True):
        if overdue_df.empty:
            st.caption("No overdue rows for the selected as-of date.")
        else:
            mix = overdue_df["escalation_stage"].value_counts().sort_index()
            st.bar_chart(mix.to_frame(name="invoice_count"), height=320)

    view_df = overdue_df.copy()
    if stage_opts:
        view_df = view_df[view_df["escalation_stage"].isin(stage_opts)]

    st.divider()
    _section_title("Invoice queue", "Overdue rows + policy outputs")
    display_cols = [
        "invoice_number",
        "client_name",
        "amount_due",
        "due_date",
        "days_overdue",
        "escalation_stage",
        "tone",
        "follow_up_count",
        "flagged_legal_review",
        "generate_email",
        "contact_email",
    ]
    with st.container(border=True):
        st.dataframe(
            view_df[display_cols].sort_values(["escalation_stage", "days_overdue"], ascending=[True, False]),
            use_container_width=True,
            hide_index=True,
            height=380,
            column_config=queue_table_column_config(),
        )

    st.divider()
    with st.container(border=True):
        st.markdown("#### 3 · Generate follow-up drafts")
        st.caption("Stage 5 invoices are logged as flagged and **skipped** for LLM drafting.")
        gen_disabled = not _api_key_configured()
        if st.button(
            "Generate emails for eligible overdue invoices",
            type="primary",
            disabled=gen_disabled,
            use_container_width=True,
        ):
            results: list[dict] = []
            flagged_rows = flagged_df.to_dict("records")
            gen_rows = gen_df.sort_values(["escalation_stage", "days_overdue"], ascending=[False, False]).to_dict(
                "records"
            )

            if len(flagged_rows) + len(gen_rows) == 0:
                st.warning("No overdue invoices to process for this as-of date.")
            else:
                with st.spinner("Generating personalised drafts and writing audit records…"):
                    progress = st.progress(0, text="Starting…")
                    total = len(flagged_rows) + len(gen_rows)
                    done = 0

                    for r in flagged_rows:
                        log_generation_event(
                            client_name=str(r["client_name"]),
                            invoice_number=str(r["invoice_number"]),
                            escalation_stage=int(r["escalation_stage"]) if pd.notna(r["escalation_stage"]) else None,
                            tone=str(r["tone"]),
                            subject="",
                            send_status="FLAGGED_LEGAL_REVIEW",
                            overdue_days=int(r["days_overdue"]),
                            contact_email=str(r["contact_email"]),
                            dry_run=bool(dry_run),
                            model=model.strip(),
                        )
                        results.append(
                            {
                                "invoice_number": r["invoice_number"],
                                "client_name": r["client_name"],
                                "contact_email": r["contact_email"],
                                "escalation_stage": int(r["escalation_stage"]),
                                "tone": r["tone"],
                                "days_overdue": int(r["days_overdue"]),
                                "subject": "",
                                "body": "",
                                "status": "FLAGGED_LEGAL_REVIEW_NO_EMAIL",
                                "dry_run": dry_run,
                            }
                        )
                        done += 1
                        progress.progress(min(done / total, 1.0), text=f"Flagged {r['invoice_number']}…")

                    for r in gen_rows:
                        due = r["due_date"]
                        due_for_model = due.date() if hasattr(due, "date") else due
                        try:
                            gen = generate_follow_up_email(
                                client_name=str(r["client_name"]),
                                invoice_number=str(r["invoice_number"]),
                                amount_due=float(r["amount_due"]),
                                due_date=due_for_model,
                                days_overdue=int(r["days_overdue"]),
                                escalation_stage=int(r["escalation_stage"]),
                                follow_up_count=int(r["follow_up_count"]),
                                contact_email=str(r["contact_email"]),
                                payment_instructions=str(r.get("payment_instructions", "") or ""),
                                model=model.strip(),
                            )

                            send_status = "DRY_RUN_SIMULATED" if dry_run else "READY_TO_SEND_DISABLED"
                            log_generation_event(
                                client_name=str(r["client_name"]),
                                invoice_number=str(r["invoice_number"]),
                                escalation_stage=int(r["escalation_stage"]),
                                tone=str(r["tone"]),
                                subject=gen.subject,
                                send_status=send_status,
                                overdue_days=int(r["days_overdue"]),
                                contact_email=str(r["contact_email"]),
                                dry_run=bool(dry_run),
                                model=gen.model,
                            )

                            results.append(
                                {
                                    "invoice_number": r["invoice_number"],
                                    "client_name": r["client_name"],
                                    "contact_email": r["contact_email"],
                                    "escalation_stage": int(r["escalation_stage"]),
                                    "tone": r["tone"],
                                    "days_overdue": int(r["days_overdue"]),
                                    "subject": gen.subject,
                                    "body": gen.body,
                                    "status": send_status,
                                    "dry_run": dry_run,
                                    "model": gen.model,
                                }
                            )
                        except Exception as e:
                            err = str(e)
                            log_generation_event(
                                client_name=str(r["client_name"]),
                                invoice_number=str(r["invoice_number"]),
                                escalation_stage=int(r["escalation_stage"]),
                                tone=str(r["tone"]),
                                subject="",
                                send_status=f"ERROR: {err[:120]}",
                                overdue_days=int(r["days_overdue"]),
                                contact_email=str(r["contact_email"]),
                                dry_run=bool(dry_run),
                                model=model.strip(),
                            )
                            results.append(
                                {
                                    "invoice_number": r["invoice_number"],
                                    "client_name": r["client_name"],
                                    "contact_email": r["contact_email"],
                                    "escalation_stage": int(r["escalation_stage"]),
                                    "tone": r["tone"],
                                    "days_overdue": int(r["days_overdue"]),
                                    "subject": "",
                                    "body": "",
                                    "status": f"ERROR: {err}",
                                    "dry_run": dry_run,
                                }
                            )

                        done += 1
                        progress.progress(min(done / total, 1.0), text=f"Processed {r['invoice_number']}…")

                    progress.progress(1.0, text="Done.")
                    st.session_state["last_results"] = results
                    export_generated_emails_json(results)
                    st.success("Generation complete — audit entries appended under `logs/`.")

    if "last_results" in st.session_state:
        res = st.session_state["last_results"]
        st.divider()
        _section_title("Latest output", "Review drafts, flags, and errors from the last run")

        gen_only = [x for x in res if x.get("subject")]
        flagged_only = [x for x in res if x.get("status") == "FLAGGED_LEGAL_REVIEW_NO_EMAIL"]
        errs = [x for x in res if str(x.get("status", "")).startswith("ERROR")]

        t1, t2, t3 = st.tabs(["Generated emails", "Flagged (Stage 5)", "Errors"])
        with t1:
            if not gen_only:
                st.info("No generated emails in the last run.")
            for item in gen_only:
                title = f"{item['invoice_number']} — {item['subject']}"
                with st.expander(title, expanded=False):
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        st.metric("Stage", int(item["escalation_stage"]))
                    with c2:
                        st.metric("Days overdue", int(item["days_overdue"]))
                    with c3:
                        st.metric("Status", "Dry run" if item.get("status") == "DRY_RUN_SIMULATED" else "Queued")
                    st.markdown(f"**Recipient (not sent):** `{item['contact_email']}`")
                    st.markdown(f"**Tone:** {item['tone']}")
                    st.text_area("Email body", value=item["body"], height=240, key=f"body_{item['invoice_number']}")

        with t2:
            if not flagged_only:
                st.info("No Stage 5 flags in the last run.")
            else:
                st.dataframe(pd.DataFrame(flagged_only), use_container_width=True, hide_index=True)

        with t3:
            if not errs:
                st.success("No errors in the last run.")
            else:
                st.dataframe(pd.DataFrame(errs), use_container_width=True, hide_index=True)

        st.download_button(
            "Download last results (JSON)",
            data=json.dumps(res, ensure_ascii=False, indent=2).encode("utf-8"),
            file_name="last_generation_results.json",
            mime="application/json",
            use_container_width=True,
        )

    _app_footer()


if __name__ == "__main__":
    main()
