"""
Comprehensive system data collector for the Sipeed NanoCluster Agent.
Uses psutil for cross-platform system monitoring.
"""

import os
import re
import time
import socket
import platform
import threading
from typing import Dict, List, Any, Optional

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False


class AgentSystemReader:
    """Collects comprehensive system metrics with background sampling for rate calculations."""

    def __init__(self, logger, thermal_path: str = "/sys/class/thermal/thermal_zone0/temp"):
        self.logger = logger
        self.thermal_path = thermal_path

        if not PSUTIL_AVAILABLE:
            self.logger.warning("psutil not available - /api/system endpoint will not work")
            return

        # Rate tracking state
        self._lock = threading.Lock()
        self._prev_disk_io = None
        self._prev_net_io = None
        self._prev_time = None
        self._disk_io_rates: Dict[str, Dict[str, float]] = {}
        self._net_io_rates: Dict[str, Dict[str, float]] = {}
        self._cpu_percent: float = 0.0
        self._cpu_per_core: List[float] = []

        # Boot time
        self._boot_time = psutil.boot_time()

        # Initialize CPU percent tracking (first call always returns 0)
        psutil.cpu_percent(percpu=True)

        # Start background sampling thread
        self._running = True
        self._sample_thread = threading.Thread(target=self._sample_loop, daemon=True)
        self._sample_thread.start()
        self.logger.info("System reader started with background sampling")

    @property
    def available(self) -> bool:
        return PSUTIL_AVAILABLE

    def stop(self):
        """Stop the background sampling thread."""
        self._running = False

    # ── Background sampling ────────────────────────────────────────────

    def _sample_loop(self):
        """Background loop – samples CPU usage and I/O counters every 2 seconds."""
        while self._running:
            try:
                self._sample()
            except Exception as e:
                self.logger.error(f"Sampling error: {e}")
            time.sleep(2)

    def _sample(self):
        now = time.time()

        # CPU usage (non-blocking because we initialized with a prior call)
        per_core = psutil.cpu_percent(interval=0, percpu=True)
        total_cpu = sum(per_core) / len(per_core) if per_core else 0.0

        # Disk I/O counters
        try:
            disk_io = psutil.disk_io_counters(perdisk=True)
        except Exception:
            disk_io = None

        # Network I/O counters
        try:
            net_io = psutil.net_io_counters(pernic=True)
        except Exception:
            net_io = None

        with self._lock:
            self._cpu_percent = total_cpu
            self._cpu_per_core = per_core

            if self._prev_time:
                dt = now - self._prev_time
                if dt > 0:
                    # Disk I/O rates
                    if disk_io and self._prev_disk_io:
                        for disk, counters in disk_io.items():
                            prev = self._prev_disk_io.get(disk)
                            if prev:
                                self._disk_io_rates[disk] = {
                                    'read_bytes_per_sec': max(0, (counters.read_bytes - prev.read_bytes) / dt),
                                    'write_bytes_per_sec': max(0, (counters.write_bytes - prev.write_bytes) / dt),
                                }

                    # Network I/O rates
                    if net_io and self._prev_net_io:
                        for nic, counters in net_io.items():
                            prev = self._prev_net_io.get(nic)
                            if prev:
                                self._net_io_rates[nic] = {
                                    'bytes_sent_per_sec': max(0, (counters.bytes_sent - prev.bytes_sent) / dt),
                                    'bytes_recv_per_sec': max(0, (counters.bytes_recv - prev.bytes_recv) / dt),
                                }

            self._prev_disk_io = disk_io
            self._prev_net_io = net_io
            self._prev_time = now

    # ── Public API ─────────────────────────────────────────────────────

    def read_temperature(self) -> Optional[float]:
        """Read CPU temperature from the thermal zone file."""
        try:
            if not os.path.exists(self.thermal_path):
                return None
            with open(self.thermal_path, 'r') as f:
                return float(f.read().strip()) / 1000.0
        except Exception as e:
            self.logger.error(f"Error reading temperature: {e}")
            return None

    def get_system_data(self, description: str = "") -> Dict[str, Any]:
        """Collect and return all system metrics."""
        if not PSUTIL_AVAILABLE:
            return {'error': 'psutil not available'}

        with self._lock:
            cpu_percent = self._cpu_percent
            cpu_per_core = list(self._cpu_per_core)
            disk_io_rates = dict(self._disk_io_rates)
            net_io_rates = dict(self._net_io_rates)

        return {
            'hostname': socket.gethostname(),
            'description': description,
            'uptime': time.time() - self._boot_time,
            'temperature': self.read_temperature(),
            'os': self._get_os_info(),
            'cpu': self._get_cpu_info(cpu_percent, cpu_per_core),
            'memory': self._get_memory_info(),
            'disks': self._get_disk_info(disk_io_rates),
            'network': self._get_network_info(net_io_rates),
            'processes': len(psutil.pids()),
        }

    # ── OS info ────────────────────────────────────────────────────────

    def _get_os_info(self) -> Dict[str, str]:
        os_name = "Unknown"
        try:
            if os.path.exists('/etc/os-release'):
                with open('/etc/os-release') as f:
                    for line in f:
                        if line.startswith('PRETTY_NAME='):
                            os_name = line.split('=', 1)[1].strip().strip('"')
                            break
        except Exception:
            pass

        return {
            'name': os_name,
            'kernel': platform.release(),
            'architecture': platform.machine(),
        }

    # ── CPU info ───────────────────────────────────────────────────────

    def _get_cpu_info(self, cpu_percent: float, cpu_per_core: List[float]) -> Dict[str, Any]:
        cpu_freq = psutil.cpu_freq()
        load_avg = list(os.getloadavg()) if hasattr(os, 'getloadavg') else [0, 0, 0]

        model = self._read_cpu_model()

        return {
            'model': model,
            'cores': psutil.cpu_count(logical=True),
            'frequency': {
                'current': round(cpu_freq.current, 0) if cpu_freq else 0,
                'min': round(cpu_freq.min, 0) if cpu_freq and cpu_freq.min else 0,
                'max': round(cpu_freq.max, 0) if cpu_freq and cpu_freq.max else 0,
            },
            'usage_percent': round(cpu_percent, 1),
            'per_core_percent': [round(p, 1) for p in cpu_per_core],
            'load_average': [round(v, 2) for v in load_avg],
        }

    @staticmethod
    def _read_cpu_model() -> str:
        try:
            if os.path.exists('/proc/cpuinfo'):
                with open('/proc/cpuinfo') as f:
                    for line in f:
                        # ARM uses "model name" or "Model"
                        if line.lower().startswith('model name'):
                            return line.split(':', 1)[1].strip()
                # Fallback: look for "Hardware" line on ARM
                with open('/proc/cpuinfo') as f:
                    for line in f:
                        if line.startswith('Hardware'):
                            return line.split(':', 1)[1].strip()
        except Exception:
            pass
        return "Unknown"

    # ── Memory info ────────────────────────────────────────────────────

    @staticmethod
    def _get_memory_info() -> Dict[str, Any]:
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()

        return {
            'total': mem.total,
            'used': mem.used,
            'available': mem.available,
            'percent': mem.percent,
            'swap_total': swap.total,
            'swap_used': swap.used,
            'swap_percent': swap.percent,
        }

    # ── Disk info ──────────────────────────────────────────────────────

    def _get_disk_info(self, disk_io_rates: Dict) -> List[Dict[str, Any]]:
        disks = []
        seen_devices = set()

        for partition in psutil.disk_partitions(all=False):
            if partition.device in seen_devices:
                continue
            seen_devices.add(partition.device)

            # Skip special filesystems
            if partition.fstype in ('squashfs', 'tmpfs', 'devtmpfs', 'overlay'):
                continue

            try:
                usage = psutil.disk_usage(partition.mountpoint)
            except (PermissionError, OSError):
                continue

            dev_basename = os.path.basename(partition.device)
            io_device = self._partition_to_base_device(dev_basename)
            io_rates = disk_io_rates.get(io_device, {})

            disks.append({
                'device': partition.device,
                'mountpoint': partition.mountpoint,
                'filesystem': partition.fstype,
                'type': self._detect_disk_type(partition.device),
                'total': usage.total,
                'used': usage.used,
                'free': usage.free,
                'percent': usage.percent,
                'io_read_bytes_per_sec': round(io_rates.get('read_bytes_per_sec', 0)),
                'io_write_bytes_per_sec': round(io_rates.get('write_bytes_per_sec', 0)),
            })

        return disks

    @staticmethod
    def _partition_to_base_device(partition_name: str) -> str:
        """Convert partition name to base device name for I/O tracking.
        e.g. mmcblk0p1 → mmcblk0, nvme0n1p1 → nvme0n1, sda1 → sda
        """
        if 'mmcblk' in partition_name or 'nvme' in partition_name:
            return re.sub(r'p\d+$', '', partition_name)
        return re.sub(r'\d+$', '', partition_name)

    def _detect_disk_type(self, device: str) -> str:
        """Detect storage type: NVMe, eMMC, SD, SATA/USB, etc."""
        basename = os.path.basename(device)
        base = self._partition_to_base_device(basename)

        if 'nvme' in base:
            return "NVMe"
        elif 'mmcblk' in base:
            return self._detect_mmc_type(base)
        elif base.startswith('sd'):
            return self._detect_scsi_type(base)
        elif 'loop' in base:
            return "Loop"
        return "Other"

    @staticmethod
    def _detect_mmc_type(base_device: str) -> str:
        """Distinguish eMMC from SD card via sysfs."""
        type_path = f"/sys/block/{base_device}/device/type"
        try:
            if os.path.exists(type_path):
                with open(type_path) as f:
                    dtype = f.read().strip()
                if dtype == "MMC":
                    return "eMMC"
                if dtype == "SD":
                    return "SD"
        except Exception:
            pass
        return "SD/eMMC"

    @staticmethod
    def _detect_scsi_type(base_device: str) -> str:
        """Distinguish USB from SATA via sysfs symlink."""
        try:
            link = os.readlink(f"/sys/block/{base_device}")
            if 'usb' in link:
                return "USB"
            if 'ata' in link or 'sata' in link:
                return "SATA"
        except Exception:
            pass
        return "SATA/USB"

    # ── Network info ───────────────────────────────────────────────────

    def _get_network_info(self, net_io_rates: Dict) -> List[Dict[str, Any]]:
        interfaces = []
        addrs = psutil.net_if_addrs()
        net_io = psutil.net_io_counters(pernic=True)
        net_stats = psutil.net_if_stats()

        for nic_name, nic_addrs in sorted(addrs.items()):
            # Skip loopback and docker/veth interfaces
            if nic_name == 'lo' or nic_name.startswith('veth') or nic_name.startswith('br-'):
                continue

            # Find IPv4 address
            ipv4 = ''
            for addr in nic_addrs:
                if hasattr(addr.family, 'name') and addr.family.name == 'AF_INET':
                    ipv4 = addr.address
                    break
                # Fallback: check by value (AF_INET = 2)
                elif addr.family == 2:
                    ipv4 = addr.address
                    break

            # Determine connection status: interface must be up AND have an IPv4 address
            stats = net_stats.get(nic_name)
            is_up = stats.isup if stats else False
            connected = is_up and bool(ipv4)

            counters = net_io.get(nic_name)
            rates = net_io_rates.get(nic_name, {})

            interfaces.append({
                'name': nic_name,
                'ip': ipv4,
                'connected': connected,
                'bytes_sent_total': counters.bytes_sent if counters else 0,
                'bytes_recv_total': counters.bytes_recv if counters else 0,
                'bytes_sent_per_sec': round(rates.get('bytes_sent_per_sec', 0)),
                'bytes_recv_per_sec': round(rates.get('bytes_recv_per_sec', 0)),
            })

        return interfaces
