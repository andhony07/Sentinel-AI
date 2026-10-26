"""Status header component for the server health monitoring dashboard."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

import streamlit as st

from app.dashboard.utils.formatting import format_timestamp
from app.dashboard.utils.theme import get_theme_tokens


def render_status_header(
    last_updated: Optional[datetime] = None,
    is_monitoring: bool = False,
    model_name: str = "IsolationForestDetector",
    is_model_trained: bool = False,
    db_record_count: int = 0,
    theme: Optional[str] = None,
    overall_status: Optional[str] = None,
    section_title: Optional[str] = None,
    **kwargs: Any,
) -> None:
    """Render top-level executive banner with system status indicators.

    Args:
        last_updated: Timestamp of the most recent telemetry sample.
        is_monitoring: Whether live background collection is running.
        model_name: Active ML model identifier.
        is_model_trained: True if fitted ML checkpoint loaded, False for heuristic baseline.
        db_record_count: Total persisted metric rows in SQLite.
        theme: Optional active theme ('dark' or 'light').
        overall_status: Optional system health status ('HEALTHY', 'DEGRADED', 'CRITICAL').
        section_title: Optional current active navigation section title.
        **kwargs: Additional legacy or forward-compatible keyword arguments.
    """
    active_mode = theme or kwargs.get("theme")
    tokens = get_theme_tokens(active_mode)

    col_title, col_status = st.columns([3, 2])

    with col_title:
        sec_badge = (
            f"<span style='background-color:{tokens.bg_card_secondary}; color:{tokens.accent}; border:1px solid {tokens.border_color}; "
            f"padding:2px 8px; border-radius:4px; font-size:11px; font-weight:700; margin-left:8px; vertical-align:middle; text-transform:uppercase; letter-spacing:0.5px;'>"
            f"{section_title}</span>"
            if section_title
            else ""
        )
        title_html = (
            f"<div style='margin-bottom:2px;'>"
            f"<div style='font-size:11px; font-weight:700; color:{tokens.accent}; text-transform:uppercase; letter-spacing:0.8px; margin-bottom:2px; display:flex; align-items:center; gap:6px;'>"
            f"<span>ðŸ›¡ï¸ SENTINELAI</span>"
            f"<span style='color:{tokens.text_muted};'>&bull;</span>"
            f"<span>OPERATIONS CONSOLE</span>"
            f"</div>"
            f"<h2 style='margin:0; color:{tokens.text_primary}; font-weight:700; letter-spacing:-0.4px; font-size:22px; display:inline-flex; align-items:center; flex-wrap:wrap; gap:8px;'>"
            f"<span>SentinelAI</span>"
            f"{sec_badge}"
            f"</h2>"
            f"<p style='color:{tokens.text_secondary}; font-size:12px; margin:3px 0 0 0; letter-spacing:0.1px;'>"
            f"Intelligent Server Health &amp; Failure Risk Monitoring &bull; Isolation Forest ML"
            f"</p>"
            f"</div>"
        )
        st.markdown(title_html, unsafe_allow_html=True)

    with col_status:
        # System status pill grounded in real state
        status_val = overall_status or ("OPERATIONAL" if is_model_trained else "STANDBY")
        if status_val in ("HEALTHY", "OPERATIONAL"):
            sys_pill = f"<span style='background-color:{tokens.bg_normal}; color:{tokens.color_normal}; border:1px solid {tokens.color_normal}40; padding:3px 8px; border-radius:4px; font-size:11px; font-weight:700;'>ðŸŸ¢ {status_val}</span>"
        elif status_val == "DEGRADED":
            sys_pill = f"<span style='background-color:{tokens.bg_moderate}; color:{tokens.color_moderate}; border:1px solid {tokens.color_moderate}40; padding:3px 8px; border-radius:4px; font-size:11px; font-weight:700;'>ðŸŸ¡ DEGRADED</span>"
        else:
            sys_pill = f"<span style='background-color:{tokens.bg_card_secondary}; color:{tokens.text_muted}; border:1px solid {tokens.border_color}; padding:3px 8px; border-radius:4px; font-size:11px; font-weight:700;'>âšª {status_val}</span>"

        # Worker status pill
        monitor_pill = (
            f"<span style='background-color:{tokens.bg_normal}; color:{tokens.color_normal}; border:1px solid {tokens.color_normal}30; padding:3px 8px; border-radius:4px; font-size:11px; font-weight:600;'>ðŸŸ¢ Worker: Active</span>"
            if is_monitoring
            else f"<span style='background-color:{tokens.bg_card_secondary}; color:{tokens.text_muted}; border:1px solid {tokens.border_color}; padding:3px 8px; border-radius:4px; font-size:11px; font-weight:600;'>âšª Worker: Idle</span>"
        )

        model_pill = (
            f"<span style='background-color:{tokens.bg_low}; color:{tokens.color_low}; border:1px solid {tokens.color_low}30; padding:3px 8px; border-radius:4px; font-size:11px; font-weight:600;'>ðŸ¤– ML: {model_name}</span>"
            if is_model_trained
            else f"<span style='background-color:{tokens.bg_moderate}; color:{tokens.color_moderate}; border:1px solid {tokens.color_moderate}30; padding:3px 8px; border-radius:4px; font-size:11px; font-weight:600;'>âš ï¸ Heuristic Baseline</span>"
        )

        db_pill = f"<span style='background-color:{tokens.bg_card_secondary}; color:{tokens.text_secondary}; border:1px solid {tokens.border_color}; padding:3px 8px; border-radius:4px; font-size:11px; font-weight:600;'>ðŸ—„ï¸ SQLite: {db_record_count:,}</span>"

        ts_str = format_timestamp(last_updated) if last_updated else "No Telemetry Ingested"
        status_html = (
            f"<div style='display:flex; flex-direction:column; align-items:flex-end; gap:4px; padding-top:2px;'>"
            f"<div style='display:flex; flex-wrap:wrap; justify-content:flex-end; gap:6px;'>"
            f"{sys_pill}{monitor_pill}{model_pill}{db_pill}"
            f"</div>"
            f"<div style='color: {tokens.text_muted}; font-size: 11px; margin-top: 2px;'>"
            f"Last Ingestion: <b style='color:{tokens.text_secondary}; font-variant-numeric:tabular-nums;'>{ts_str}</b>"
            f"</div>"
            f"</div>"
        )
        st.markdown(status_html, unsafe_allow_html=True)

    st.markdown(f"<hr style='margin-top: 8px; margin-bottom: 18px; border:none; border-top: 1px solid {tokens.border_color};'>", unsafe_allow_html=True)
