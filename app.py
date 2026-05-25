import html
import platform
import shutil
import socket
import subprocess
import time
from pathlib import Path
from string import Template

from flask import Flask

app = Flask(__name__)


def read_key_value_file(path):
    data = {}
    try:
        for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            data[key.strip()] = value.strip().strip('"')
    except OSError:
        pass
    return data


def read_cpu_model():
    candidates = []
    try:
        for line in Path("/proc/cpuinfo").read_text(encoding="utf-8", errors="replace").splitlines():
            if ":" not in line:
                continue

            key, value = [part.strip() for part in line.split(":", 1)]
            key = key.lower()
            if key in {"model name", "hardware", "processor"} and value and not value.isdigit():
                candidates.append(value)
    except OSError:
        pass
    return candidates[0] if candidates else platform.processor() or "-"


def bytes_to_gib(value):
    try:
        return f"{value / (1024 ** 3):.1f} GiB"
    except (TypeError, ValueError):
        return "-"


def memory_info():
    values = {}
    try:
        for line in Path("/proc/meminfo").read_text(encoding="utf-8", errors="replace").splitlines():
            key, raw_value = line.split(":", 1)
            values[key] = int(raw_value.strip().split()[0]) * 1024
    except (OSError, ValueError, IndexError):
        return {"total": "-", "available": "-"}

    return {
        "total": bytes_to_gib(values.get("MemTotal")),
        "available": bytes_to_gib(values.get("MemAvailable")),
    }


def uptime_info():
    try:
        seconds = int(float(Path("/proc/uptime").read_text(encoding="utf-8").split()[0]))
    except (OSError, ValueError, IndexError):
        return "-"

    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, _ = divmod(remainder, 60)

    parts = []
    if days:
        parts.append(f"{days} hari")
    if hours:
        parts.append(f"{hours} jam")
    parts.append(f"{minutes} menit")
    return " ".join(parts)


def default_route_ip():
    ip_command = shutil.which("ip")
    if not ip_command:
        return "-"

    try:
        result = subprocess.run(
            [ip_command, "-4", "route", "get", "1.1.1.1"],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "-"

    words = result.stdout.split()
    if "src" in words:
        index = words.index("src") + 1
        if index < len(words):
            return words[index]
    return "-"


def network_interfaces():
    ip_command = shutil.which("ip")
    if not ip_command:
        return []

    try:
        result = subprocess.run(
            [ip_command, "-o", "-4", "addr", "show"],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []

    interfaces = []
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 4:
            interfaces.append({"name": parts[1], "address": parts[3]})
    return interfaces


def disk_info():
    usage = shutil.disk_usage("/")
    return {
        "total": bytes_to_gib(usage.total),
        "used": bytes_to_gib(usage.used),
        "free": bytes_to_gib(usage.free),
        "percent": f"{usage.used / usage.total * 100:.0f}%" if usage.total else "-",
    }


def collect_system_info():
    os_release = read_key_value_file("/etc/os-release")
    armbian_release = read_key_value_file("/etc/armbian-release")
    memory = memory_info()
    disk = disk_info()
    interfaces = network_interfaces()

    return {
        "hostname": socket.gethostname(),
        "os_name": os_release.get("PRETTY_NAME", platform.platform()),
        "armbian_version": armbian_release.get("VERSION", "-"),
        "armbian_board": armbian_release.get("BOARD", "-"),
        "armbian_family": armbian_release.get("BOARD_NAME", armbian_release.get("FAMILY", "-")),
        "kernel": platform.release(),
        "architecture": platform.machine(),
        "cpu_model": read_cpu_model(),
        "cpu_cores": str(os_cpu_count() or "-"),
        "memory_total": memory["total"],
        "memory_available": memory["available"],
        "disk_total": disk["total"],
        "disk_used": disk["used"],
        "disk_free": disk["free"],
        "disk_percent": disk["percent"],
        "uptime": uptime_info(),
        "ip_address": default_route_ip(),
        "interfaces": interfaces,
        "armbian_release": armbian_release,
        "last_update": time.strftime("%Y-%m-%d %H:%M:%S %Z"),
    }


def os_cpu_count():
    try:
        count = len([entry for entry in Path("/sys/devices/system/cpu").glob("cpu[0-9]*")])
        return count or None
    except OSError:
        return None


def escape(value):
    return html.escape(str(value), quote=True)


def info_row(label, value):
    return f"""
                    <div class="info-row">
                        <span>{escape(label)}</span>
                        <strong>{escape(value)}</strong>
                    </div>
    """


def render_key_value_rows(data):
    if not data:
        return info_row("Status", "File /etc/armbian-release tidak ditemukan")

    return "".join(info_row(key, value) for key, value in sorted(data.items()))


def render_interfaces(interfaces):
    if not interfaces:
        return info_row("Interface", "Tidak terdeteksi")

    return "".join(info_row(item["name"], item["address"]) for item in interfaces)


@app.route("/")
def home():
    system = collect_system_info()
    armbian_rows = render_key_value_rows(system["armbian_release"])
    interface_rows = render_interfaces(system["interfaces"])
    disk_used = f'{system["disk_used"]} ({system["disk_percent"]})'
    summary_left = "".join(
        [
            info_row("Armbian", system["armbian_version"]),
            info_row("Board", system["armbian_board"]),
            info_row("Board Name", system["armbian_family"]),
            info_row("Arsitektur", system["architecture"]),
            info_row("CPU", system["cpu_model"]),
            info_row("Core CPU", system["cpu_cores"]),
        ]
    )
    summary_right = "".join(
        [
            info_row("Memori Total", system["memory_total"]),
            info_row("Memori Tersedia", system["memory_available"]),
            info_row("Disk / Total", system["disk_total"]),
            info_row("Disk / Terpakai", disk_used),
            info_row("Disk / Kosong", system["disk_free"]),
            info_row("Uptime", system["uptime"]),
        ]
    )

    page = Template("""
    <!DOCTYPE html>
    <html lang="id">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Armbian Linux Dashboard</title>

        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
                font-family: Arial, sans-serif;
            }

            body {
                background: #f4f7fb;
                color: #1f2937;
            }

            .container {
                display: flex;
                min-height: 100vh;
            }

            .sidebar {
                width: 250px;
                background: #182235;
                color: white;
                padding: 25px 20px;
            }

            .sidebar h2 {
                margin-bottom: 35px;
                font-size: 22px;
            }

            .sidebar a {
                display: block;
                color: #d1d5db;
                text-decoration: none;
                margin: 18px 0;
                padding: 12px;
                border-radius: 10px;
                transition: 0.3s;
            }

            .sidebar a:hover {
                background: #374151;
                color: white;
            }

            .main {
                flex: 1;
                padding: 30px;
            }

            .header {
                background: white;
                padding: 25px;
                border-radius: 8px;
                box-shadow: 0 8px 25px rgba(0,0,0,0.08);
                margin-bottom: 30px;
            }

            .header h1 {
                font-size: 32px;
                color: #111827;
                margin-bottom: 8px;
            }

            .header p {
                color: #6b7280;
            }

            .cards {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
                gap: 20px;
                margin-bottom: 30px;
            }

            .card {
                background: white;
                padding: 25px;
                border-radius: 8px;
                box-shadow: 0 8px 25px rgba(0,0,0,0.08);
            }

            .card h3 {
                font-size: 16px;
                color: #6b7280;
                margin-bottom: 12px;
            }

            .card .value {
                font-size: 28px;
                font-weight: bold;
                color: #111827;
                overflow-wrap: anywhere;
            }

            .status-online {
                display: inline-block;
                margin-top: 10px;
                padding: 7px 14px;
                background: #dcfce7;
                color: #166534;
                border-radius: 999px;
                font-size: 14px;
                font-weight: bold;
            }

            .panel {
                background: white;
                padding: 25px;
                border-radius: 8px;
                box-shadow: 0 8px 25px rgba(0,0,0,0.08);
                margin-bottom: 30px;
            }

            .panel h2 {
                margin-bottom: 15px;
            }

            .grid-two {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
                gap: 20px;
            }

            .info-list {
                border: 1px solid #e5e7eb;
                border-radius: 8px;
                overflow: hidden;
            }

            .info-row {
                display: grid;
                grid-template-columns: minmax(120px, 0.9fr) minmax(0, 1.5fr);
                gap: 16px;
                padding: 13px 15px;
                border-bottom: 1px solid #e5e7eb;
                align-items: start;
            }

            .info-row:last-child {
                border-bottom: 0;
            }

            .info-row span {
                color: #6b7280;
                font-size: 14px;
            }

            .info-row strong {
                color: #111827;
                font-size: 14px;
                overflow-wrap: anywhere;
            }

            .button {
                display: inline-block;
                margin-top: 20px;
                padding: 12px 20px;
                background: #2563eb;
                color: white;
                text-decoration: none;
                border-radius: 10px;
                transition: 0.3s;
            }

            .button:hover {
                background: #1d4ed8;
            }

            @media (max-width: 768px) {
                .container {
                    flex-direction: column;
                }

                .sidebar {
                    width: 100%;
                }

                .info-row {
                    grid-template-columns: 1fr;
                    gap: 6px;
                }
            }
        </style>
    </head>

    <body>
        <div class="container">

            <div class="sidebar">
                <h2>Armbian UI</h2>
                <a href="#">Dashboard</a>
                <a href="#">Monitoring</a>
                <a href="#">Device Info</a>
                <a href="#">Settings</a>
            </div>

            <div class="main">

                <div class="header">
                    <h1>Dashboard Armbian Linux</h1>
                    <p>Konfigurasi sistem dibaca langsung dari perangkat Linux ini.</p>
                    <span class="status-online">Server Online</span>
                </div>

                <div class="cards">
                    <div class="card">
                        <h3>Hostname</h3>
                        <div class="value">$hostname</div>
                    </div>

                    <div class="card">
                        <h3>OS</h3>
                        <div class="value">$os_name</div>
                    </div>

                    <div class="card">
                        <h3>Kernel</h3>
                        <div class="value">$kernel</div>
                    </div>

                    <div class="card">
                        <h3>IP Utama</h3>
                        <div class="value">$ip_address</div>
                    </div>
                </div>

                <div class="panel">
                    <h2>Ringkasan Sistem</h2>
                    <div class="grid-two">
                        <div class="info-list">
                            $summary_left
                        </div>

                        <div class="info-list">
                            $summary_right
                        </div>
                    </div>

                    <a href="/" class="button">Refresh Dashboard</a>
                </div>

                <div class="grid-two">
                    <div class="panel">
                        <h2>Network Interface</h2>
                        <div class="info-list">
                            $interface_rows
                        </div>
                    </div>

                    <div class="panel">
                        <h2>/etc/armbian-release</h2>
                        <div class="info-list">
                            $armbian_rows
                        </div>
                    </div>
                </div>

                <p>Update terakhir: $last_update</p>

            </div>
        </div>
    </body>
    </html>
    """)

    return page.safe_substitute(
        hostname=escape(system["hostname"]),
        os_name=escape(system["os_name"]),
        kernel=escape(system["kernel"]),
        ip_address=escape(system["ip_address"]),
        summary_left=summary_left,
        summary_right=summary_right,
        interface_rows=interface_rows,
        armbian_rows=armbian_rows,
        last_update=escape(system["last_update"]),
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
