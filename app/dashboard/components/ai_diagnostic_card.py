"""Streamlit component for rendering SentinelAI AI incident diagnoses and runbooks.

Displays evidence-backed incident summaries, probable cause rankings, recommended
investigation steps, safety-rated remediation actions, and explicit uncertainty boundaries.
"""

from __future__ import annotations

from typing import Any, Optional

import streamlit as st

from app.ai.models import AIIncidentDiagnosis, ConfidenceLevel, SafetyLevel
from app.dashboard.utils.theme import get_theme_tokens


def render_ai_diagnostic_card(
    diagnosis: Optional[AIIncidentDiagnosis],
    theme: Optional[str] = "dark",
    **kwargs: Any,
) -> None:
    """Render structured AI incident diagnosis report.

    Args:
        diagnosis: Evaluated AIIncidentDiagnosis model.
        theme: Theme name ('dark' or 'light').
        **kwargs: Optional forward-compatible arguments.
    """
    tokens = get_theme_tokens(theme)

    if diagnosis is None:
        st.markdown(
            f"""<div style="background-color:{tokens.bg_card}; border: 1px dashed {tokens.border_color}; border-radius:8px; padding:24px; text-align:center;">
                <div style="font-size:28px;">🤖</div>
                <div style="color:{tokens.text_primary}; font-weight:700; font-size:15px; margin-top:6px;">No AI Diagnosis Generated</div>
                <div style="color:{tokens.text_secondary}; font-size:12px; margin-top:4px;">Click 'Generate AI Diagnosis' to synthesize live telemetry, ML anomaly evaluation, and top processes into an evidence-grounded incident runbook.</div>
            </div>""",
            unsafe_allow_html=True,
        )
        return

    # Provider / Execution Mode Banner
    if diagnosis.is_fallback:
        badge_html = (
            f"<span style='background:rgba(245, 158, 11, 0.16); color:#F59E0B; border:1px solid rgba(245, 158, 11, 0.4); "
            f"padding:2px 8px; border-radius:4px; font-size:10px; font-weight:800; letter-spacing:0.8px;'>DETERMINISTIC FALLBACK</span>"
        )
        mode_note = (
            f"<span style='font-size:11px; color:#F59E0B;'>AI provider unavailable or disabled &bull; "
            f"Latency: <b>{diagnosis.latency_ms:.1f}ms</b></span>"
        )
    else:
        badge_html = (
            f"<span style='background:rgba(56, 189, 248, 0.16); color:#38BDF8; border:1px solid rgba(56, 189, 248, 0.4); "
            f"padding:2px 8px; border-radius:4px; font-size:10px; font-weight:800; letter-spacing:0.8px;'>AI-POWERED DIAGNOSIS &bull; {diagnosis.model_used.upper()}</span>"
        )
        mode_note = (
            f"<span style='font-size:11px; color:#38BDF8;'>Model: <b>{diagnosis.model_used}</b> &bull; "
            f"Latency: <b>{diagnosis.latency_ms:.1f}ms</b></span>"
        )

    st.markdown(
        f"""<div style="background-color:{tokens.bg_card}; border: 1px solid {tokens.border_color}; border-radius:8px; padding:16px; margin-bottom:14px;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
                <div style="display:flex; align-items:center; gap:8px;">
                    {badge_html}
                    <span style="font-size:11px; color:{tokens.text_muted};">ID: <code>{diagnosis.incident_id}</code></span>
                </div>
                <div>{mode_note}</div>
            </div>
            <div style="color:{tokens.text_primary}; font-size:15px; font-weight:600; line-height:1.4; margin-bottom:10px;">
                {diagnosis.incident_summary}
            </div>
            <div style="display:flex; gap:16px; font-size:12px; color:{tokens.text_secondary}; padding-top:8px; border-top:1px solid {tokens.border_subtle};">
                <div>Operational Risk: <b style="color:{tokens.text_primary};">{diagnosis.risk_category}</b></div>
                <div>Anomaly Score: <b style="color:{tokens.text_primary};">{diagnosis.anomaly_score:.4f}</b></div>
                <div>Health Score: <b style="color:{tokens.text_primary};">{f'{diagnosis.health_score:.1f}/100' if diagnosis.health_score is not None else 'N/A'}</b></div>
            </div>
        </div>""",
        unsafe_allow_html=True,
    )

    # 1. Probable Causes (Evidence-Grounded Hypotheses)
    if diagnosis.probable_causes:
        st.markdown(
            f"<div style='font-size:12px; font-weight:700; color:{tokens.text_secondary}; text-transform:uppercase; letter-spacing:0.6px; margin: 12px 0 8px 0;'>"
            f"🔍 Evidence-Based Probable Causes</div>",
            unsafe_allow_html=True,
        )

        conf_colors = {
            ConfidenceLevel.HIGH: ("#EF4444", "rgba(239, 68, 68, 0.15)"),
            ConfidenceLevel.MEDIUM: ("#F59E0B", "rgba(245, 158, 11, 0.15)"),
            ConfidenceLevel.LOW: ("#38BDF8", "rgba(56, 189, 248, 0.15)"),
        }

        for cause in diagnosis.probable_causes:
            c_col, c_bg = conf_colors.get(cause.confidence, ("#94A3B8", "rgba(148, 163, 184, 0.15)"))
            evidence_html = "".join([f"<li style='margin-bottom:2px;'>{e}</li>" for e in cause.supporting_evidence])

            st.markdown(
                f"""<div style="background-color:{tokens.bg_card_secondary}; border-left: 3px solid {c_col}; border-radius:4px; padding:10px 14px; margin-bottom:8px;">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
                        <span style="font-size:13px; font-weight:700; color:{tokens.text_primary};">Cause #{cause.rank}: {cause.hypothesis}</span>
                        <span style="background:{c_bg}; color:{c_col}; font-size:10px; font-weight:800; padding:2px 6px; border-radius:4px;">{cause.confidence.value} CONFIDENCE</span>
                    </div>
                    <ul style="font-size:11px; color:{tokens.text_secondary}; margin:4px 0 0 16px; padding:0;">
                        {evidence_html}
                    </ul>
                </div>""",
                unsafe_allow_html=True,
            )

    # 2. Investigation Steps
    if diagnosis.investigation_steps:
        st.markdown(
            f"<div style='font-size:12px; font-weight:700; color:{tokens.text_secondary}; text-transform:uppercase; letter-spacing:0.6px; margin: 16px 0 8px 0;'>"
            f"🔬 Prioritized Investigation Steps</div>",
            unsafe_allow_html=True,
        )
        for idx, step in enumerate(diagnosis.investigation_steps, start=1):
            st.markdown(
                f"""<div style="display:flex; align-items:flex-start; gap:8px; font-size:12px; color:{tokens.text_primary}; margin-bottom:6px;">
                    <span style="background:{tokens.border_color}; color:{tokens.text_secondary}; border-radius:50%; min-width:18px; height:18px; font-size:10px; font-weight:700; display:flex; align-items:center; justify-content:center;">{idx}</span>
                    <span>{step}</span>
                </div>""",
                unsafe_allow_html=True,
            )

    # 3. Remediation Actions (Safety-Rated Runbook)
    if diagnosis.remediation_actions:
        st.markdown(
            f"<div style='font-size:12px; font-weight:700; color:{tokens.text_secondary}; text-transform:uppercase; letter-spacing:0.6px; margin: 16px 0 6px 0;'>"
            f"🛠️ Prioritized Remediation Runbook (Human Review Required)</div>",
            unsafe_allow_html=True,
        )

        st.markdown(
            f"""<div style="background:rgba(239, 68, 68, 0.08); border: 1px solid rgba(239, 68, 68, 0.3); border-radius:6px; padding:10px 14px; margin-bottom:12px;">
                <div style="display:flex; align-items:center; gap:8px;">
                    <span style="font-size:15px;">⚠️</span>
                    <span style="font-size:11px; font-weight:800; color:#EF4444; text-transform:uppercase; letter-spacing:0.8px;">Mandatory Operator Review Required</span>
                </div>
                <div style="font-size:11px; color:#F8FAFC; margin-top:4px; line-height:1.4;">
                    AI-generated remediation suggestions are strictly advisory and generated by an untrusted language model.
                    <b>Autonomous command execution is permanently disabled.</b> Operators must independently inspect target PIDs, verify command semantics for the active OS, and confirm prerequisites before executing any operational action.
                </div>
            </div>""",
            unsafe_allow_html=True,
        )

        safety_colors = {
            SafetyLevel.SAFE: ("#10B981", "rgba(16, 185, 129, 0.15)"),
            SafetyLevel.CAUTION: ("#F59E0B", "rgba(245, 158, 11, 0.15)"),
            SafetyLevel.CRITICAL: ("#EF4444", "rgba(239, 68, 68, 0.15)"),
        }

        for act in diagnosis.remediation_actions:
            s_col, s_bg = safety_colors.get(act.safety_level, ("#94A3B8", "rgba(148, 163, 184, 0.15)"))
            if act.command:
                cmd_html = (
                    f"<div style='margin-top:6px; display:flex; flex-direction:column; gap:4px;'>"
                    f"<div style='background:{tokens.bg_app}; border:1px solid {tokens.border_color}; border-radius:4px; padding:6px 10px; overflow-x:auto; max-width:100%;'>"
                    f"<code style='color:#38BDF8; font-family:monospace; font-size:12px; white-space:pre-wrap; word-break:break-all;'>{act.command}</code>"
                    f"</div>"
                    f"<span style='font-size:10px; color:#94A3B8;'><i>⚠️ Manual review required — command execution is disabled</i></span>"
                    f"</div>"
                )
            else:
                cmd_html = f"<div style='font-size:11px; color:{tokens.text_muted}; margin-top:4px;'><i>[No automated command provided &bull; manual inspection required]</i></div>"

            st.markdown(
                f"""<div style="background-color:{tokens.bg_card}; border: 1px solid {tokens.border_subtle}; border-radius:6px; padding:10px 14px; margin-bottom:8px;">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <span style="font-size:13px; font-weight:600; color:{tokens.text_primary};">Step {act.step_number}: {act.action}</span>
                        <span style="background:{s_bg}; color:{s_col}; font-size:10px; font-weight:800; padding:2px 6px; border-radius:4px;">{act.safety_level.value}</span>
                    </div>
                    {cmd_html}
                    <div style="font-size:11px; color:{tokens.text_muted}; margin-top:4px; font-style:italic;">
                        &bull; {act.precautions}
                    </div>
                </div>""",
                unsafe_allow_html=True,
            )

    # 4. Uncertainty Assessment
    st.markdown(
        f"""<div style="background-color:rgba(148, 163, 184, 0.08); border-left: 3px solid #64748B; border-radius:4px; padding:10px 14px; margin-top:14px;">
            <div style="font-size:11px; font-weight:700; color:{tokens.text_secondary}; text-transform:uppercase; letter-spacing:0.5px; margin-bottom:2px;">
                ℹ️ Evidence Boundaries &amp; Uncertainty Assessment
            </div>
            <div style="font-size:11px; color:{tokens.text_muted}; line-height:1.4;">
                {diagnosis.uncertainty_assessment}
            </div>
            <div style="font-size:10px; color:#64748B; margin-top:4px;">
                Advisory Notice: SentinelAI provides diagnostic guidance based on hardware sensors. Autonomous execution is prohibited; human operator validation is mandatory prior to remediation.
            </div>
        </div>""",
        unsafe_allow_html=True,
    )
