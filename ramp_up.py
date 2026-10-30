#!/usr/bin/env python3
"""
HTTP Load Tester
==============================
Usage:
    python3 ramp_up.py <url> <jumlah> [opsi]

Contoh:
    python3 ramp_up.py https://example.com 50
    python3 haqloader.py https://example.com 50 --method POST --body '{"user":"test"}' --content-type json
    python3 ramp_up.py https://example.com 50 --auth-basic user:pass
    python3 ramp_up.py https://example.com 50 --auth-bearer TOKEN123
    python3 ramp_up.py https://example.com 50 --cookie "session=abc; token=xyz"
    python3 ramp_up.py https://example.com 50 --header "X-Api-Key:secret" --header "X-Custom:value"
    python3 ramp_up.py https://example.com 50 --body-file payload.json --content-type json
    python3 ramp_up.py https://example.com 100 --concurrent 5 --report

Opsi request:
    --method METHOD        GET/POST/PUT/PATCH/DELETE/HEAD (default: GET)
    --body TEXT            Body request (string langsung)
    --body-file PATH       Body dari file (JSON/XML/txt)
    --content-type TYPE    json / form / xml / text (default: auto)
    --header K:V           Tambah/override header (bisa dipakai berkali-kali)
    --cookie TEXT          Cookie string: "key=val; key2=val2"
    --auth-basic USER:PASS HTTP Basic Auth
    --auth-bearer TOKEN    Bearer token (Authorization header)
    --auth-apikey K:V      API Key header, misal "X-Api-Key:secret"
    --no-verify-ssl        Skip verifikasi SSL

Opsi umum:
    --concurrent N         Request paralel (default: 1)
    --jeda N               Jeda antar batch detik (default: 4)
    --timeout N            Timeout per request (default: 30)
    --ramp-up N            +1 concurrent tiap N batch
    --report               Simpan laporan HTML
    --no-istirahat         Nonaktifkan istirahat tiap 10 batch

pip install requests --break-system-packages
"""

import sys
import time
import argparse
import statistics
import json
import os
import signal
import base64
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import requests
    requests.packages.urllib3.disable_warnings()
except ImportError:
    print("[ERROR] Install dulu: pip install requests --break-system-packages")
    sys.exit(1)


# ─────────────────────────────────────────────
# DAFTAR USER-AGENT BUILT-IN
# ─────────────────────────────────────────────
UA_BUILTIN = [
    # Chrome Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    # Chrome macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    # Chrome Linux
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    # Firefox Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    # Firefox macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.4; rv:125.0) Gecko/20100101 Firefox/125.0",
    # Firefox Linux
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:124.0) Gecko/20100101 Firefox/124.0",
    # Safari macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Safari/605.1.15",
    # Edge Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
    # Chrome Android
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.82 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Mobile Safari/537.36",
    # Safari iOS
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
]

def load_ua_list(args):
    """Return list UA yang akan digunakan (built-in atau dari file)."""
    if args.ua_file:
        try:
            with open(args.ua_file, "r", encoding="utf-8") as f:
                uas = [l.strip() for l in f if l.strip() and not l.startswith("#")]
            if not uas:
                raise ValueError("File kosong")
            print(w(f"  [UA] Dimuat dari file: {args.ua_file} ({len(uas)} UA)", "biru"))
            return uas
        except Exception as e:
            print(w(f"  [WARN] Gagal baca ua-file ({e}), pakai built-in", "kuning"))
    if args.ua:
        print(w(f"  [UA] Custom UA: {args.ua[:60]}", "biru"))
        return [args.ua]
    if getattr(args, "ua_rotate", False):
        print(w(f"  [UA] Rotasi built-in: {len(UA_BUILTIN)} UA", "biru"))
        return UA_BUILTIN
    # default: satu UA saja
    return [UA_BUILTIN[0]]


# ─────────────────────────────────────────────
# PROXY PROVIDER SOURCES (auto-download)
# ─────────────────────────────────────────────
PROXY_SOURCES = [
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
    "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/http/data.txt",
    "https://raw.githubusercontent.com/mertguvencli/http-proxy-list/main/proxy-list/data.txt",
    "https://raw.githubusercontent.com/roosterkid/openproxylist/main/HTTPS_RAW.txt",
    "https://raw.githubusercontent.com/MuRongPIG/Proxy-Master/main/http.txt",
    "https://raw.githubusercontent.com/officialputuid/KangProxy/KangProxy/http/http.txt",
    "https://raw.githubusercontent.com/prxchk/proxy-list/main/http.txt",
    "https://raw.githubusercontent.com/proxylist-to/proxy-list/main/http.txt",
    "https://raw.githubusercontent.com/yuceltoluyag/GoodProxy/main/raw.txt",
    "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt",
    "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/https.txt",
    "https://raw.githubusercontent.com/mmpx12/proxy-list/master/https.txt",
    "https://raw.githubusercontent.com/Anonym0usWork1221/Free-Proxies/main/proxy_files/http_proxies.txt",
    "https://raw.githubusercontent.com/opsxcq/proxy-list/master/list.txt",
    "https://raw.githubusercontent.com/Anonym0usWork1221/Free-Proxies/main/proxy_files/https_proxies.txt",
    "https://api.openproxylist.xyz/http.txt",
    "https://api.proxyscrape.com/v2/?request=displayproxies",
    "https://api.proxyscrape.com/?request=displayproxies&proxytype=http",
    "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all",
    "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=10000&country=all&ssl=all&anonymity=anonymous",
    "http://worm.rip/http.txt",
    "https://proxyspace.pro/http.txt",
    "https://multiproxy.org/txt_all/proxy.txt",
    "https://proxy-spider.com/api/proxies.example.txt",
]

import re as _re
_PROXY_RE = _re.compile(r"^\d{1,3}(?:\.\d{1,3}){3}:\d{2,5}$")

def _parse_proxy_line(line):
    """Normalisasi satu baris proxy → string host:port atau None jika tidak valid."""
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    # Hapus prefix protokol jika ada
    for prefix in ("https://", "http://", "socks5://", "socks4://"):
        if line.lower().startswith(prefix):
            line = line[len(prefix):]
            break
    # Ambil hanya host:port (buang path/param di belakang)
    line = line.split("/")[0].split("?")[0].strip()
    if _PROXY_RE.match(line):
        return line
    return None


def fetch_proxies_from_sources(workers=10, timeout=8):
    """
    Download proxy dari semua PROXY_SOURCES secara paralel.
    Return list string "host:port" yang unik, sudah disortir.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    print(w(f"\n  [FETCH] Mengunduh dari {len(PROXY_SOURCES)} sumber...", "biru"))

    hasil_per_sumber = {}

    def unduh(url):
        try:
            r = requests.get(url, timeout=timeout,
                             headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code == 200:
                lines = r.text.splitlines()
                parsed = [_parse_proxy_line(l) for l in lines]
                return url, [p for p in parsed if p]
            return url, []
        except Exception:
            return url, []

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(unduh, url): url for url in PROXY_SOURCES}
        for future in as_completed(futures):
            url, daftar = future.result()
            nama = url.split("/")[2][:30]  # domain saja
            if daftar:
                print(w(f"  [OK]  {nama:<32} {len(daftar):>5} proxy", "hijau"))
            else:
                print(w(f"  [--]  {nama:<32}   timeout/kosong", "abu"))
            hasil_per_sumber[url] = daftar

    semua = sorted(set(p for daftar in hasil_per_sumber.values() for p in daftar))
    print(w(f"\n  [FETCH] Total unik: {len(semua)} proxy", "biru"))
    return semua


def validate_proxies(raw_list, test_url="http://httpbin.org/ip",
                     workers=20, timeout=6, max_valid=200):
    """
    Uji setiap proxy dengan request ke test_url.
    Return list proxy yang berhasil respond, maks max_valid.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    print(w(f"\n  [VALID] Memvalidasi {len(raw_list)} proxy "
            f"(max {max_valid}, workers={workers})...", "biru"))

    valid = []
    lock = __import__("threading").Lock()

    def cek(proxy_str):
        proxy_dict = {
            "http":  f"http://{proxy_str}",
            "https": f"http://{proxy_str}",
        }
        try:
            r = requests.get(test_url, proxies=proxy_dict,
                             timeout=timeout, verify=False)
            if r.status_code == 200:
                return proxy_str
        except Exception:
            pass
        return None

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(cek, p): p for p in raw_list}
        selesai = 0
        for future in as_completed(futures):
            selesai += 1
            hasil = future.result()
            if hasil:
                with lock:
                    valid.append(hasil)
                    pct = len(valid) / max(len(raw_list), 1) * 100
                    print(w(f"  [✓] {hasil:<24} ({len(valid)} valid)", "hijau"), end="\r")
                    if len(valid) >= max_valid:
                        break
            # Tampilkan progres setiap 50 cek
            if selesai % 50 == 0:
                print(f"  [VALID] {selesai}/{len(raw_list)} dicek, "
                      f"{len(valid)} valid...      ", end="\r")

    print(f"\n  [VALID] Selesai: {len(valid)} proxy valid dari "
          f"{selesai} yang dicek.")
    return valid


def load_proxy_list(args):
    """
    Return list dict proxy untuk requests: [{"http":..,"https":..}, ...]
    Urutan prioritas:
    1. --fetch-proxies  → download otomatis dari PROXY_SOURCES
    2. --proxy-file     → dari file lokal
    3. --proxy          → dari argumen langsung
    """
    raw = []

    # ── 1. Auto-fetch ──
    if getattr(args, "fetch_proxies", False):
        workers = getattr(args, "proxy_workers", 10)
        raw = fetch_proxies_from_sources(workers=workers)

        if getattr(args, "proxy_validate", False):
            max_v = getattr(args, "proxy_max", 200)
            raw = validate_proxies(raw, workers=workers, max_valid=max_v)

        if getattr(args, "proxy_save", None):
            try:
                with open(args.proxy_save, "w", encoding="utf-8") as f:
                    f.write("\n".join(raw))
                print(w(f"  [SAVE] {len(raw)} proxy disimpan → {args.proxy_save}", "hijau"))
            except Exception as e:
                print(w(f"  [WARN] Gagal simpan: {e}", "kuning"))

    # ── 2. Dari file lokal ──
    elif getattr(args, "proxy_file", None):
        try:
            with open(args.proxy_file, "r", encoding="utf-8") as f:
                raw = [_parse_proxy_line(l) for l in f]
                raw = [p for p in raw if p]
            print(w(f"  [PROXY] Dari file: {args.proxy_file} ({len(raw)} proxy)", "biru"))
        except Exception as e:
            print(w(f"  [WARN] Gagal baca proxy-file: {e}", "kuning"))

    # ── 3. Dari argumen --proxy ──
    elif getattr(args, "proxy", None):
        for p in args.proxy:
            parsed = _parse_proxy_line(p)
            raw.append(parsed if parsed else p.replace("http://","").replace("https://",""))

    if not raw:
        return []

    proxies = [{"http": f"http://{p}", "https": f"http://{p}"} for p in raw]

    mode = "rotasi acak" if getattr(args, "proxy_rotate", False) else "sekuensial"
    print(w(f"  [PROXY] {len(proxies)} proxy siap ({mode})", "biru"))
    return proxies


# ─────────────────────────────────────────────
# WARNA TERMINAL
# ─────────────────────────────────────────────
WARNA = {
    "hijau":  "\033[92m",
    "kuning": "\033[93m",
    "merah":  "\033[91m",
    "biru":   "\033[94m",
    "ungu":   "\033[95m",
    "abu":    "\033[90m",
    "reset":  "\033[0m",
    "tebal":  "\033[1m",
}

def w(text, warna):
    return f"{WARNA.get(warna,'')}{text}{WARNA['reset']}"


# ─────────────────────────────────────────────
# GLOBAL STATE (untuk graceful shutdown)
# ─────────────────────────────────────────────
_semua_hasil_global = []
_args_global        = None
_url_global         = ""
_waktu_mulai_global = 0
_shutdown_flag      = False
_req_config_global  = {}

def _handle_signal(sig, frame):
    global _shutdown_flag
    print(w(f"\n\n  [SIGNAL {sig}] Dihentikan. Menyimpan hasil parsial...", "kuning"))
    _shutdown_flag = True
    _simpan_parsial()
    sys.exit(0)

def _simpan_parsial():
    if not _semua_hasil_global:
        return
    durasi = time.time() - _waktu_mulai_global if _waktu_mulai_global else 0
    stat = hitung_statistik(_semua_hasil_global)
    print_statistik(stat, _url_global, durasi,
                    _args_global.concurrent if _args_global else 1,
                    _args_global.method if _args_global else "GET")
    if _args_global and _args_global.report:
        html = buat_html_report(_url_global,
                                _args_global.method,
                                _args_global.concurrent,
                                _semua_hasil_global, stat, durasi,
                                _req_config_global)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        nama = f"report_parsial_{ts}.html"
        with open(nama, "w", encoding="utf-8") as f:
            f.write(html)
        print(w(f"  📄 Report parsial: {os.path.abspath(nama)}", "hijau"))


# ─────────────────────────────────────────────
# BUILD REQUEST CONFIG
# ─────────────────────────────────────────────
def build_request_config(args, ua_list, proxy_list):
    """
    Susun headers, auth, body, cookies dari argumen CLI.
    ua_list dan proxy_list digunakan per-request di kirim_request().
    Return dict siap pakai untuk requests.request().
    """
    # Header dasar (UA diisi dinamis per request)
    headers = {
        "User-Agent": ua_list[0],  # default, akan diganti per-request jika rotate
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Referer": "https://www.google.com/",
    }

    # ── Custom header dari --header K:V ──
    for h in (args.header or []):
        if ":" in h:
            k, v = h.split(":", 1)
            headers[k.strip()] = v.strip()
        else:
            print(w(f"  [WARN] Format header salah (pakai K:V): {h}", "kuning"))

    # ── Auth ──
    auth_tuple = None

    if args.auth_basic:
        if ":" in args.auth_basic:
            u, p = args.auth_basic.split(":", 1)
            auth_tuple = (u, p)
            print(w(f"  [AUTH] Basic Auth: {u}:***", "biru"))
        else:
            print(w("  [WARN] --auth-basic harus berformat user:pass", "kuning"))

    if args.auth_bearer:
        headers["Authorization"] = f"Bearer {args.auth_bearer}"
        print(w(f"  [AUTH] Bearer token: {args.auth_bearer[:12]}...", "biru"))

    if args.auth_apikey:
        if ":" in args.auth_apikey:
            k, v = args.auth_apikey.split(":", 1)
            headers[k.strip()] = v.strip()
            print(w(f"  [AUTH] API Key header: {k.strip()}: {v[:8]}...", "biru"))
        else:
            print(w("  [WARN] --auth-apikey harus berformat Header:value", "kuning"))

    # ── Cookie ──
    cookies = {}
    if args.cookie:
        for part in args.cookie.split(";"):
            part = part.strip()
            if "=" in part:
                ck, cv = part.split("=", 1)
                cookies[ck.strip()] = cv.strip()
        print(w(f"  [COOKIE] {len(cookies)} cookie dimuat", "biru"))

    # ── Body ──
    body_raw = None
    body_json = None
    body_data = None

    if args.body_file:
        try:
            with open(args.body_file, "r", encoding="utf-8") as f:
                body_raw = f.read()
            print(w(f"  [BODY] Dari file: {args.body_file} ({len(body_raw)} chars)", "biru"))
        except Exception as e:
            print(w(f"  [ERROR] Gagal baca body file: {e}", "merah"))
    elif args.body:
        body_raw = args.body

    # Tentukan Content-Type dan format body
    ct = (args.content_type or "").lower()

    if body_raw:
        if ct == "json" or (not ct and body_raw.strip().startswith("{")):
            try:
                body_json = json.loads(body_raw)
                headers.setdefault("Content-Type", "application/json")
                print(w(f"  [BODY] JSON ({len(body_raw)} chars)", "biru"))
            except json.JSONDecodeError:
                # Bukan JSON valid, kirim sebagai teks
                body_data = body_raw
                headers.setdefault("Content-Type", "text/plain")
                print(w("  [BODY] Teks biasa (JSON parse gagal)", "kuning"))
        elif ct == "form":
            # "key=val&key2=val2" → dict
            pairs = {}
            for part in body_raw.split("&"):
                if "=" in part:
                    k, v = part.split("=", 1)
                    pairs[k] = v
            body_data = pairs
            headers.setdefault("Content-Type", "application/x-www-form-urlencoded")
            print(w(f"  [BODY] Form data ({len(pairs)} field)", "biru"))
        elif ct == "xml":
            body_data = body_raw
            headers.setdefault("Content-Type", "application/xml")
            print(w(f"  [BODY] XML ({len(body_raw)} chars)", "biru"))
        else:
            body_data = body_raw
            headers.setdefault("Content-Type", "text/plain")
            print(w(f"  [BODY] Text ({len(body_raw)} chars)", "biru"))

    config = {
        "headers":    headers,
        "auth":       auth_tuple,
        "cookies":    cookies if cookies else None,
        "json":       body_json,
        "data":       body_data,
        "verify_ssl": not args.no_verify_ssl,
        "ua_list":    ua_list,
        "proxy_list": proxy_list,
        "ua_rotate":  getattr(args, "ua_rotate", False) or len(ua_list) > 1,
        "proxy_rotate": getattr(args, "proxy_rotate", False),
        "info": {
            "auth_type":      "basic"   if auth_tuple  else
                              "bearer"  if args.auth_bearer else
                              "api_key" if args.auth_apikey else "none",
            "cookie_count":   len(cookies),
            "body_size":      len(body_raw) if body_raw else 0,
            "content_type":   headers.get("Content-Type", "-"),
            "custom_headers": len(args.header or []),
            "ua_count":       len(ua_list),
            "proxy_count":    len(proxy_list),
        }
    }
    return config


# ─────────────────────────────────────────────
# KIRIM SATU REQUEST
# ─────────────────────────────────────────────
def kirim_request(url, method, timeout, nomor, req_config):
    import random as _random
    hasil = {"nomor": nomor, "status": None, "durasi": None, "error": None,
             "size": 0, "ua": None, "proxy": None}

    # Pilih UA: rotate per-request jika ada lebih dari satu
    ua_list = req_config.get("ua_list", [])
    if len(ua_list) > 1:
        ua = _random.choice(ua_list)
    else:
        ua = ua_list[0] if ua_list else req_config["headers"].get("User-Agent", "")

    # Salin header agar tidak race condition antar thread, ganti UA
    headers = dict(req_config["headers"])
    headers["User-Agent"] = ua
    hasil["ua"] = ua[:60] + ("..." if len(ua) > 60 else "")

    # Pilih proxy
    proxy_list = req_config.get("proxy_list", [])
    proxy = None
    if proxy_list:
        proxy = _random.choice(proxy_list) if req_config.get("proxy_rotate") else proxy_list[0]
        hasil["proxy"] = list(proxy.values())[0] if proxy else None

    try:
        start = time.time()
        r = requests.request(
            method  = method,
            url     = url,
            headers = headers,
            auth    = req_config["auth"],
            cookies = req_config["cookies"],
            json    = req_config["json"],
            data    = req_config["data"],
            timeout = timeout,
            allow_redirects = True,
            verify  = req_config["verify_ssl"],
            proxies = proxy,
        )
        durasi = (time.time() - start) * 1000
        hasil["status"] = r.status_code
        hasil["durasi"] = round(durasi, 2)
        hasil["size"]   = len(r.content)
    except requests.exceptions.ProxyError as e:
        hasil["error"] = f"Proxy Error: {str(e)[:40]}"
    except requests.exceptions.Timeout:
        hasil["error"] = "Timeout"
    except requests.exceptions.SSLError as e:
        hasil["error"] = f"SSL Error: {str(e)[:40]}"
    except requests.exceptions.ConnectionError:
        hasil["error"] = "Connection Error"
    except Exception as e:
        hasil["error"] = str(e)[:50]
    return hasil


# ─────────────────────────────────────────────
# HELPERS TAMPILAN
# ─────────────────────────────────────────────
def label_status(status):
    if status is None:
        return w("GAGAL", "merah")
    if 200 <= status < 300:
        return w(str(status), "hijau")
    if 300 <= status < 400:
        return w(str(status), "biru")
    if 400 <= status < 500:
        return w(str(status), "kuning")
    return w(str(status), "merah")


def progress_bar(selesai, total, lebar=28):
    pct = selesai / total
    isi = int(lebar * pct)
    bar = "█" * isi + "░" * (lebar - isi)
    return f"[{bar}] {selesai}/{total} ({pct*100:.0f}%)"


# ─────────────────────────────────────────────
# STATISTIK
# ─────────────────────────────────────────────
def hitung_statistik(semua_hasil):
    waktu = [h["durasi"] for h in semua_hasil if h["durasi"] is not None]
    status_counter = {}
    error_counter  = {}

    for h in semua_hasil:
        if h["status"]:
            status_counter[h["status"]] = status_counter.get(h["status"], 0) + 1
        if h["error"]:
            error_counter[h["error"]] = error_counter.get(h["error"], 0) + 1

    sorted_waktu = sorted(waktu) if waktu else []

    def persentil(data, p):
        if not data:
            return 0
        k = (len(data) - 1) * p / 100
        f = int(k)
        c = f + 1
        if c >= len(data):
            return data[f]
        return round(data[f] + (data[c] - data[f]) * (k - f), 2)

    return {
        "total":          len(semua_hasil),
        "sukses":         len(waktu),
        "gagal":          len(semua_hasil) - len(waktu),
        "min":            round(min(waktu), 2) if waktu else 0,
        "max":            round(max(waktu), 2) if waktu else 0,
        "rata2":          round(statistics.mean(waktu), 2) if waktu else 0,
        "median":         round(statistics.median(waktu), 2) if waktu else 0,
        "stdev":          round(statistics.stdev(waktu), 2) if len(waktu) > 1 else 0,
        "p90":            persentil(sorted_waktu, 90),
        "p95":            persentil(sorted_waktu, 95),
        "p99":            persentil(sorted_waktu, 99),
        "status_counter": status_counter,
        "error_counter":  error_counter,
    }


# ─────────────────────────────────────────────
# PRINT STATISTIK TERMINAL
# ─────────────────────────────────────────────
def print_statistik(stat, url, durasi_total, concurrent, method):
    print("\n" + w("=" * 58, "biru"))
    print(w("  RAMP_UP STATISTIK ", "tebal"))
    print(w("=" * 58, "biru"))
    print(f"  URL       : {url}")
    print(f"  Method    : {method}")
    print(f"  Concurrent: {concurrent}")
    print(f"  Durasi    : {round(durasi_total, 1)} detik")
    print()
    print(f"  Total     : {stat['total']} request")
    print(f"  Sukses    : {w(str(stat['sukses']), 'hijau')}")
    print(f"  Gagal     : {w(str(stat['gagal']), 'merah' if stat['gagal'] > 0 else 'hijau')}")
    success_rate = stat['sukses'] / stat['total'] * 100 if stat['total'] else 0
    print(f"  Success % : {w(f'{success_rate:.1f}%', 'hijau' if success_rate >= 95 else 'kuning')}")
    if stat['total'] > 0 and durasi_total > 0:
        rps = round(stat['total'] / durasi_total, 2)
        print(f"  RPS       : {rps} req/detik")
    print()
    print(f"  Min       : {stat['min']} ms")
    print(f"  Max       : {stat['max']} ms")
    print(f"  Rata-rata : {stat['rata2']} ms")
    print(f"  Median    : {stat['median']} ms")
    print(f"  Std Dev   : {stat['stdev']} ms")
    print(f"  P90       : {stat['p90']} ms")
    print(f"  P95       : {stat['p95']} ms")
    print(f"  P99       : {stat['p99']} ms")

    if stat["status_counter"]:
        print()
        print("  Status Code:")
        for kode, jml in sorted(stat["status_counter"].items()):
            bar = "▓" * min(jml, 30)
            print(f"    {label_status(kode)} : {bar} {jml}x")

    if stat["error_counter"]:
        print()
        print("  Error:")
        for err, jml in stat["error_counter"].items():
            print(f"    {w(err, 'merah')}: {jml}x")

    print(w("=" * 58, "biru"))


# ─────────────────────────────────────────────
# CHART ASCII DISTRIBUSI WAKTU
# ─────────────────────────────────────────────
def print_chart_distribusi(semua_hasil):
    waktu = [h["durasi"] for h in semua_hasil if h["durasi"] is not None]
    if len(waktu) < 5:
        return
    mn, mx = min(waktu), max(waktu)
    if mn == mx:
        return

    bucket   = 10
    step     = (mx - mn) / bucket
    bins     = [0] * bucket

    for t in waktu:
        idx = min(int((t - mn) / step), bucket - 1)
        bins[idx] += 1

    max_bin = max(bins) if bins else 1
    bar_max = 28

    print(w("\n  Distribusi Waktu Respons (ms):", "tebal"))
    for i, count in enumerate(bins):
        lo      = round(mn + i * step)
        hi      = round(mn + (i + 1) * step)
        bar_len = int(count / max_bin * bar_max)
        bar     = "█" * bar_len
        pct     = count / len(waktu) * 100
        print(f"  {lo:>6}-{hi:<6} ms | {w(bar, 'biru'):<28} {count:>3} ({pct:.0f}%)")


# ─────────────────────────────────────────────
# HTML REPORT
# ─────────────────────────────────────────────
def buat_html_report(url, method, concurrent, semua_hasil, stat, durasi_total, req_config=None):
    waktu_list    = [h["durasi"] for h in semua_hasil if h["durasi"] is not None]
    chart_labels  = json.dumps([h["nomor"] for h in semua_hasil if h["durasi"] is not None])
    chart_data    = json.dumps(waktu_list)
    status_labels = json.dumps([str(k) for k in stat["status_counter"].keys()])
    status_values = json.dumps(list(stat["status_counter"].values()))

    rps          = round(stat['total'] / durasi_total, 2) if durasi_total > 0 else 0
    success_rate = stat['sukses'] / stat['total'] * 100 if stat['total'] else 0
    ts           = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    info         = req_config.get("info", {}) if req_config else {}

    # Badge auth
    auth_badge = ""
    at = info.get("auth_type", "none")
    if at == "basic":
        auth_badge = '<span class="badge badge-blue">Basic Auth</span>'
    elif at == "bearer":
        auth_badge = '<span class="badge badge-blue">Bearer Token</span>'
    elif at == "api_key":
        auth_badge = '<span class="badge badge-blue">API Key</span>'

    cookie_badge = f'<span class="badge badge-ungu">{info.get("cookie_count",0)} Cookie</span>' if info.get("cookie_count") else ""
    body_badge   = f'<span class="badge badge-abu">Body {info.get("body_size",0)}B</span>' if info.get("body_size") else ""
    hdr_badge    = f'<span class="badge badge-abu">+{info.get("custom_headers",0)} Header</span>' if info.get("custom_headers") else ""
    ua_badge     = f'<span class="badge badge-hijau">{info.get("ua_count",1)} UA</span>' if info.get("ua_count", 1) > 1 else ""
    proxy_badge  = f'<span class="badge badge-merah">{info.get("proxy_count",0)} Proxy</span>' if info.get("proxy_count") else ""

    html = f"""<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Load Test Report - haqloader</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.0/chart.umd.min.js"></script>
<style>
  :root {{
    --bg:#0f1117;--card:#1a1d2e;--accent:#4f8ef7;
    --green:#22c55e;--red:#ef4444;--yellow:#eab308;--ungu:#a855f7;
    --text:#e2e8f0;--muted:#94a3b8;--border:#2d3748;
  }}
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{background:var(--bg);color:var(--text);font-family:'Segoe UI',sans-serif;padding:24px}}
  h1{{font-size:1.6rem;margin-bottom:4px;color:var(--accent)}}
  .sub{{color:var(--muted);font-size:.85rem;margin-bottom:8px}}
  .badges{{margin-bottom:20px;display:flex;gap:6px;flex-wrap:wrap}}
  .badge{{display:inline-block;padding:3px 10px;border-radius:20px;font-size:.75rem;font-weight:600}}
  .badge-blue{{background:#1e3a5f;color:var(--accent)}}
  .badge-ungu{{background:#3b1f6e;color:var(--ungu)}}
  .badge-abu{{background:#2d3748;color:var(--muted)}}
  .badge-hijau{{background:#14532d;color:var(--green)}}
  .badge-merah{{background:#450a0a;color:var(--red)}}
  .grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(155px,1fr));gap:12px;margin-bottom:24px}}
  .card{{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:16px}}
  .card .label{{font-size:.72rem;color:var(--muted);margin-bottom:6px;text-transform:uppercase;letter-spacing:.05em}}
  .card .value{{font-size:1.45rem;font-weight:700}}
  .green{{color:var(--green)}}.red{{color:var(--red)}}.yellow{{color:var(--yellow)}}.blue{{color:var(--accent)}}
  .chart-wrap{{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:20px;margin-bottom:20px}}
  .chart-wrap h2{{font-size:.95rem;color:var(--muted);margin-bottom:16px}}
  .charts-2col{{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:20px}}
  table{{width:100%;border-collapse:collapse;font-size:.82rem}}
  th{{background:#252840;padding:10px 12px;text-align:left;color:var(--muted);border-bottom:1px solid var(--border)}}
  td{{padding:8px 12px;border-bottom:1px solid var(--border)}}
  tr:hover td{{background:#1e2235}}
  .tag{{display:inline-block;padding:2px 8px;border-radius:4px;font-size:.75rem;font-weight:600}}
  .tag-ok{{background:#14532d;color:var(--green)}}
  .tag-err{{background:#450a0a;color:var(--red)}}
  .tag-redir{{background:#1e3a5f;color:var(--accent)}}
  .tag-warn{{background:#4a3500;color:var(--yellow)}}
  @media(max-width:700px){{.charts-2col{{grid-template-columns:1fr}}}}
</style>
</head>
<body>
<h1>⚡ Ramp_up — Load Test Report</h1>
<div class="sub">URL: <strong>{url}</strong> &nbsp;|&nbsp; {ts} &nbsp;|&nbsp; Method: <strong>{method}</strong> &nbsp;|&nbsp; Concurrent: {concurrent}</div>
<div class="badges">{auth_badge}{cookie_badge}{body_badge}{hdr_badge}{ua_badge}{proxy_badge}</div>

<div class="grid">
  <div class="card"><div class="label">Total Request</div><div class="value blue">{stat['total']}</div></div>
  <div class="card"><div class="label">Sukses</div><div class="value green">{stat['sukses']}</div></div>
  <div class="card"><div class="label">Gagal</div><div class="value {'red' if stat['gagal'] > 0 else 'green'}">{stat['gagal']}</div></div>
  <div class="card"><div class="label">Success Rate</div><div class="value {'green' if success_rate >= 95 else 'yellow'}">{success_rate:.1f}%</div></div>
  <div class="card"><div class="label">RPS</div><div class="value blue">{rps}</div></div>
  <div class="card"><div class="label">Rata-rata</div><div class="value">{stat['rata2']} ms</div></div>
  <div class="card"><div class="label">Median</div><div class="value">{stat['median']} ms</div></div>
  <div class="card"><div class="label">P90</div><div class="value">{stat['p90']} ms</div></div>
  <div class="card"><div class="label">P95</div><div class="value yellow">{stat['p95']} ms</div></div>
  <div class="card"><div class="label">P99</div><div class="value red">{stat['p99']} ms</div></div>
  <div class="card"><div class="label">Min</div><div class="value green">{stat['min']} ms</div></div>
  <div class="card"><div class="label">Max</div><div class="value red">{stat['max']} ms</div></div>
</div>

<div class="chart-wrap">
  <h2>Waktu Respons per Request (ms)</h2>
  <canvas id="lineChart" height="80"></canvas>
</div>

<div class="charts-2col">
  <div class="chart-wrap">
    <h2>Distribusi Status Code</h2>
    <canvas id="pieChart"></canvas>
  </div>
  <div class="chart-wrap">
    <h2>Distribusi Waktu Respons</h2>
    <canvas id="histChart"></canvas>
  </div>
</div>

<div class="chart-wrap">
  <h2>Detail Per Request</h2>
  <table>
    <thead><tr><th>#</th><th>Status</th><th>Durasi (ms)</th><th>Size (bytes)</th><th>Keterangan</th></tr></thead>
    <tbody>
"""
    for h in semua_hasil:
        if h["status"]:
            if 200 <= h["status"] < 300:
                tag = f'<span class="tag tag-ok">{h["status"]}</span>'
            elif 300 <= h["status"] < 400:
                tag = f'<span class="tag tag-redir">{h["status"]}</span>'
            elif 400 <= h["status"] < 500:
                tag = f'<span class="tag tag-warn">{h["status"]}</span>'
            else:
                tag = f'<span class="tag tag-err">{h["status"]}</span>'
            ket = ""
        else:
            tag = '<span class="tag tag-err">GAGAL</span>'
            ket = h.get("error", "")

        dur  = f"{h['durasi']} ms" if h['durasi'] else "-"
        size = h.get("size", 0) if h["status"] else "-"
        html += f"      <tr><td>{h['nomor']}</td><td>{tag}</td><td>{dur}</td><td>{size}</td><td>{ket}</td></tr>\n"

    html += f"""    </tbody>
  </table>
</div>

<script>
const labels = {chart_labels};
const data   = {chart_data};

new Chart(document.getElementById('lineChart'), {{
  type: 'line',
  data: {{
    labels,
    datasets: [{{
      label: 'Waktu Respons (ms)',
      data,
      borderColor: '#4f8ef7',
      backgroundColor: 'rgba(79,142,247,.1)',
      pointRadius: data.length > 100 ? 0 : 3,
      fill: true, tension: 0.3,
    }}]
  }},
  options: {{
    responsive: true,
    plugins: {{ legend: {{ display: false }} }},
    scales: {{
      x: {{ ticks: {{ color: '#94a3b8' }}, grid: {{ color: '#2d3748' }} }},
      y: {{ ticks: {{ color: '#94a3b8' }}, grid: {{ color: '#2d3748' }},
            title: {{ display: true, text: 'ms', color: '#94a3b8' }} }}
    }}
  }}
}});

new Chart(document.getElementById('pieChart'), {{
  type: 'doughnut',
  data: {{
    labels: {status_labels},
    datasets: [{{ data: {status_values},
      backgroundColor: ['#22c55e','#4f8ef7','#eab308','#ef4444','#a855f7','#06b6d4'] }}]
  }},
  options: {{ plugins: {{ legend: {{ labels: {{ color: '#e2e8f0' }} }} }} }}
}});

const mn = Math.min(...data), mx = Math.max(...data);
const bucket = 10, step = (mx-mn)/bucket;
const bins = new Array(bucket).fill(0);
data.forEach(v => {{ const i = Math.min(Math.floor((v-mn)/step), bucket-1); bins[i]++; }});
const histLabels = bins.map((_,i) => Math.round(mn+i*step)+'-'+Math.round(mn+(i+1)*step));
new Chart(document.getElementById('histChart'), {{
  type: 'bar',
  data: {{
    labels: histLabels,
    datasets: [{{ label: 'Jumlah', data: bins,
      backgroundColor: 'rgba(79,142,247,.7)', borderColor: '#4f8ef7', borderWidth: 1 }}]
  }},
  options: {{
    plugins: {{ legend: {{ display: false }} }},
    scales: {{
      x: {{ ticks: {{ color: '#94a3b8', maxRotation: 45 }}, grid: {{ color: '#2d3748' }} }},
      y: {{ ticks: {{ color: '#94a3b8' }}, grid: {{ color: '#2d3748' }} }}
    }}
  }}
}});
</script>
</body></html>"""
    return html


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    global _semua_hasil_global, _args_global, _url_global
    global _waktu_mulai_global, _shutdown_flag, _req_config_global

    signal.signal(signal.SIGINT,  _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    parser = argparse.ArgumentParser(
        description="RAMP_UP - HTTP Load Tester",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    # Argumen posisional
    parser.add_argument("url",    help="URL target")
    parser.add_argument("jumlah", type=int, help="Jumlah total request")

    # Request config
    rg = parser.add_argument_group("Request")
    rg.add_argument("--method",       default="GET",
                    choices=["GET","POST","PUT","PATCH","DELETE","HEAD"],
                    help="HTTP method (default: GET)")
    rg.add_argument("--body",         metavar="TEXT",  help="Body request sebagai string")
    rg.add_argument("--body-file",    metavar="PATH",  help="Body dari file")
    rg.add_argument("--content-type", metavar="TYPE",
                    choices=["json","form","xml","text"],
                    help="Format body: json/form/xml/text")
    rg.add_argument("--header",       metavar="K:V",   action="append",
                    help="Tambah/override header (bisa dipakai berkali-kali)")
    rg.add_argument("--cookie",       metavar="TEXT",  help="Cookie: 'key=val; key2=val2'")
    rg.add_argument("--auth-basic",   metavar="U:P",   help="Basic Auth: user:pass")
    rg.add_argument("--auth-bearer",  metavar="TOKEN", help="Bearer token")
    rg.add_argument("--auth-apikey",  metavar="K:V",   help="API Key header: Header:value")
    rg.add_argument("--no-verify-ssl", action="store_true", help="Skip verifikasi SSL")

    # User-Agent
    ug = parser.add_argument_group("User-Agent")
    ug.add_argument("--ua",        metavar="STRING", help="UA custom (satu string)")
    ug.add_argument("--ua-rotate", action="store_true",
                    help="Rotasi UA acak dari daftar built-in (17 UA)")
    ug.add_argument("--ua-file",   metavar="PATH",
                    help="Rotasi UA dari file teks (satu UA per baris)")

    # Proxy
    pg = parser.add_argument_group("Proxy")
    pg.add_argument("--proxy",         metavar="URL",  action="append",
                    help="Proxy manual (bisa dipakai berkali-kali): --proxy ip:port")
    pg.add_argument("--proxy-file",    metavar="PATH",
                    help="List proxy dari file teks (satu ip:port per baris)")
    pg.add_argument("--fetch-proxies", action="store_true",
                    help=f"Auto-download proxy dari {len(PROXY_SOURCES)} sumber publik")
    pg.add_argument("--proxy-validate", action="store_true",
                    help="Validasi proxy sebelum dipakai (butuh --fetch-proxies / --proxy-file)")
    pg.add_argument("--proxy-save",    metavar="PATH",
                    help="Simpan proxy hasil fetch/validasi ke file (misal: proxies.txt)")
    pg.add_argument("--proxy-max",     type=int, default=200, metavar="N",
                    help="Batas proxy valid saat validasi (default: 200)")
    pg.add_argument("--proxy-workers", type=int, default=10,  metavar="N",
                    help="Thread untuk fetch & validasi proxy (default: 10)")
    pg.add_argument("--proxy-rotate",  action="store_true",
                    help="Rotasi acak antar proxy per request")

    # Load test config
    lg = parser.add_argument_group("Load Test")
    lg.add_argument("--concurrent",   type=int,   default=1,    help="Request paralel (default: 1)")
    lg.add_argument("--jeda",         type=float, default=4.0,  help="Jeda antar batch detik (default: 4)")
    lg.add_argument("--timeout",      type=int,   default=30,   help="Timeout per request (default: 30)")
    lg.add_argument("--ramp-up",      type=int,   default=0,    help="+1 concurrent tiap N batch")
    lg.add_argument("--report",       action="store_true",      help="Simpan laporan HTML")
    lg.add_argument("--no-istirahat", action="store_true",      help="Nonaktifkan istirahat tiap 10 batch")

    args = parser.parse_args()

    url = args.url
    if not url.startswith("http"):
        url = "https://" + url

    _args_global = args
    _url_global  = url

    print(w("\n⚡ RAMP_UP. — HTTP Load Tester", "tebal"))
    print(w("=" * 58, "biru"))
    print(f"  Target     : {url}")
    print(f"  Request    : {args.jumlah}")
    print(f"  Concurrent : {args.concurrent}")
    print(f"  Jeda       : {args.jeda} detik")
    print(f"  Method     : {args.method}")
    print(f"  Timeout    : {args.timeout} detik")
    if args.ramp_up:
        print(f"  Ramp-up    : +1 tiap {args.ramp_up} batch")
    print(w("─" * 58, "abu"))

    # Muat UA dan proxy
    ua_list    = load_ua_list(args)
    proxy_list = load_proxy_list(args)

    # Build request config
    req_config = build_request_config(args, ua_list, proxy_list)
    _req_config_global = req_config

    print(w("=" * 58, "biru"))
    print()

    # ── Loop utama ──
    semua_hasil         = []
    _semua_hasil_global = semua_hasil
    batch_ke            = 0
    i                   = 1
    concurrent          = args.concurrent
    waktu_mulai         = time.time()
    _waktu_mulai_global = waktu_mulai
    timeout_adaptif     = args.timeout
    timeout_hits        = 0
    lebar_nomor         = len(str(args.jumlah))

    while i <= args.jumlah and not _shutdown_flag:

        # Ramp-up
        if args.ramp_up and batch_ke > 0 and batch_ke % args.ramp_up == 0:
            concurrent += 1
            print(w(f"\n  [RAMP-UP] Concurrent naik ke {concurrent}", "kuning"))

        # Batch
        sisa         = args.jumlah - i + 1
        ukuran_batch = min(concurrent, sisa)
        nomor_batch  = list(range(i, i + ukuran_batch))

        with ThreadPoolExecutor(max_workers=ukuran_batch) as ex:
            futures = {
                ex.submit(kirim_request, url, args.method, timeout_adaptif, n, req_config): n
                for n in nomor_batch
            }
            hasil_batch = {}
            for future in as_completed(futures):
                n = futures[future]
                hasil_batch[n] = future.result()

        for n in sorted(hasil_batch.keys()):
            h = hasil_batch[n]
            semua_hasil.append(h)

            prefix = f"  [{w(str(n).rjust(lebar_nomor), 'abu')}/{args.jumlah}]"

            if h["durasi"] is not None:
                warna_dur = "hijau" if h["durasi"] < 800 else "kuning" if h["durasi"] < 2000 else "merah"
                print(f"{prefix} {label_status(h['status'])} | "
                      f"{w(str(h['durasi']).rjust(8)+' ms', warna_dur)} | "
                      f"{h['size']:>8,} B")
            else:
                if h.get("error") == "Timeout":
                    timeout_hits += 1
                print(f"{prefix} {w('GAGAL', 'merah')} — {h['error']}")

        # Auto-adaptif timeout
        if timeout_hits >= 3 and timeout_adaptif > 8:
            timeout_adaptif = max(8, timeout_adaptif - 5)
            timeout_hits    = 0
            print(w(f"  [AUTO] Timeout disesuaikan → {timeout_adaptif}s", "kuning"))

        i        += ukuran_batch
        batch_ke += 1

        print(f"  {progress_bar(min(i-1, args.jumlah), args.jumlah)}")

        if i <= args.jumlah:
            time.sleep(args.jeda)

        if not args.no_istirahat and batch_ke % 10 == 0 and i <= args.jumlah:
            print(w(f"\n  --- Istirahat 10 detik (batch ke-{batch_ke}) ---", "abu"))
            time.sleep(10)

    durasi_total = time.time() - waktu_mulai
    semua_hasil.sort(key=lambda x: x["nomor"])

    stat = hitung_statistik(semua_hasil)
    print_statistik(stat, url, durasi_total, concurrent, args.method)
    print_chart_distribusi(semua_hasil)

    if args.report:
        html     = buat_html_report(url, args.method, args.concurrent,
                                    semua_hasil, stat, durasi_total, req_config)
        ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
        nama     = f"report_loadtest_{ts}.html"
        with open(nama, "w", encoding="utf-8") as f:
            f.write(html)
        print(w(f"\n  📄 Report HTML: {os.path.abspath(nama)}", "hijau"))

    print()


if __name__ == "__main__":
    main()

