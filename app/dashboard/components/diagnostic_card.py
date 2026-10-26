"""Explainable diagnostic recommendations component for SentinelAI.

Renders empirical telemetry evidence, ML anomaly correlations, root-cause hypotheses,
and prioritized remediation runbooks aligned with the SentinelAI design system.
"""

from __future__ import annotations

from typing import Any, Optional

import streamlit as st

from app.dashboard.utils.theme import get_theme_tokens
from app.ml.diagnostics import DiagnosticReport, EvidenceLevel


def render_diagnostic_report(
    report: Optional[DiagnosticReport],
    theme: Optional[str] = None,
    **kwargs: Any,
) -> None:
    """Render explainable, evidence-based diagnostic recommendations and findings.

    Args:
        report: DiagnosticReport from DiagnosticEngine.
        theme: Optional active theme ('dark' or 'light').
        **kwargs: Additional legacy or forward-compatible keyword arguments.
    """
    active_mode = theme or kwargs.get("theme")
    tokens = get_theme_tokens(active_mode)

    if report is None:
        st.markdown(
            f"""<div class="sentinel-empty-state aiops-empty-state">
                <div style="font-size:28px;">ðŸ©º</div>
                <div class="title">Diagnostic Report Unavailable</div>
                <div class="desc">No diagnostic findings or root-cause evaluations are available for the current telemetry state. Capture a snapshot or execute an anomaly simulation to generate explainable findings.</div>
            </div>""",
            unsafe_allow_html=True,
        )
        return

    # Executive Headline Banner with Severity Accent
    if report.critical_count > 0:
        headline_border = tokens.color_critical
        headline_bg = tokens.bg_critical
    elif report.warning_count > 0:
        headline_border = tokens.color_moderate
        headline_bg = tokens.bg_moderate
    else:
        headline_border = tokens.color_normal
        headline_bg = tokens.bg_normal

    health_score_str = f"&nbsp;|&nbsp; <b>Health Score:</b> <code style='font-size:12px;'>{report.overall_health_score:.1f}/100</code>" if report.overall_health_score is not None else ""

    headline_html = (
        f"<div style='background-color:{headline_bg}; border:1px solid {headline_border}60; border-left:4px solid {headline_border}; "
        f"padding:14px 18px; border-radius:6px; margin-bottom:14px;'>"
        f"<div style='font-size:16px; font-weight:700; color:{tokens.text_primary};'>{report.summary_headline}</div>"
        f"<div style='font-size:12px; color:{tokens.text_secondary}; margin-top:4px;'>"
        f"<b>Primary Concern:</b> <code style='font-size:11px;'>{report.primary_concern or 'Nominal'}</code> &nbsp;|&nbsp; "
        f"<b>Evaluated Risk:</b> <span style='color:{headline_border}; font-weight:700;'>{report.risk_category.value}</span> "
        f"{health_score_str}"
        f"</div>"
        f"</div>"
    )
    st.markdown(headline_html, unsafe_allow_html=True)

    # Theme-aware severity colors and badges
    if tokens.mode == "dark":
        sev_colors = {
            EvidenceLevel.CRITICAL: ("#EF4444", "rgba(239, 68, 68, 0.20)", "ðŸ”´"),
            EvidenceLevel.HIGH: ("#F97316", "rgba(249, 115, 22, 0.20)", "ðŸŸ "),
            EvidenceLevel.MODERATE: ("#F59E0B", "rgba(245, 158, 11, 0.20)", "ðŸŸ¡"),
            EvidenceLevel.LOW: ("#38BDF8", "rgba(56, 189, 248, 0.20)", "ðŸ”µ"),
            EvidenceLevel.INFO: ("#10B981", "rgba(16, 185, 129, 0.20)", "ðŸŸ¢"),
        }
    else:
        sev_colors = {
            EvidenceLevel.CRITICAL: ("#DC2626", "#FEE2E2", "ðŸ”´"),
            EvidenceLevel.HIGH: ("#EA580C", "#FFEDD5", "ðŸŸ "),
            EvidenceLevel.MODERATE: ("#D97706", "#FEF3C7", "ðŸŸ¡"),
            EvidenceLevel.LOW: ("#2563EB", "#EFF6FF", "ðŸ”µ"),
            EvidenceLevel.INFO: ("#059669", "#D1FAE5", "ðŸŸ¢"),
        }

    # 1. Consolidated Empirical Telemetry Evidence Table (Standardized Headers)
    all_evidence = []
    for rec in report.recommendations:
        for ev in rec.evidence:
            all_evidence.append({
                "Metric Indicator": ev.metric_name,
                "Observed Value": str(ev.observed_value),
                "Threshold Boundary": ev.threshold,
                "Severity": ev.level.value,
                "Diagnostic Description": ev.description,
            })

    if all_evidence:
        st.markdown(
            f"<div style='font-size:12px; font-weight:700; color:{tokens.text_secondary}; text-transform:uppercase; letter-spacing:0.6px; margin: 14px 0 6px 0; display:flex; align-items:center; gap:6px;'>"
            f"<span>ðŸ” Supporting Telemetry Evidence</span>"
            f"<span style='font-size:10px; color:{tokens.text_muted}; text-transform:none; font-weight:400;'>(Empirical hardware sensor signals)</span>"
            f"</div>",
            unsafe_allow_html=True,
        )
        st.dataframe(all_evidence, width="stretch", hide_index=True)

    # 2. Structured Diagnostic Recommendations & Remediation Sequences
    st.markdown("<div style='margin-top:16px;'></div>", unsafe_allow_html=True)
    st.markdown(
        f"<div style='font-size:12px; font-weight:700; color:{tokens.text_secondary}; text-transform:uppercase; letter-spacing:0.6px; margin-bottom:8px; display:flex; align-items:center; gap:6px;'>"
        f"<span>ðŸ› ï¸ Explainable Diagnostic Recommendations &amp; Prioritized Remediation Plan</span>"
        f"</div>",
        unsafe_allow_html=True,
    )

    if not report.recommendations:
        st.markdown(
            f"""<div style="background-color:{tokens.bg_card}; border: 1px solid {tokens.border_color}; border-radius:8px; padding:18px; text-align:center;">
                <div style="color:{tokens.color_normal}; font-weight:700; font-size:14px;">ðŸŸ¢ All Subsystems Nominal</div>
                <div style="color:{tokens.text_secondary}; font-size:12px; margin-top:4px;">No critical or warning-level operational anomalies detected across host hardware and processes.</div>
            </div>""",
            unsafe_allow_html=True,
        )
        return

    for idx, rec in enumerate(report.recommendations):
        color, bg, icon = sev_colors.get(rec.severity, ("#64748B", tokens.bg_card_secondary, "âšª"))
        card_title = f"{icon} [{rec.severity.value}] {rec.title}"

        with st.expander(card_title, expanded=(idx == 0 or rec.severity in (EvidenceLevel.CRITICAL, EvidenceLevel.HIGH))):
            target_str = rec.target_component or "Host Subsystem"

            # 1. Header Chips (Severity, Target, Domain)
            st.markdown(
                f"<div style='margin-bottom:10px; display:flex; align-items:center; gap:8px; flex-wrap:wrap;'>"
                f"<span style='background-color:{bg}; color:{color}; padding:2px 8px; border-radius:4px; font-size:11px; font-weight:700; border:1px solid {color}40;'>"
                f"{rec.severity.value}"
                f"</span>"
                f"<span style='background-color:{tokens.bg_card_secondary}; color:{tokens.text_primary}; padding:2px 8px; border-radius:4px; font-size:11px; font-weight:600; border:1px solid {tokens.border_color};'>"
                f"Target Component: <strong style='color:{tokens.accent};'>{target_str}</strong>"
                f"</span>"
                f"<span style='background-color:{tokens.bg_card_secondary}; color:{tokens.text_secondary}; padding:2px 8px; border-radius:4px; font-size:11px; font-weight:500; border:1px solid {tokens.border_color}; text-transform:uppercase;'>"
                f"{rec.category.value} Domain"
                f"</span>"
                f"</div>",
                unsafe_allow_html=True,
            )

            # 2. Concise Incident Summary
            st.markdown(
                f"<div style='font-size:13px; color:{tokens.text_primary}; line-height:1.4; margin-bottom:10px;'>"
                f"{rec.summary}"
                f"</div>",
                unsafe_allow_html=True,
            )

            # 3. Root-Cause Hypothesis Callout (Matches React Cyan Callout)
            st.markdown(
                f"<div style='background-color:rgba(56, 189, 248, 0.06); border:1px solid rgba(56, 189, 248, 0.22); border-radius:6px; padding:10px 14px; margin:10px 0; font-size:12px; color:#E0F2FE; display:flex; align-items:flex-start; gap:8px;'>"
                f"<span style='color:{tokens.accent}; font-size:14px; flex-shrink:0;'>â„¹ï¸</span>"
                f"<div><b>Root Cause Hypothesis:</b> {rec.root_cause_hypothesis}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )

            # 4. Per-Recommendation Evidence Table
            if rec.evidence:
                st.markdown(
                    f"<div style='font-size:10.5px; font-weight:700; color:{tokens.text_muted}; text-transform:uppercase; letter-spacing:0.5px; margin:10px 0 4px 0;'>"
                    f"Supporting Telemetry Evidence</div>",
                    unsafe_allow_html=True,
                )
                rec_evidence_data = [
                    {
                        "Metric Indicator": ev.metric_name,
                        "Observed Value": str(ev.observed_value),
                        "Threshold Boundary": ev.threshold,
                        "Severity": ev.level.value,
                        "Diagnostic Description": ev.description,
                    }
                    for ev in rec.evidence
                ]
                st.dataframe(rec_evidence_data, width="stretch", hide_index=True)

            # 5. Prioritized Remediation Actions (Runbook)
            if rec.remediation_steps:
                st.markdown(
                    f"<div style='font-size:11px; font-weight:700; color:{tokens.color_normal}; text-transform:uppercase; letter-spacing:0.5px; margin:14px 0 6px 0; display:flex; align-items:center; gap:5px;'>"
                    f"<span>ðŸ“‹ Prioritized Remediation Actions</span>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
                for s_idx, step in enumerate(rec.remediation_steps, 1):
                    st.markdown(
                        f"<div style='display:flex; align-items:flex-start; gap:8px; margin-bottom:6px; font-size:12.5px; color:{tokens.text_primary};'>"
                        f"<span style='background-color:{tokens.bg_card_secondary}; color:{tokens.text_primary}; border:1px solid {tokens.border_color}; padding:1px 6px; border-radius:3px; font-size:10.5px; font-weight:700;'>{s_idx}</span>"
                        f"<span>{step}</span>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )

            # 6. Mandatory Human-Review Notice
            st.markdown(
                f"<div style='margin-top:10px; padding-top:8px; border-top:1px solid {tokens.border_subtle}; font-size:10.5px; color:{tokens.text_muted};'>"
                f"âš ï¸ <b>Advisory Notice:</b> Remediation actions are advisory and require human operator review before manual execution. Autonomous command execution is disabled."
                f"</div>",
                unsafe_allow_html=True,
            )
