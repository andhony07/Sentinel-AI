"""Operational safety validation and guardrails for SentinelAI AI diagnostic assistant.

Enforces strict defense-in-depth policies:
1. Never allows autonomous execution of model-generated commands.
2. Treats all model recommendations as untrusted suggestions requiring human operator review.
3. Detects and blocks attempts to terminate critical operating-system processes (e.g. Windows System Idle Process, System, PID 0/4, systemd, init).
4. Validates operating-system command compatibility, rejecting Linux commands on Windows and vice versa without unverified blind translations.
5. Strips dangerous, destructive, or power-disruptive commands, replacing them with safe, non-destructive investigation steps.
6. Enforces explicit operator-review disclaimers and safety ratings.
"""

from __future__ import annotations

import platform
import re
from typing import Any, Optional

from app.ai.models import ConfidenceLevel, ProbableCause, RemediationAction, SafetyLevel
from app.core.logging_config import get_logger

logger = get_logger("app.ai.safety")

# Protected critical processes by operating system
CRITICAL_PROCESSES_WINDOWS: frozenset[str] = frozenset({
    "system idle process",
    "system",
    "registry",
    "smss.exe",
    "smss",
    "csrss.exe",
    "csrss",
    "wininit.exe",
    "wininit",
    "services.exe",
    "services",
    "lsass.exe",
    "lsass",
    "svchost.exe",
    "svchost",
    "fontdrvhost.exe",
    "fontdrvhost",
    "winlogon.exe",
    "winlogon",
    "explorer.exe",
    "explorer",
    "dwm.exe",
    "dwm",
    "spoolsv.exe",
    "spoolsv",
    "conhost.exe",
    "conhost",
})

CRITICAL_PROCESSES_LINUX: frozenset[str] = frozenset({
    "systemd",
    "init",
    "kthreadd",
    "kworker",
    "systemd-journald",
    "systemd-udevd",
    "systemd-resolved",
    "auditd",
    "sshd",
    "cron",
    "crond",
})

CRITICAL_PROCESSES_DARWIN: frozenset[str] = frozenset({
    "launchd",
    "kernel_task",
    "syslogd",
    "logd",
})

# Protected PIDs
CRITICAL_PIDS_WINDOWS: frozenset[int] = frozenset({0, 4})
CRITICAL_PIDS_POSIX: frozenset[int] = frozenset({0, 1, 2})

# Patterns for destructive or dangerous commands
DANGEROUS_COMMAND_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    # Filesystem destruction
    (re.compile(r"\brm\s+-[a-zA-Z]*r[a-zA-Z]*f\s+[\/\*]", re.IGNORECASE), "Destructive file removal ('rm -rf /')"),
    (re.compile(r"\brmdir\s+/[sS]", re.IGNORECASE), "Recursive directory deletion ('rmdir /s')"),
    (re.compile(r"\bdel\s+(?:/[fFqQsS]\s+)+[a-zA-Z]:\\", re.IGNORECASE), "System root file deletion ('del /s /q')"),
    (re.compile(r"\bformat\s+[a-zA-Z]:", re.IGNORECASE), "Disk formatting ('format')"),
    (re.compile(r"\bmkfs(?:\.[a-zA-Z0-9]+)?\b", re.IGNORECASE), "Filesystem recreation ('mkfs')"),
    (re.compile(r"\bdd\s+if=.*of=/dev/(?:sd[a-z]|nvme|hd[a-z])", re.IGNORECASE), "Raw disk overwrite ('dd')"),
    (re.compile(r"\bfdisk\b", re.IGNORECASE), "Partition alteration ('fdisk')"),

    # System reboot and power state disruption
    (re.compile(r"\bshutdown\b", re.IGNORECASE), "System shutdown command"),
    (re.compile(r"\breboot\b", re.IGNORECASE), "System reboot command"),
    (re.compile(r"\binit\s+[06]\b", re.IGNORECASE), "System state halt/reboot ('init 0/6')"),
    (re.compile(r"\bhalt\b", re.IGNORECASE), "System halt command"),
    (re.compile(r"\bpoweroff\b", re.IGNORECASE), "System poweroff command"),
    (re.compile(r"\bStop-Computer\b", re.IGNORECASE), "PowerShell computer stop ('Stop-Computer')"),
    (re.compile(r"\bRestart-Computer\b", re.IGNORECASE), "PowerShell computer restart ('Restart-Computer')"),

    # Denial of service / fork bombs
    (re.compile(r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;", re.IGNORECASE), "Shell fork bomb"),
    (re.compile(r"%\s*0\s*\|\s*%\s*0", re.IGNORECASE), "Batch fork bomb"),

    # Blanket process termination
    (re.compile(r"\bkill\s+-9\s+-1\b", re.IGNORECASE), "Blanket process termination ('kill -9 -1')"),
    (re.compile(r"\btaskkill\s+(?:/[fF]\s+)?(?:/IM|/im)\s+\*", re.IGNORECASE), "Blanket task termination ('taskkill /IM *')"),
    (re.compile(r"\bStop-Process\s+(?:-Name\s+)?\*", re.IGNORECASE), "Blanket PowerShell process termination"),
    (re.compile(r"\bpkill\s+-9\s+-f\s+['\"]?\.\*['\"]?", re.IGNORECASE), "Blanket regex process kill ('pkill -9 -f .*')"),

    # Untrusted remote script execution pipes
    (re.compile(r"\bcurl\b.*\|\s*(?:bash|sh|python|powershell)", re.IGNORECASE), "Piping untrusted remote script into shell"),
    (re.compile(r"\bwget\b.*\|\s*(?:bash|sh)", re.IGNORECASE), "Piping untrusted remote download into shell"),
)

# OS-Specific Command Indicators
LINUX_COMMAND_INDICATORS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bkill\s+-(?:9|15|KILL|TERM|HUP)\b", re.IGNORECASE),
    re.compile(r"\bkillall\b", re.IGNORECASE),
    re.compile(r"\bpkill\b", re.IGNORECASE),
    re.compile(r"\bpidof\b", re.IGNORECASE),
    re.compile(r"\bsystemctl\b", re.IGNORECASE),
    re.compile(r"\bjournalctl\b", re.IGNORECASE),
    re.compile(r"\biostat\b", re.IGNORECASE),
    re.compile(r"\btop\s+-", re.IGNORECASE),
    re.compile(r"\bhtop\b", re.IGNORECASE),
    re.compile(r"\bps\s+-(?:ef|aux)\b", re.IGNORECASE),
    re.compile(r"\bfree\s+-[mghk]\b", re.IGNORECASE),
    re.compile(r"\bvmstat\b", re.IGNORECASE),
    re.compile(r"\bapt(?:-get)?\b", re.IGNORECASE),
    re.compile(r"\byum\b", re.IGNORECASE),
    re.compile(r"\$\(pidof\b", re.IGNORECASE),
    re.compile(r"/proc/\d+", re.IGNORECASE),
)

WINDOWS_COMMAND_INDICATORS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\btaskkill\b", re.IGNORECASE),
    re.compile(r"\btasklist\b", re.IGNORECASE),
    re.compile(r"\bGet-Process\b", re.IGNORECASE),
    re.compile(r"\bStop-Process\b", re.IGNORECASE),
    re.compile(r"\bGet-Service\b", re.IGNORECASE),
    re.compile(r"\bRestart-Service\b", re.IGNORECASE),
    re.compile(r"\bGet-Counter\b", re.IGNORECASE),
    re.compile(r"\bresmon\b", re.IGNORECASE),
    re.compile(r"\bperfmon\b", re.IGNORECASE),
    re.compile(r"\bwmic\b", re.IGNORECASE),
    re.compile(r"\bpowershell(?:\.exe)?\b", re.IGNORECASE),
    re.compile(r"\bcmd(?:\.exe)?\s+/c\b", re.IGNORECASE),
    re.compile(r"\bsc\s+query\b", re.IGNORECASE),
)


def get_target_os(explicit_os: Optional[str] = None) -> str:
    """Resolve the host operating system name (e.g. 'Windows', 'Linux', 'Darwin')."""
    if explicit_os and explicit_os.strip():
        return explicit_os.strip().capitalize()
    return platform.system()


def is_critical_process(
    process_name: Optional[str],
    pid: Optional[int] = None,
    target_os: Optional[str] = None,
) -> bool:
    """Determine whether a process is a protected operating system component.

    Args:
        process_name: Name or path of process.
        pid: Optional process ID.
        target_os: Optional target OS ('Windows', 'Linux', 'Darwin').

    Returns:
        True if the process is a protected critical OS component that must not be terminated.
    """
    resolved_os = get_target_os(target_os)

    # Check PIDs
    if pid is not None:
        if resolved_os == "Windows" and pid in CRITICAL_PIDS_WINDOWS:
            return True
        if resolved_os in ("Linux", "Darwin") and pid in CRITICAL_PIDS_POSIX:
            return True

    if not process_name:
        return False

    norm_name = str(process_name).strip().lower()
    # Normalize variants like "System+Idle+Process" or "System_Idle_Process"
    norm_name = re.sub(r"[+_]", " ", norm_name)
    if norm_name.endswith(".exe"):
        norm_name = norm_name[:-4]

    # Windows critical check
    if resolved_os == "Windows":
        if norm_name in ("system idle process", "system idle", "idle process", "system", "registry"):
            return True
        if norm_name in CRITICAL_PROCESSES_WINDOWS or f"{norm_name}.exe" in CRITICAL_PROCESSES_WINDOWS:
            return True

    # Linux critical check
    if resolved_os == "Linux":
        if norm_name in CRITICAL_PROCESSES_LINUX:
            return True
        if norm_name.startswith("kworker") or norm_name.startswith("ksoftirqd"):
            return True

    # Darwin critical check
    if resolved_os == "Darwin":
        if norm_name in CRITICAL_PROCESSES_DARWIN:
            return True

    # Universal protection for system idle
    if "system idle process" in norm_name or "idle process" in norm_name:
        return True

    return False


def is_dangerous_command(command: Optional[str]) -> tuple[bool, str]:
    """Detect whether a command is destructive, system-disrupting, or hazardous.

    Args:
        command: Command string to inspect.

    Returns:
        Tuple of (is_dangerous, reason_description).
    """
    if not command or not command.strip():
        return False, ""

    cmd = command.strip()

    # Check for critical process termination in command text
    cmd_lower = cmd.lower()
    if any(k in cmd_lower for k in ("system idle", "system+idle", "system_idle", "pidof -s -x system+idle")):
        return True, "Attempt to terminate core OS process ('System Idle Process')"

    if re.search(r"\bkill\s+-9\s+(?:0|1|4)\b", cmd):
        return True, "Attempt to terminate kernel/core OS PID (0, 1, or 4)"

    for pattern, description in DANGEROUS_COMMAND_PATTERNS:
        if pattern.search(cmd):
            return True, description

    return False, ""


def is_command_compatible_with_os(
    command: Optional[str],
    target_os: Optional[str] = None,
) -> tuple[bool, Optional[str]]:
    """Verify that a recommended command matches the dialect of the host operating system.

    Args:
        command: Command string to check.
        target_os: Operating system ('Windows', 'Linux', 'Darwin').

    Returns:
        Tuple of (is_compatible, mismatch_reason).
    """
    if not command or not command.strip():
        return True, None

    resolved_os = get_target_os(target_os)
    cmd = command.strip()

    if resolved_os == "Windows":
        for indicator in LINUX_COMMAND_INDICATORS:
            if indicator.search(cmd):
                return False, f"Linux POSIX command '{indicator.pattern}' is incompatible with Windows host"

    elif resolved_os in ("Linux", "Darwin"):
        for indicator in WINDOWS_COMMAND_INDICATORS:
            if indicator.search(cmd):
                return False, f"Windows command '{indicator.pattern}' is incompatible with {resolved_os} host"

    return True, None


def sanitize_remediation_and_evidence(
    actions: list[RemediationAction],
    probable_causes: list[ProbableCause],
    investigation_steps: list[str],
    telemetry_metrics: Optional[dict[str, Any]] = None,
    target_os: Optional[str] = None,
) -> tuple[list[RemediationAction], list[ProbableCause], list[str], list[str]]:
    """Enforce complete defense-in-depth safety guardrails across diagnostic output.

    1. Blocks and replaces attempts to terminate critical system processes.
    2. Corrects false accusations against Windows System Idle Process.
    3. Strips destructive or hazardous commands.
    4. Strips OS-mismatched commands rather than performing unverified translation.
    5. Replaces unsafe actions with non-destructive diagnostic investigation steps.
    6. Attaches mandatory human operator review disclaimers to all precautions.

    Args:
        actions: List of RemediationAction items from LLM or heuristic report.
        probable_causes: List of ProbableCause items.
        investigation_steps: List of investigation step strings.
        telemetry_metrics: Optional raw telemetry dictionary for contextual reference.
        target_os: Optional target OS override.

    Returns:
        Tuple of (sanitized_actions, sanitized_causes, sanitized_steps, safety_notices).
    """
    resolved_os = get_target_os(target_os)
    safety_notices: list[str] = []

    # -------------------------------------------------------------------------
    # 1. Sanitize Probable Causes (Correct Windows System Idle Process False Hypotheses)
    # -------------------------------------------------------------------------
    sanitized_causes: list[ProbableCause] = []
    for cause in probable_causes:
        hypo = cause.hypothesis
        # Check if model blamed System Idle Process for high CPU on Windows
        if resolved_os == "Windows" and any(
            k in hypo.lower() for k in ("system idle process", "system idle", "idle process")
        ):
            notice = (
                "Safety Clarification: On Windows hosts, 'System Idle Process' (PID 0) represents "
                "available CPU capacity (time when CPU is idle), not an anomalous resource consumer."
            )
            safety_notices.append(notice)
            sanitized_causes.append(
                ProbableCause(
                    rank=cause.rank,
                    hypothesis=(
                        "System Idle Process reflects unallocated CPU idle capacity. "
                        "Effective operational CPU load is normal; no active CPU runaway detected."
                    ),
                    confidence=ConfidenceLevel.HIGH,
                    supporting_evidence=[
                        "System Idle Process indicates available processor cycles on Windows.",
                        "Observed high metric percentage represents unallocated core capacity.",
                    ],
                )
            )
        else:
            sanitized_causes.append(cause)

    # -------------------------------------------------------------------------
    # 2. Sanitize Remediation Actions
    # -------------------------------------------------------------------------
    sanitized_actions: list[RemediationAction] = []
    additional_investigation_steps: list[str] = []

    for act in actions:
        cmd = act.command
        action_text = act.action
        safety_lvl = act.safety_level
        precautions = act.precautions or "Human operator review required before execution."

        # Check critical process target
        targets_critical = False
        if is_critical_process(action_text, target_os=resolved_os) or (
            cmd and is_critical_process(cmd, target_os=resolved_os)
        ):
            targets_critical = True

        # Check dangerous command patterns
        is_dangerous, danger_reason = is_dangerous_command(cmd)

        # Check OS dialect compatibility
        is_compat, compat_reason = is_command_compatible_with_os(cmd, target_os=resolved_os)

        # Resolve interventions
        if targets_critical:
            cmd = None
            action_text = (
                f"Verify system baseline: '{act.action}' targets a protected operating system component "
                f"which must not be terminated. Observe process metrics using native system monitor."
            )
            safety_lvl = SafetyLevel.SAFE
            precautions = (
                "SAFETY INTERVENTION: Targeted process is a critical operating system component. "
                "Autonomous or manual termination is blocked to prevent kernel panic or system crash. "
                "Operator review required."
            )
            safety_notices.append(f"Action {act.step_number} blocked: attempted to target critical OS process.")
            additional_investigation_steps.append(
                "Review host resource allocation using Task Manager or Resource Monitor (resmon)."
                if resolved_os == "Windows"
                else "Review system services via 'systemctl status' or 'top -b -n 1'."
            )

        elif is_dangerous:
            cmd = None
            action_text = f"Perform safe diagnostic inspection: dangerous command was omitted ({danger_reason})."
            safety_lvl = SafetyLevel.SAFE
            precautions = (
                f"SAFETY INTERVENTION: Model suggested a hazardous command ({danger_reason}). "
                "Command stripped by safety filter. Operator review required."
            )
            safety_notices.append(f"Action {act.step_number} command omitted: {danger_reason}.")

        elif not is_compat:
            cmd = None
            action_text = f"{act.action} (Command omitted due to OS dialect mismatch for {resolved_os})."
            safety_lvl = SafetyLevel.SAFE
            precautions = (
                f"OS DIALECT MISMATCH: Suggested command is incompatible with target host OS ({resolved_os}). "
                "Unverified blind translation was rejected. Operator must inspect using native tools."
            )
            safety_notices.append(f"Action {act.step_number} command omitted: {compat_reason}.")
            if resolved_os == "Windows":
                additional_investigation_steps.append(
                    "Inspect running processes using PowerShell: 'Get-Process | Sort-Object CPU -Descending | Select-Object -First 10'."
                )
            else:
                additional_investigation_steps.append(
                    "Inspect running processes using Linux POSIX tool: 'ps -eo pid,ppid,cmd,%mem,%cpu --sort=-%cpu | head -n 10'."
                )

        else:
            # Command is non-destructive and compatible, but enforce operator review disclaimer
            if "operator review" not in precautions.lower():
                precautions = f"{precautions} Human operator review required before executing any remediation."

        sanitized_actions.append(
            RemediationAction(
                step_number=act.step_number,
                action=action_text[:500],
                command=cmd[:500] if cmd else None,
                safety_level=safety_lvl,
                precautions=precautions[:1000],
            )
        )

    # -------------------------------------------------------------------------
    # 3. Sanitize Investigation Steps
    # -------------------------------------------------------------------------
    sanitized_steps: list[str] = []
    for step in investigation_steps:
        # Check if step contains incompatible commands on Windows (e.g. `top -b -p ...` or `iostat`)
        if resolved_os == "Windows":
            if any(k in step.lower() for k in ("top -b", "iostat", "pidof", "grep -v pid")):
                sanitized_steps.append(
                    "Inspect process resource utilization using Windows Task Manager, Resource Monitor (resmon), "
                    "or PowerShell: Get-Process | Sort-Object CPU -Descending | Select-Object -First 5."
                )
                continue
        elif resolved_os in ("Linux", "Darwin"):
            if any(k in step.lower() for k in ("get-process", "tasklist", "resmon", "perfmon")):
                sanitized_steps.append(
                    "Inspect process resource utilization using Linux tools: 'top -b -n 1' or 'ps -ef'."
                )
                continue
        sanitized_steps.append(step)

    for add_step in additional_investigation_steps:
        if add_step not in sanitized_steps:
            sanitized_steps.append(add_step)

    return sanitized_actions, sanitized_causes, sanitized_steps[:12], safety_notices
