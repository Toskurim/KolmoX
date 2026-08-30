"""
KolmoX - Hardware Awareness and Dynamic Topology Profiler
Pure standard-library implementation for platform detection, memory profiling,
and GPU HW-accelerated video decoding capabilities.
"""
import os
import platform
import shutil
import subprocess
import ctypes
from dataclasses import dataclass
from typing import Optional


def _get_ram_info():
    """Retrieve total and available RAM using platform native APIs."""
    total_gb = 16.0
    avail_gb = 8.0
    
    plat = platform.system().lower()
    if plat == "windows":
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]
        stat = MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
            total_gb = stat.ullTotalPhys / (1024 ** 3)
            avail_gb = stat.ullAvailPhys / (1024 ** 3)
    elif plat == "darwin":
        try:
            total_bytes = int(os.popen("sysctl -n hw.memsize").read().strip())
            total_gb = total_bytes / (1024 ** 3)
            avail_gb = total_gb * 0.6
        except Exception:
            pass
    elif plat == "linux":
        try:
            with open("/proc/meminfo", "r") as f:
                lines = f.readlines()
            info = {}
            for line in lines:
                parts = line.split(":")
                if len(parts) == 2:
                    info[parts[0].strip()] = int(parts[1].split()[0])
            if "MemTotal" in info:
                total_gb = info["MemTotal"] / (1024 ** 2)
            if "MemAvailable" in info:
                avail_gb = info["MemAvailable"] / (1024 ** 2)
        except Exception:
            pass

    return total_gb, avail_gb


def find_ffmpeg_binary() -> Optional[str]:
    """Locate ffmpeg executable in system PATH, where.exe, or standard Winget locations."""
    # 1. Standard PATH
    found = shutil.which("ffmpeg")
    if found:
        return found

    # 2. Windows where.exe lookup
    if platform.system().lower() == "windows":
        try:
            res = subprocess.run(
                ["where.exe", "ffmpeg"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=2
            )
            if res.returncode == 0:
                first_line = res.stdout.strip().splitlines()[0].strip()
                if os.path.isfile(first_line):
                    return first_line
        except Exception:
            pass

        # 3. Direct Winget / Local AppData fallback scan
        local_app = os.environ.get("LOCALAPPDATA", "")
        if local_app:
            winget_pkgs = os.path.join(local_app, "Microsoft", "WinGet", "Packages")
            if os.path.isdir(winget_pkgs):
                for root, _, files in os.walk(winget_pkgs):
                    if "ffmpeg.exe" in files:
                        return os.path.join(root, "ffmpeg.exe")

    return None


def _detect_hw_accel_backend(is_apple: bool) -> Optional[str]:
    """Detect if FFmpeg is available and which HW decoding backend is supported."""
    ffmpeg_bin = find_ffmpeg_binary()
    if not ffmpeg_bin:
        return None

    if is_apple:
        return "videotoolbox"

    try:
        res = subprocess.run(
            [ffmpeg_bin, "-hwaccels"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=3
        )
        output = res.stdout.lower()
        if "cuda" in output:
            return "cuda"
        if "nvdec" in output:
            return "nvdec"
        if "d3d11va" in output:
            return "d3d11va"
        if "dxva2" in output:
            return "dxva2"
        if "vaapi" in output:
            return "vaapi"
    except Exception:
        pass

    return None


@dataclass
class HardwareProfile:
    platform_name: str
    machine_arch: str
    logical_cores: int
    total_ram_gb: float
    available_ram_gb: float
    is_apple_silicon: bool
    hwaccel_backend: Optional[str]
    recommended_workers: int
    recommended_chunk_frames: int

    @classmethod
    def detect(cls) -> "HardwareProfile":
        plat = platform.system().lower()
        arch = platform.machine().lower()
        
        log_cores = os.cpu_count() or 8
        total_ram, avail_ram = _get_ram_info()
        
        is_apple = (plat == "darwin") and ("arm" in arch or "arm64" in arch)
        hwaccel = _detect_hw_accel_backend(is_apple)
        recommended_workers = max(2, log_cores)
        
        if avail_ram > 32:
            chunk_frames = 120
        elif avail_ram > 16:
            chunk_frames = 60
        else:
            chunk_frames = 30

        return cls(
            platform_name=plat,
            machine_arch=arch,
            logical_cores=log_cores,
            total_ram_gb=round(total_ram, 2),
            available_ram_gb=round(avail_ram, 2),
            is_apple_silicon=is_apple,
            hwaccel_backend=hwaccel,
            recommended_workers=recommended_workers,
            recommended_chunk_frames=chunk_frames
        )