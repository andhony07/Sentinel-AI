"""Unit and integration tests for SentinelAI operational safety guardrails.

Validates:
1. Critical operating-system process detection (Windows System Idle Process, System, PID 0/4, systemd, init).
2. Dangerous command detection (destructive files, reboots, blanket termination, fork bombs).
3. OS command dialect compatibility (rejecting Linux commands on Windows and vice versa).
4. Remediation sanitization and non-destructive fallback.
5. Preservation of authoritative ML metrics under dangerous suggestions.
6. Hypothesis correction for Windows System Idle Process.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

import httpx
import pytest

from app.ai.client import OllamaClient
from app.ai.models import (
    AIIncidentDiagnosis,
    ConfidenceLevel,
    ProbableCause,
    RemediationAction,
    SafetyLevel,
)
from app.ai.safety import (
    get_target_os,
    is_command_compatible_with_os,
    is_critical_process,
    is_dangerous_command,
    sanitize_remediation_and_evidence,
)
from app.ai.service import AIDiagnosticService
from app.core.config import Settings, load_config
from app.dashboard.services.dashboard_service import DashboardService


class TestCriticalProcessProtection:
    """Test suite for critical operating system process detection and immunity."""

    def test_windows_system_idle_process_detection(self) -> None:
        """Verify Windows System Idle Process is protected across all naming variations."""
        assert is_critical_process("System Idle Process", target_os="Windows") is True
        assert is_critical_process("system idle process", target_os="Windows") is True
        assert is_critical_process("System+Idle+Process", target_os="Windows") is True
        assert is_critical_process("system_idle_process", target_os="Windows") is True
        assert is_critical_process("Idle Process", target_os="Windows") is True
        assert is_critical_process("System Idle", target_os="Windows") is True
        # PID 0 is always protected on Windows
        assert is_critical_process(None, pid=0, target_os="Windows") is True
        assert is_critical_process("unknown.exe", pid=0, target_os="Windows") is True

    def test_windows_core_system_processes(self) -> None:
        """Verify core Windows processes and kernel PID 4 are protected."""
        assert is_critical_process("System", target_os="Windows") is True
        assert is_critical_process(None, pid=4, target_os="Windows") is True
        assert is_critical_process("smss.exe", target_os="Windows") is True
        assert is_critical_process("csrss.exe", target_os="Windows") is True
        assert is_critical_process("wininit.exe", target_os="Windows") is True
        assert is_critical_process("services.exe", target_os="Windows") is True
        assert is_critical_process("lsass.exe", target_os="Windows") is True
        assert is_critical_process("svchost.exe", target_os="Windows") is True
        assert is_critical_process("explorer.exe", target_os="Windows") is True

    def test_linux_core_system_processes(self) -> None:
        """Verify core Linux processes (systemd, init, kthreadd) are protected."""
        assert is_critical_process("systemd", target_os="Linux") is True
        assert is_critical_process("init", target_os="Linux") is True
        assert is_critical_process("kthreadd", target_os="Linux") is True
        assert is_critical_process("kworker/0:1", target_os="Linux") is True
        assert is_critical_process(None, pid=1, target_os="Linux") is True
        assert is_critical_process(None, pid=2, target_os="Linux") is True

    def test_non_critical_processes_allowed(self) -> None:
        """Verify ordinary applications and workloads are not falsely flagged as critical."""
        assert is_critical_process("python.exe", pid=1042, target_os="Windows") is False
        assert is_critical_process("nginx", pid=5540, target_os="Linux") is False
        assert is_critical_process("stress_worker", pid=9999, target_os="Linux") is False
        assert is_critical_process("postgres.exe", pid=4020, target_os="Windows") is False


class TestDangerousCommandDetection:
    """Test suite for detecting destructive, system-disrupting, or hazardous commands."""

    def test_detect_destructive_filesystem_commands(self) -> None:
        """Verify destructive filesystem modifications are identified."""
        dangerous_cmds = [
            "rm -rf /",
            "rm -rf *",
            "rmdir /s C:\\",
            "del /f /s /q C:\\*",
            "format D:",
            "mkfs.ext4 /dev/sda1",
            "dd if=/dev/zero of=/dev/sda",
            "fdisk /dev/nvme0n1",
        ]
        for cmd in dangerous_cmds:
            is_dang, desc = is_dangerous_command(cmd)
            assert is_dang is True, f"Failed to detect dangerous command: {cmd}"
            assert len(desc) > 0

    def test_detect_reboot_and_shutdown_commands(self) -> None:
        """Verify power state alterations and reboots are flagged."""
        reboot_cmds = [
            "shutdown -r now",
            "shutdown /s /t 0",
            "reboot",
            "init 0",
            "init 6",
            "poweroff",
            "Stop-Computer -Force",
            "Restart-Computer -Force",
        ]
        for cmd in reboot_cmds:
            is_dang, _ = is_dangerous_command(cmd)
            assert is_dang is True, f"Failed to detect reboot/shutdown command: {cmd}"

    def test_detect_blanket_termination_and_critical_kill(self) -> None:
        """Verify wildcard or critical PID termination commands are flagged."""
        critical_kills = [
            "kill -9 -1",
            "taskkill /F /IM *",
            "Stop-Process -Name *",
            "kill -9 $(pidof -s -x System+Idle+Process)",
            "kill -9 0",
            "kill -9 4",
        ]
        for cmd in critical_kills:
            is_dang, _ = is_dangerous_command(cmd)
            assert is_dang is True, f"Failed to detect dangerous kill command: {cmd}"

    def test_safe_inspection_commands_permitted(self) -> None:
        """Verify non-destructive diagnostic queries are not flagged as dangerous."""
        safe_cmds = [
            "Get-Process python",
            "tasklist /FI \"IMAGENAME eq python.exe\"",
            "netstat -ano",
            "resmon",
            "ps -ef | grep worker",
            "top -b -n 1",
        ]
        for cmd in safe_cmds:
            is_dang, _ = is_dangerous_command(cmd)
            assert is_dang is False, f"Falsely flagged safe command as dangerous: {cmd}"


class TestOSCommandCompatibility:
    """Test suite for host OS command dialect enforcement."""

    def test_linux_commands_rejected_on_windows(self) -> None:
        """Verify Linux commands are rejected on Windows hosts."""
        linux_cmds = [
            "kill -9 1042",
            "killall nginx",
            "pkill -f worker",
            "pidof python",
            "systemctl restart server",
            "journalctl -xe",
            "top -b -n 1",
            "htop",
            "iostat -x 1 1",
            "cat /proc/123/status",
        ]
        for cmd in linux_cmds:
            is_compat, reason = is_command_compatible_with_os(cmd, target_os="Windows")
            assert is_compat is False, f"Failed to reject Linux command on Windows: {cmd}"
            assert reason is not None

    def test_windows_commands_accepted_on_windows(self) -> None:
        """Verify native Windows and PowerShell commands are accepted on Windows."""
        windows_cmds = [
            "Get-Process | Sort-Object CPU -Descending | Select-Object -First 5",
            "tasklist /FI \"CPUTIME gt 00:01:00\"",
            "resmon",
            "perfmon",
            "Stop-Process -Id 1042",
            "Get-Service -Name W32Time",
        ]
        for cmd in windows_cmds:
            is_compat, _ = is_command_compatible_with_os(cmd, target_os="Windows")
            assert is_compat is True, f"Falsely rejected Windows command on Windows: {cmd}"

    def test_windows_commands_rejected_on_linux(self) -> None:
        """Verify Windows commands are rejected on Linux hosts."""
        win_cmds = [
            "taskkill /F /PID 1042",
            "tasklist",
            "Get-Process",
            "Stop-Process -Name worker",
            "wmic process where name='test.exe' call terminate",
        ]
        for cmd in win_cmds:
            is_compat, reason = is_command_compatible_with_os(cmd, target_os="Linux")
            assert is_compat is False, f"Failed to reject Windows command on Linux: {cmd}"
            assert reason is not None


class TestRemediationSafetySanitization:
    """Test suite for defense-in-depth sanitization of LLM recommendations."""

    def test_sanitize_blocks_system_idle_process_kill_on_windows(self) -> None:
        """Verify that attempting to kill System Idle Process on Windows strips the command and corrects hypothesis."""
        actions = [
            RemediationAction(
                step_number=1,
                action="Identify and terminate the System Idle Process",
                command="kill -9 $(pidof -s -x System+Idle+Process)",
                safety_level=SafetyLevel.CAUTION,
                precautions="Ensure process is not critical before terminating.",
            )
        ]
        causes = [
            ProbableCause(
                rank=1,
                hypothesis="High CPU utilization driven by System Idle Process.",
                confidence=ConfidenceLevel.HIGH,
                supporting_evidence=["System Idle Process consuming 572% CPU"],
            )
        ]
        steps = ["top -b -p $(pidof -s -x System+Idle+Process) -n 1"]

        san_actions, san_causes, san_steps, notices = sanitize_remediation_and_evidence(
            actions=actions,
            probable_causes=causes,
            investigation_steps=steps,
            target_os="Windows",
        )

        # Command must be stripped
        assert san_actions[0].command is None
        assert san_actions[0].safety_level == SafetyLevel.SAFE
        assert "protected operating system component" in san_actions[0].action
        assert "SAFETY INTERVENTION" in san_actions[0].precautions

        # Hypothesis must be corrected to explain idle cycles
        assert "unallocated CPU idle capacity" in san_causes[0].hypothesis

        # Investigation step must not use Linux 'top'
        assert not any("top -b" in s for s in san_steps)
        assert len(notices) >= 1

    def test_sanitize_strips_destructive_commands(self) -> None:
        """Verify destructive commands have command attribute stripped."""
        actions = [
            RemediationAction(
                step_number=1,
                action="Clean temporary directories to reclaim disk space.",
                command="rm -rf /",
                safety_level=SafetyLevel.CRITICAL,
                precautions="Delete everything.",
            )
        ]
        san_actions, _, _, notices = sanitize_remediation_and_evidence(
            actions=actions,
            probable_causes=[],
            investigation_steps=[],
            target_os="Linux",
        )

        assert san_actions[0].command is None
        assert "dangerous command was omitted" in san_actions[0].action
        assert len(notices) >= 1

    def test_sanitize_strips_os_mismatched_command(self) -> None:
        """Verify that a Linux command proposed for a Windows host has command stripped without blind translation."""
        actions = [
            RemediationAction(
                step_number=1,
                action="Terminate rogue worker thread.",
                command="kill -9 2048",
                safety_level=SafetyLevel.CAUTION,
                precautions="Stop thread.",
            )
        ]
        san_actions, _, san_steps, notices = sanitize_remediation_and_evidence(
            actions=actions,
            probable_causes=[],
            investigation_steps=[],
            target_os="Windows",
        )

        assert san_actions[0].command is None
        assert "OS dialect mismatch" in san_actions[0].action
        assert "OS DIALECT MISMATCH" in san_actions[0].precautions
        # Safe Windows inspection command should be added to investigation steps
        assert any("Get-Process" in s for s in san_steps)


class TestServiceSafetyIntegration:
    """Test suite verifying AIDiagnosticService end-to-end integration with safety guardrails."""

    def test_service_sanitizes_dangerous_mocked_llm_response(self, tmp_path: Path) -> None:
        """Verify AIDiagnosticService neutralizes dangerous LLM commands and preserves ML scores."""
        async def _test() -> None:
            settings = load_config(
                database_path=tmp_path / "test_safety_service.db",
                ai_enabled=True,
                ai_provider="ollama",
            )
            settings.ensure_directories()
            dash_service = DashboardService(settings=settings)

            # Malicious/hallucinated model response attempting to kill System Idle Process with kill -9
            dangerous_llm_output = {
                "incident_summary": "System Idle Process is consuming all processor power.",
                "probable_causes": [
                    {
                        "rank": 1,
                        "hypothesis": "High CPU utilization caused by System Idle Process.",
                        "confidence": "HIGH",
                        "supporting_evidence": ["System Idle Process at 500%"],
                    }
                ],
                "investigation_steps": ["top -b -n 1 | grep System+Idle+Process"],
                "remediation_actions": [
                    {
                        "step_number": 1,
                        "action": "Terminate System Idle Process immediately.",
                        "command": "kill -9 $(pidof -s -x System+Idle+Process)",
                        "safety_level": "CAUTION",
                        "precautions": "Run as root.",
                    }
                ],
                "uncertainty_assessment": "Unobserved storage telemetry.",
            }

            envelope = {
                "model": "qwen2.5:3b",
                "response": json.dumps(dangerous_llm_output),
                "done": True,
            }

            async def mock_handler(request: httpx.Request) -> httpx.Response:
                return httpx.Response(200, json=envelope)

            mock_client = OllamaClient(
                base_url="http://mock-ollama:11434",
                transport=httpx.MockTransport(mock_handler),
            )

            service = AIDiagnosticService(
                settings=settings,
                dashboard_service=dash_service,
                client=mock_client,
            )

            diagnosis = await service.diagnose_latest()

            assert isinstance(diagnosis, AIIncidentDiagnosis)
            assert diagnosis.is_fallback is False

            # Verify command was neutralized
            assert diagnosis.remediation_actions[0].command is None
            assert diagnosis.remediation_actions[0].safety_level == SafetyLevel.SAFE

            # Verify safety notices in metadata
            assert "safety_notices" in diagnosis.metadata
            assert len(diagnosis.metadata["safety_notices"]) >= 1

            # Verify authoritative ML scores preserved
            assert diagnosis.health_score is None or (0.0 <= diagnosis.health_score <= 100.0)
            assert 0.0 <= diagnosis.anomaly_score <= 1.0

        asyncio.run(_test())
