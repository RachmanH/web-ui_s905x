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
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
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
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
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
                    <div class="grid grid-cols-1 gap-1 border-b border-slate-200 px-4 py-3 last:border-b-0 sm:grid-cols-[150px_minmax(0,1fr)]">
                        <dt class="text-sm font-medium text-slate-500">{escape(label)}</dt>
                        <dd class="break-words text-sm font-semibold text-slate-900">{escape(value)}</dd>
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
        <script src="https://cdn.tailwindcss.com"></script>
        <script src="https://unpkg.com/lucide@latest"></script>
    </head>

    <body class="min-h-screen bg-slate-100 font-sans text-slate-900 antialiased">
        <div class="min-h-screen lg:flex">
            <aside class="bg-slate-950 text-white lg:sticky lg:top-0 lg:h-screen lg:w-72">
                <div class="flex items-center justify-between border-b border-white/10 px-5 py-5 lg:block">
                    <div>
                        <p class="text-xs font-semibold uppercase tracking-widest text-cyan-300">Web UI</p>
                        <h1 class="mt-1 text-2xl font-bold">Armbian</h1>
                    </div>
                    <span class="inline-flex items-center gap-2 rounded-full bg-emerald-400/10 px-3 py-1 text-xs font-semibold text-emerald-200">
                        <span class="h-2 w-2 rounded-full bg-emerald-400"></span>
                        Online
                    </span>
                </div>

                <nav class="grid grid-cols-2 gap-2 p-4 text-sm font-medium sm:grid-cols-4 lg:mt-4 lg:grid-cols-1">
                    <a class="flex items-center gap-3 rounded-lg bg-white/10 px-3 py-3 text-white" href="/">
                        <i data-lucide="layout-dashboard" class="h-4 w-4"></i>
                        Dashboard
                    </a>
                    <a class="flex items-center gap-3 rounded-lg px-3 py-3 text-slate-300 hover:bg-white/10 hover:text-white" href="#system">
                        <i data-lucide="server" class="h-4 w-4"></i>
                        Sistem
                    </a>
                    <a class="flex items-center gap-3 rounded-lg px-3 py-3 text-slate-300 hover:bg-white/10 hover:text-white" href="#network">
                        <i data-lucide="network" class="h-4 w-4"></i>
                        Network
                    </a>
                    <a class="flex items-center gap-3 rounded-lg px-3 py-3 text-slate-300 hover:bg-white/10 hover:text-white" href="#armbian">
                        <i data-lucide="file-cog" class="h-4 w-4"></i>
                        Armbian
                    </a>
                </nav>
            </aside>

            <main class="flex-1 p-4 sm:p-6 lg:p-8">
                <header class="mb-6 overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
                    <div class="border-b border-slate-100 px-5 py-5 sm:flex sm:items-start sm:justify-between sm:gap-6">
                        <div class="min-w-0">
                            <div class="flex flex-wrap items-center gap-2">
                                <span class="inline-flex items-center rounded-full bg-cyan-50 px-3 py-1 text-xs font-semibold text-cyan-700">Armbian Linux</span>
                                <span class="inline-flex items-center rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700">Server Online</span>
                            </div>
                            <h2 class="mt-3 text-2xl font-bold tracking-normal text-slate-950 sm:text-3xl">Dashboard Sistem</h2>
                            <p class="mt-2 max-w-3xl text-sm leading-6 text-slate-600">Konfigurasi dibaca langsung dari perangkat Linux ini.</p>
                        </div>

                        <a href="/" class="mt-4 inline-flex items-center justify-center gap-2 rounded-lg bg-cyan-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-cyan-700 sm:mt-0">
                            <i data-lucide="refresh-cw" class="h-4 w-4"></i>
                            Refresh
                        </a>
                    </div>

                    <div class="grid gap-px bg-slate-200 sm:grid-cols-2 xl:grid-cols-4">
                        <section class="bg-white p-5">
                            <div class="flex items-center justify-between gap-3">
                                <p class="text-sm font-medium text-slate-500">Hostname</p>
                                <span class="rounded-lg bg-cyan-50 p-2 text-cyan-700"><i data-lucide="square-terminal" class="h-5 w-5"></i></span>
                            </div>
                            <p class="mt-4 break-words text-xl font-bold text-slate-950">$hostname</p>
                        </section>

                        <section class="bg-white p-5">
                            <div class="flex items-center justify-between gap-3">
                                <p class="text-sm font-medium text-slate-500">OS</p>
                                <span class="rounded-lg bg-emerald-50 p-2 text-emerald-700"><i data-lucide="cpu" class="h-5 w-5"></i></span>
                            </div>
                            <p class="mt-4 break-words text-xl font-bold text-slate-950">$os_name</p>
                        </section>

                        <section class="bg-white p-5">
                            <div class="flex items-center justify-between gap-3">
                                <p class="text-sm font-medium text-slate-500">Kernel</p>
                                <span class="rounded-lg bg-amber-50 p-2 text-amber-700"><i data-lucide="box" class="h-5 w-5"></i></span>
                            </div>
                            <p class="mt-4 break-words text-xl font-bold text-slate-950">$kernel</p>
                        </section>

                        <section class="bg-white p-5">
                            <div class="flex items-center justify-between gap-3">
                                <p class="text-sm font-medium text-slate-500">IP Utama</p>
                                <span class="rounded-lg bg-violet-50 p-2 text-violet-700"><i data-lucide="router" class="h-5 w-5"></i></span>
                            </div>
                            <p class="mt-4 break-words text-xl font-bold text-slate-950">$ip_address</p>
                        </section>
                    </div>
                </header>

                <section id="system" class="mb-6 rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
                    <div class="mb-4 flex flex-wrap items-center justify-between gap-3">
                        <div>
                            <p class="text-xs font-semibold uppercase tracking-widest text-cyan-700">System</p>
                            <h2 class="mt-1 text-lg font-bold text-slate-950">Ringkasan Sistem</h2>
                        </div>
                        <span class="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600">Update $last_update</span>
                    </div>

                    <div class="grid gap-4 xl:grid-cols-2">
                        <dl class="overflow-hidden rounded-lg border border-slate-200 bg-slate-50">
                            $summary_left
                        </dl>

                        <dl class="overflow-hidden rounded-lg border border-slate-200 bg-slate-50">
                            $summary_right
                        </dl>
                    </div>
                </section>

                <section class="grid gap-6 xl:grid-cols-2">
                    <div id="network" class="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
                        <div class="mb-4 flex items-center gap-3">
                            <span class="rounded-lg bg-cyan-50 p-2 text-cyan-700"><i data-lucide="network" class="h-5 w-5"></i></span>
                            <div>
                                <p class="text-xs font-semibold uppercase tracking-widest text-cyan-700">Network</p>
                                <h2 class="text-lg font-bold text-slate-950">Network Interface</h2>
                            </div>
                        </div>
                        <dl class="overflow-hidden rounded-lg border border-slate-200 bg-slate-50">
                            $interface_rows
                        </dl>
                    </div>

                    <div id="armbian" class="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
                        <div class="mb-4 flex items-center gap-3">
                            <span class="rounded-lg bg-emerald-50 p-2 text-emerald-700"><i data-lucide="file-cog" class="h-5 w-5"></i></span>
                            <div>
                                <p class="text-xs font-semibold uppercase tracking-widest text-emerald-700">Config</p>
                                <h2 class="text-lg font-bold text-slate-950">/etc/armbian-release</h2>
                            </div>
                        </div>
                        <dl class="overflow-hidden rounded-lg border border-slate-200 bg-slate-50">
                            $armbian_rows
                        </dl>
                    </div>
                </section>
            </main>
        </div>

        <script>
            if (window.lucide) {
                window.lucide.createIcons();
            }
        </script>
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
