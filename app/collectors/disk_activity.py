"""Disk activity provider subsystem using native operating system performance counters.

Provides reliable disk active time percentage (% Disk Time / % Idle Time) and I/O throughput
using Windows Performance Data Helper (PDH) via ctypes on Windows, with graceful
fallback to a null provider on unsupported platforms or when counters are unavailable.
"""

from __future__ import annotations

import ctypes
import sys
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from app.core.logging_config import get_logger

logger = get_logger("app.collectors.disk_activity")


@dataclass(frozen=True)
class DiskActivityMetrics:
    """Snapshot of physical disk activity and throughput.

    Attributes:
        active_time_percent: Percentage of measurement interval the disk was busy (0.0 - 100.0).
            None if counter is unavailable or unprimed.
        read_bytes_per_sec: Rate of data read from disk in bytes/sec, or None if unavailable.
        write_bytes_per_sec: Rate of data written to disk in bytes/sec, or None if unavailable.
    """

    active_time_percent: Optional[float] = None
    read_bytes_per_sec: Optional[float] = None
    write_bytes_per_sec: Optional[float] = None


class BaseDiskActivityProvider(ABC):
    """Abstract base provider for disk activity metrics."""

    @abstractmethod
    def get_activity(self) -> DiskActivityMetrics:
        """Harvest disk activity metrics.

        Returns:
            DiskActivityMetrics instance.
        """
        raise NotImplementedError

    def close(self) -> None:
        """Release any underlying system handles or queries."""
        pass


class NullDiskActivityProvider(BaseDiskActivityProvider):
    """Fallback provider when native disk activity counters are unsupported or unavailable."""

    def get_activity(self) -> DiskActivityMetrics:
        return DiskActivityMetrics(
            active_time_percent=None,
            read_bytes_per_sec=None,
            write_bytes_per_sec=None,
        )


class WindowsPdhDiskActivityProvider(BaseDiskActivityProvider):
    """Harvests physical disk active time and throughput using Windows PDH.

    Queries:
        - \\PhysicalDisk(<instance>)\\% Idle Time (per physical disk)
        - \\PhysicalDisk(_Total)\\% Idle Time (storage subsystem aggregate)
        - \\PhysicalDisk(_Total)\\% Disk Time (secondary fallback)
        - \\PhysicalDisk(_Total)\\Disk Read Bytes/sec
        - \\PhysicalDisk(_Total)\\Disk Write Bytes/sec

    Active time calculation:
        In Windows Task Manager and performance monitor, disk active time reflects
        the percentage of time the storage controller was actively servicing read or write
        requests. The authoritative counter bounded between 0% and 100% is % Idle Time:
            Active Time (%) = max(0.0, min(100.0, 100.0 - % Idle Time))
        This avoids the counter inflation inherent in % Disk Time, which sums queued/overlapping
        requests across NVMe/NCQ storage controllers and frequently exceeds 100%.
    """

    def __init__(self, prime_on_init: bool = True) -> None:
        """Initialize Windows PDH query and performance counters.

        Args:
            prime_on_init: If True, executes an initial collection to prime rate counters.
        """
        self._initialized = False
        self._h_query = None
        self._drive_instances: list[str] = []
        self._h_drive_idle: dict[str, Any] = {}
        self._h_total_idle = None
        self._h_counter_active = None
        self._h_counter_read = None
        self._h_counter_write = None
        self._last_collect_time: float = 0.0

        if sys.platform != "win32":
            logger.debug("WindowsPdhDiskActivityProvider disabled: non-Windows platform (%s).", sys.platform)
            return

        self._setup_pdh(prime_on_init=prime_on_init)

    def _setup_pdh(self, prime_on_init: bool) -> None:
        """Set up PDH query and add performance counters."""
        try:
            from ctypes import byref, c_double, c_ulong, create_unicode_buffer, wintypes

            pdh = ctypes.windll.pdh

            class PDH_FmtCounterValue(ctypes.Structure):
                _fields_ = [("CStatus", c_ulong), ("doubleValue", c_double)]

            self._PDH_FmtCounterValue = PDH_FmtCounterValue
            self._PDH_FMT_DOUBLE = 0x00000200

            h_query = wintypes.HANDLE()
            status = pdh.PdhOpenQueryW(None, 0, byref(h_query))
            if status != 0:
                logger.debug("PdhOpenQueryW failed with status: 0x%08X", status)
                return

            self._h_query = h_query

            # Discover concrete physical disk instances (e.g., '0 C: D: E:' or '0 C:', '1 D:')
            try:
                c_size = c_ulong(0)
                i_size = c_ulong(0)
                pdh.PdhEnumObjectItemsW(None, None, "PhysicalDisk", None, byref(c_size), None, byref(i_size), 400, 0)
                if i_size.value > 0:
                    c_buf = create_unicode_buffer(c_size.value)
                    i_buf = create_unicode_buffer(i_size.value)
                    if pdh.PdhEnumObjectItemsW(None, None, "PhysicalDisk", c_buf, byref(c_size), i_buf, byref(i_size), 400, 0) == 0:
                        raw = i_buf[:]
                        items = []
                        curr = []
                        for ch in raw:
                            if ch == '\x00':
                                if curr:
                                    items.append("".join(curr))
                                    curr = []
                                else:
                                    break
                            else:
                                curr.append(ch)
                        self._drive_instances = [inst for inst in items if inst != "_Total"]
            except Exception as enum_exc:
                logger.debug("PhysicalDisk instance enumeration encountered an error: %s", enum_exc)

            # Add per-drive idle counters for individual physical drives
            self._h_drive_idle = {}
            for drive in self._drive_instances:
                h_idle = wintypes.HANDLE()
                res = pdh.PdhAddCounterW(
                    self._h_query,
                    f"\\PhysicalDisk({drive})\\% Idle Time",
                    0,
                    byref(h_idle),
                )
                if res == 0:
                    self._h_drive_idle[drive] = h_idle

            # Add aggregate % Idle Time counter on _Total
            h_total_idle = wintypes.HANDLE()
            res_total_idle = pdh.PdhAddCounterW(
                self._h_query,
                "\\PhysicalDisk(_Total)\\% Idle Time",
                0,
                byref(h_total_idle),
            )
            if res_total_idle == 0:
                self._h_total_idle = h_total_idle

            # Add fallback % Disk Time counter on _Total
            h_active = wintypes.HANDLE()
            res_active = pdh.PdhAddCounterW(
                self._h_query,
                "\\PhysicalDisk(_Total)\\% Disk Time",
                0,
                byref(h_active),
            )
            if res_active == 0:
                self._h_counter_active = h_active

            # Add throughput rate counters
            h_read = wintypes.HANDLE()
            res_read = pdh.PdhAddCounterW(
                self._h_query,
                "\\PhysicalDisk(_Total)\\Disk Read Bytes/sec",
                0,
                byref(h_read),
            )
            if res_read == 0:
                self._h_counter_read = h_read

            h_write = wintypes.HANDLE()
            res_write = pdh.PdhAddCounterW(
                self._h_query,
                "\\PhysicalDisk(_Total)\\Disk Write Bytes/sec",
                0,
                byref(h_write),
            )
            if res_write == 0:
                self._h_counter_write = h_write

            self._initialized = True

            if prime_on_init:
                pdh.PdhCollectQueryData(self._h_query)
                self._last_collect_time = time.monotonic()

            logger.debug(
                "Windows PDH Disk Activity provider successfully initialized (instances: %s).",
                self._drive_instances or ["_Total"],
            )
        except Exception as exc:
            logger.debug("Windows PDH initialization encountered an error: %s", exc)
            self.close()

    def get_activity(self) -> DiskActivityMetrics:
        """Collect current disk active percentage and throughput rates."""
        if not self._initialized or not self._h_query:
            return DiskActivityMetrics(None, None, None)

        try:
            pdh = ctypes.windll.pdh
            from ctypes import byref

            now = time.monotonic()
            elapsed = now - self._last_collect_time if self._last_collect_time > 0 else 0.0

            # If unprimed or called with virtually zero elapsed time, do a small sleep to sample
            if self._last_collect_time == 0.0 or elapsed < 0.1:
                pdh.PdhCollectQueryData(self._h_query)
                time.sleep(0.1)

            status = pdh.PdhCollectQueryData(self._h_query)
            self._last_collect_time = time.monotonic()

            if status != 0:
                logger.debug("PdhCollectQueryData returned status: 0x%08X", status)
                return DiskActivityMetrics(None, None, None)

            active_pct: Optional[float] = None
            read_rate: Optional[float] = None
            write_rate: Optional[float] = None

            # Strategy 1: Check per-drive % Idle Time counters (deliberate multi-disk handling)
            per_drive_actives: list[float] = []
            for drive, h_counter in self._h_drive_idle.items():
                val = self._PDH_FmtCounterValue()
                res = pdh.PdhGetFormattedCounterValue(
                    h_counter,
                    self._PDH_FMT_DOUBLE,
                    None,
                    byref(val),
                )
                if res == 0 and val.CStatus == 0:
                    drive_active = max(0.0, min(100.0, 100.0 - float(val.doubleValue)))
                    per_drive_actives.append(drive_active)

            if per_drive_actives:
                # If multiple physical disks are present, report the maximum active percentage
                # among physical disks, which accurately identifies storage saturation and bottlenecks
                active_pct = round(max(per_drive_actives), 2)

            # Strategy 2: If per-drive counters were unavailable, evaluate aggregate _Total % Idle Time
            if active_pct is None and self._h_total_idle:
                val = self._PDH_FmtCounterValue()
                res = pdh.PdhGetFormattedCounterValue(
                    self._h_total_idle,
                    self._PDH_FMT_DOUBLE,
                    None,
                    byref(val),
                )
                if res == 0 and val.CStatus == 0:
                    active_pct = round(max(0.0, min(100.0, 100.0 - float(val.doubleValue))), 2)

            # Strategy 3: Fallback to % Disk Time if % Idle Time is not supported on this host
            if active_pct is None and self._h_counter_active:
                val = self._PDH_FmtCounterValue()
                res = pdh.PdhGetFormattedCounterValue(
                    self._h_counter_active,
                    self._PDH_FMT_DOUBLE,
                    None,
                    byref(val),
                )
                if res == 0 and val.CStatus == 0:
                    raw_val = float(val.doubleValue)
                    active_pct = round(max(0.0, min(100.0, raw_val)), 2)

            if self._h_counter_read:
                val = self._PDH_FmtCounterValue()
                res = pdh.PdhGetFormattedCounterValue(
                    self._h_counter_read,
                    self._PDH_FMT_DOUBLE,
                    None,
                    byref(val),
                )
                if res == 0 and val.CStatus == 0:
                    read_rate = round(max(0.0, float(val.doubleValue)), 2)

            if self._h_counter_write:
                val = self._PDH_FmtCounterValue()
                res = pdh.PdhGetFormattedCounterValue(
                    self._h_counter_write,
                    self._PDH_FMT_DOUBLE,
                    None,
                    byref(val),
                )
                if res == 0 and val.CStatus == 0:
                    write_rate = round(max(0.0, float(val.doubleValue)), 2)

            return DiskActivityMetrics(
                active_time_percent=active_pct,
                read_bytes_per_sec=read_rate,
                write_bytes_per_sec=write_rate,
            )
        except Exception as exc:
            logger.debug("Error querying PDH disk activity: %s", exc)
            return DiskActivityMetrics(None, None, None)

    def close(self) -> None:
        """Release PDH query handle and counters."""
        if self._h_query:
            try:
                pdh = ctypes.windll.pdh
                pdh.PdhCloseQuery(self._h_query)
            except Exception:
                pass
            self._h_query = None
        self._h_drive_idle.clear()
        self._drive_instances.clear()
        self._h_total_idle = None
        self._h_counter_active = None
        self._h_counter_read = None
        self._h_counter_write = None
        self._initialized = False


def create_default_disk_activity_provider() -> BaseDiskActivityProvider:
    """Factory creating the best available disk activity provider for the current OS."""
    if sys.platform == "win32":
        try:
            provider = WindowsPdhDiskActivityProvider(prime_on_init=True)
            if provider._initialized:
                return provider
        except Exception as err:
            logger.debug("Failed to instantiate WindowsPdhDiskActivityProvider: %s", err)

    return NullDiskActivityProvider()
