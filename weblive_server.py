#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
WebLive Studio Pro v3.1 — Core Python Broadcast Server & Media Engine
===============================================================================
Arquitetura Profissional de Transmissão Ao Vivo em Python 3 (Zero-Dependency Nativo):
  1. Servidor HTTP Multithreaded de Alta Performance (`ThreadingHTTPServer`)
  2. Hub de Eventos em Tempo Real (SSE `/api/events` + `/api/sync`) para:
     - Painel do Diretor (Director Interface)
     - Tela de Exibição OBS Studio (`Browser Source` 1080p60 + Clean Feed `?clean=1`)
     - Convidados Remotos WebRTC (Sinalização SDP/ICE + Tally Light + Mix-Minus)
  3. Extrator Nativo `yt-dlp` (`/api/ytdlp?url=...`): Converte links do YouTube,
     Twitch, Instagram e Facebook em streams diretos sem bloqueio de iframe!
  4. Motor de Transmissão RTMP / SRT via `FFmpeg` (`/api/rtmp/start` & `/api/rtmp/stop`):
     Transmite o vídeo REAL do Program da Estação Desktop para YouTube Live, Twitch ou Facebook Live.
  5. Persistência SQLite Nativa (`weblive_studio.db`): Salva projetos, cenas,
     configurações e histórico auditável de exibições/comerciais (#49).
  6. Feed RSS real (#37), Clima real via Open-Meteo (#36) e Speedtest real (#41).
  7. API REST Customizada para Elgato Stream Deck / Bitfocus Companion (#46).
"""

import json
import os
import queue
import socket
import sqlite3
import sys
import threading
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PUBLIC_DIR = BASE_DIR / "public"
DB_PATH = BASE_DIR / "weblive_studio.db"


class WebLiveDatabase:
    """Camada de persistência profissional em SQLite3 nativo do Python."""

    def __init__(self, db_path: Path):
        self.db_path = str(db_path)
        self._lock = threading.Lock()
        self._init_schema()

    def _init_schema(self):
        with self._lock, sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS project_state (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    state_json TEXT NOT NULL,
                    updated_at REAL NOT NULL
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    category TEXT NOT NULL,
                    action TEXT NOT NULL
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS rtmp_targets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    platform TEXT NOT NULL,
                    rtmp_url TEXT NOT NULL,
                    stream_key TEXT NOT NULL,
                    enabled INTEGER DEFAULT 1
                )
                """
            )
            conn.commit()

    def save_state(self, state_dict: dict):
        with self._lock, sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO project_state (id, state_json, updated_at)
                VALUES (1, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    state_json = excluded.state_json,
                    updated_at = excluded.updated_at
                """,
                (json.dumps(state_dict, ensure_ascii=False), time.time()),
            )
            conn.commit()

    def load_state(self):
        with self._lock, sqlite3.connect(self.db_path) as conn:
            row = conn.execute("SELECT state_json FROM project_state WHERE id = 1").fetchone()
            if row:
                try:
                    return json.loads(row[0])
                except Exception:
                    return None
            return None

    def add_audit_log(self, action: str, category: str = "BROADCAST"):
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        with self._lock, sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO audit_logs (timestamp, category, action) VALUES (?, ?, ?)",
                (ts, category, action),
            )
            conn.commit()

    def get_recent_logs(self, limit: int = 100):
        with self._lock, sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT timestamp, category, action FROM audit_logs ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [{"time": r[0], "category": r[1], "msg": r[2]} for r in rows]


class FFmpegStreamerEngine:
    """
    Transmissão RTMP / RTMPS / SRT (YouTube, Twitch, Facebook) do vídeo REAL do Program via FFmpeg.
    Os quadros vêm do compositor da Estação Desktop (`frame_provider`, definido por
    weblive_studio_gui.pyw). Com o servidor rodando sozinho não há vídeo do Program, então o
    início é recusado com uma mensagem clara (nada de "sucesso" sem transmitir).
    """

    def __init__(self, db: WebLiveDatabase):
        self.db = db
        self.frame_provider = None
        self.output = None
        self.current_target = ""

    @property
    def is_streaming(self) -> bool:
        return bool(self.output and self.output.active)

    def start_stream(self, rtmp_url: str, stream_key: str):
        if self.is_streaming:
            return {"ok": False, "message": "A transmissão RTMP já está em execução."}
        if self.frame_provider is None:
            return {"ok": False, "message": "Abra a Estação Desktop (weblive_studio_gui.pyw): o servidor sozinho não tem o vídeo do Program para transmitir."}

        rtmp_url = (rtmp_url or "").strip()
        stream_key = (stream_key or "").strip()
        if not rtmp_url.startswith(("rtmp://", "rtmps://", "srt://")):
            return {"ok": False, "message": "O endereço do servidor deve começar com rtmp://, rtmps:// ou srt://"}
        if not rtmp_url.startswith("srt://") and not stream_key:
            return {"ok": False, "message": "Informe a chave de transmissão (stream key) fornecida pela plataforma."}

        from weblive_video import FFmpegOutput  # import tardio: o servidor sozinho não depende de OpenCV

        full_url = rtmp_url if rtmp_url.startswith("srt://") else rtmp_url.rstrip("/") + "/" + stream_key.strip("/")
        self.output = FFmpegOutput("rtmp", self.frame_provider, secret=stream_key)
        res = self.output.start(full_url)
        if res.get("ok"):
            self.current_target = rtmp_url  # nunca expõe a chave em status/SSE
            self.db.add_audit_log(f"Transmissão RTMP iniciada (Program real via FFmpeg) para {rtmp_url}", "RTMP")
        return res

    def stop_stream(self):
        if self.output:
            self.output.stop(timeout=5.0)
            self.db.add_audit_log("Transmissão RTMP finalizada pelo Diretor", "RTMP")
        return {"ok": True, "is_streaming": False}

    def check(self):
        """Mensagem de erro se o FFmpeg caiu sozinho (chave inválida, rede, servidor recusou)."""
        err = self.output.check() if self.output else None
        if err:
            self.db.add_audit_log(f"Transmissão RTMP interrompida: {err[:200]}", "RTMP")
        return err

    def status(self):
        return {
            "is_streaming": self.is_streaming,
            "target": self.current_target if self.is_streaming else "",
            "uptime_sec": self.output.uptime if self.output else 0,
        }


YTDLP_COOKIES_FILE = BASE_DIR / "cookies.txt"
YTDLP_FORMAT_WEB = "best[ext=mp4]/best"
# A Estação Desktop ainda não reproduz o áudio da mídia: pega só o vídeo H.264 até 720p
YTDLP_FORMAT_DESKTOP = "bestvideo[height<=720][vcodec^=avc1]/best[height<=720]/best"


class YtDlpMediaResolver:
    """
    Integração com o pacote Python `yt-dlp` instalado na máquina para extrair
    metadados e URLs diretas de vídeo/áudio (YouTube, Twitch, Instagram, Facebook, TikTok).
    Se existir `cookies.txt` (formato Netscape) na pasta do programa, ele é usado: o YouTube
    hoje exige login ("confirme que você não é um robô") para muitos vídeos.
    """

    @staticmethod
    def resolve_url(url: str, fmt: str = YTDLP_FORMAT_WEB) -> dict:
        if not url:
            return {"ok": False, "error": "URL vazia"}

        try:
            import yt_dlp  # Usa a biblioteca Python yt-dlp instalada no ambiente

            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "skip_download": True,
                "format": fmt,
            }
            if YTDLP_COOKIES_FILE.is_file():
                ydl_opts["cookiefile"] = str(YTDLP_COOKIES_FILE)
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                return {
                    "ok": True,
                    "title": info.get("title", "Mídia Externa"),
                    "uploader": info.get("uploader", "WebLive Media"),
                    "duration": info.get("duration", 0),
                    "thumbnail": info.get("thumbnail", ""),
                    "direct_url": info.get("url", url),
                    "webpage_url": info.get("webpage_url", url),
                }
        except Exception as exc:
            msg = str(exc)
            if "Sign in to confirm" in msg or "cookies" in msg:
                msg = (
                    "O YouTube pediu login para liberar este vídeo. Exporte os cookies do seu navegador "
                    "(extensão \"Get cookies.txt LOCALLY\") e salve como cookies.txt na pasta do WebLive Studio."
                )
            # Fallback para embed amigável caso a URL seja privada ou live restrita
            return {
                "ok": False,
                "fallback_url": url,
                "error": msg,
            }


class BroadcastEventHub:
    """Gerenciador Thread-Safe de clientes Server-Sent Events (SSE) em Python."""

    def __init__(self):
        self._clients = set()
        self._lock = threading.Lock()

    def register(self) -> queue.Queue:
        q = queue.Queue(maxsize=150)
        with self._lock:
            self._clients.add(q)
        return q

    def unregister(self, q: queue.Queue):
        with self._lock:
            self._clients.discard(q)

    def broadcast(self, payload: dict):
        msg = f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode("utf-8")
        with self._lock:
            dead = []
            for q in self._clients:
                try:
                    q.put_nowait(msg)
                except queue.Full:
                    dead.append(q)
            for q in dead:
                self._clients.discard(q)

    def client_count(self) -> int:
        with self._lock:
            return len(self._clients)


# Instâncias Globais do Servidor Python
DB = WebLiveDatabase(DB_PATH)
HUB = BroadcastEventHub()
RTMP_ENGINE = FFmpegStreamerEngine(DB)

MIME_MAP = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".svg": "image/svg+xml",
    ".webm": "video/webm",
    ".mp4": "video/mp4",
    ".ico": "image/x-icon",
}


class WebLiveRequestHandler(BaseHTTPRequestHandler):
    """Handler HTTP/1.1 Multithreaded para o WebLive Studio Pro (Python)."""

    protocol_version = "HTTP/1.1"

    def log_message(self, format_str, *args):
        # Silencia logs repetitivos de polling para manter o console limpo
        pass

    def _send_cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, HEAD")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _send_json(self, data: dict, status: int = 200):
        raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self._send_cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_OPTIONS(self):
        self.send_response(204)
        self._send_cors()
        self.end_headers()

    def do_HEAD(self):
        self.send_response(200)
        self._send_cors()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        pathname = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)

        # 1. Stream de Eventos em Tempo Real (SSE: /api/events)
        if pathname == "/api/events":
            self.send_response(200)
            self._send_cors()
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.end_headers()

            client_q = HUB.register()
            try:
                hello = f"data: {json.dumps({'type': 'CONNECTED', 'engine': 'Python3-Pro', 'timestamp': int(time.time()*1000)})}\n\n".encode("utf-8")
                self.wfile.write(hello)
                self.wfile.flush()

                while True:
                    try:
                        chunk = client_q.get(timeout=15.0)
                        self.wfile.write(chunk)
                        self.wfile.flush()
                    except queue.Empty:
                        # Keep-alive heartbeat
                        self.wfile.write(b": heartbeat\n\n")
                        self.wfile.flush()
            except Exception:
                pass
            finally:
                HUB.unregister(client_q)
            return

        # 2. Função #46: API Endpoints Customizados para Elgato Stream Deck / Bitfocus Companion
        if pathname == "/api/streamdeck":
            action = qs.get("action", ["cut"])[0]
            target = qs.get("target", [""])[0]
            value = qs.get("value", [""])[0]
            cmd_payload = {
                "type": "STREAMDECK_COMMAND",
                "action": action,
                "target": target,
                "value": value,
                "timestamp": int(time.time() * 1000),
            }
            HUB.broadcast(cmd_payload)
            DB.add_audit_log(f"Stream Deck API: action={action} target={target}", "STREAMDECK")
            self._send_json({"status": "dispatched", "engine": "python", "command": cmd_payload})
            return

        # 3. Função #33: Webhook para Alertas de Doação / Superchat / Inscritos
        if pathname == "/api/webhook/alert":
            user = qs.get("user", ["Apoiador Ao Vivo"])[0]
            amount = qs.get("amount", ["R$ 50,00"])[0]
            msg = qs.get("msg", ["Parabéns pela transmissão profissional em Python!"])[0]
            alert_payload = {
                "type": "WEBHOOK_ALERT",
                "alertType": "superchat",
                "user": user,
                "amount": amount,
                "message": msg,
                "timestamp": int(time.time() * 1000),
            }
            HUB.broadcast(alert_payload)
            DB.add_audit_log(f"Superchat Webhook: {user} ({amount}) - {msg}", "MONETIZATION")
            self._send_json({"triggered": True, "user": user, "amount": amount})
            return

        # 4. Core #2 Avançado: Extrator Python `yt-dlp` para vídeos/lives (YouTube, Twitch, IG, TikTok)
        if pathname == "/api/ytdlp":
            target_url = qs.get("url", [""])[0]
            result = YtDlpMediaResolver.resolve_url(target_url)
            if result.get("ok"):
                DB.add_audit_log(f"yt-dlp extraiu stream direto: {result.get('title')}", "MEDIA")
            self._send_json(result)
            return

        # 5. Função #37 Real: Buscador Python de Feed RSS (sem bloqueio CORS do navegador)
        if pathname == "/api/rss":
            rss_url = qs.get("url", [DEFAULT_RSS_URL])[0]
            try:
                headlines = fetch_rss_headlines(rss_url)
            except Exception as exc:
                self._send_json({"ok": False, "headlines": [], "error": str(exc)})
                return
            self._send_json({"ok": True, "headlines": headlines, "ticker_text": " • ".join(headlines) + " • "})
            return

        # 6. Status do Backend Python, Clientes Conectados, Banco SQLite e Streamer RTMP
        if pathname == "/api/python/status":
            self._send_json({
                "ok": True,
                "python_version": sys.version.split()[0],
                "connected_clients": HUB.client_count(),
                "rtmp": RTMP_ENGINE.status(),
                "db_logs": DB.get_recent_logs(25),
            })
            return

        # 7. Servir arquivos estáticos da pasta /public
        rel_path = "/index.html" if pathname == "/" else pathname
        safe_part = os.path.normpath(rel_path.lstrip("/"))
        if safe_part.startswith(".."):
            self._send_json({"error": "Forbidden"}, 403)
            return

        file_path = PUBLIC_DIR / safe_part
        if not file_path.is_file():
            self._send_json({"error": "404 - Arquivo não encontrado no WebLive Studio Python"}, 404)
            return

        ext = file_path.suffix.lower()
        mime = MIME_MAP.get(ext, "application/octet-stream")
        data = file_path.read_bytes()
        self.send_response(200)
        self._send_cors()
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        pathname = parsed.path
        length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"

        try:
            body = json.loads(raw_body) if raw_body else {}
        except Exception:
            body = {}

        # 1. Barramento de Sincronização e WebRTC Signaling (/api/sync)
        if pathname == "/api/sync":
            HUB.broadcast(body)
            if body.get("type") == "STATE_UPDATE" and isinstance(body.get("data"), dict):
                DB.save_state(body["data"])
            self._send_json({"ok": True})
            return

        # 2. Controle do Motor RTMP / FFmpeg em Python (/api/rtmp/start & /api/rtmp/stop)
        if pathname == "/api/rtmp/start":
            rtmp_url = body.get("rtmp_url", "rtmp://a.rtmp.youtube.com/live2")
            stream_key = body.get("stream_key", "")
            res = RTMP_ENGINE.start_stream(rtmp_url, stream_key)
            HUB.broadcast({"type": "RTMP_STATUS", "data": RTMP_ENGINE.status()})
            self._send_json(res)
            return

        if pathname == "/api/rtmp/stop":
            res = RTMP_ENGINE.stop_stream()
            HUB.broadcast({"type": "RTMP_STATUS", "data": RTMP_ENGINE.status()})
            self._send_json(res)
            return

        if pathname == "/api/webhook/alert":
            HUB.broadcast({"type": "WEBHOOK_ALERT", **body})
            self._send_json({"triggered": True})
            return

        self._send_json({"error": "Endpoint POST desconhecido"}, 404)

DEFAULT_RSS_URL = "https://g1.globo.com/rss/g1/"
HTTP_UA = {"User-Agent": "WebLiveStudioPro/3.1"}


def _http_get_json(url: str, timeout: float = 8.0):
    req = urllib.request.Request(url, headers=HTTP_UA)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_rss_headlines(rss_url: str, limit: int = 6):
    """Manchetes reais de um feed RSS 2.0 ou Atom (#37). Lança exceção se o feed falhar."""
    req = urllib.request.Request(rss_url, headers=HTTP_UA)
    with urllib.request.urlopen(req, timeout=6.0) as resp:
        root = ET.fromstring(resp.read())
    nodes = root.findall(".//item/title") or root.findall(".//{http://www.w3.org/2005/Atom}entry/{http://www.w3.org/2005/Atom}title")
    titles = [" ".join(n.text.split()) for n in nodes if n.text and n.text.strip()][:limit]
    if not titles:
        raise ValueError("o feed não trouxe nenhuma manchete")
    return titles


WMO_CODES_PT = {
    0: "Céu limpo", 1: "Predomínio de sol", 2: "Parcialmente nublado", 3: "Nublado",
    45: "Neblina", 48: "Neblina", 51: "Garoa", 53: "Garoa", 55: "Garoa forte",
    56: "Garoa congelante", 57: "Garoa congelante", 61: "Chuva fraca", 63: "Chuva", 65: "Chuva forte",
    66: "Chuva congelante", 67: "Chuva congelante", 71: "Neve", 73: "Neve", 75: "Neve forte", 77: "Neve",
    80: "Pancadas de chuva", 81: "Pancadas de chuva", 82: "Temporal", 85: "Neve", 86: "Neve",
    95: "Trovoadas", 96: "Trovoadas com granizo", 99: "Trovoadas com granizo",
}


def fetch_weather(city: str) -> str:
    """Clima atual real (#36) via Open-Meteo (gratuito, sem chave). Ex.: 'São Paulo 24°C • Nublado'."""
    q = urllib.parse.urlencode({"name": city, "count": 1, "language": "pt", "format": "json"})
    geo = _http_get_json(f"https://geocoding-api.open-meteo.com/v1/search?{q}")
    if not geo.get("results"):
        raise ValueError(f"cidade não encontrada: {city}")
    place = geo["results"][0]
    q = urllib.parse.urlencode({"latitude": place["latitude"], "longitude": place["longitude"], "current": "temperature_2m,weather_code", "timezone": "auto"})
    cur = _http_get_json(f"https://api.open-meteo.com/v1/forecast?{q}")["current"]
    desc = WMO_CODES_PT.get(int(cur.get("weather_code", -1)), "")
    text = f"{place['name']} {round(cur['temperature_2m'])}°C"
    return f"{text} • {desc}" if desc else text


def run_speedtest() -> dict:
    """Speedtest real (#41) contra speed.cloudflare.com: latência, download e upload em Mbps."""
    base = "https://speed.cloudflare.com"
    rtts = []
    for _ in range(3):
        t0 = time.perf_counter()
        with urllib.request.urlopen(urllib.request.Request(f"{base}/__down?bytes=0", headers=HTTP_UA), timeout=8) as r:
            r.read()
        rtts.append((time.perf_counter() - t0) * 1000)

    size_down = 10_000_000
    t0 = time.perf_counter()
    with urllib.request.urlopen(urllib.request.Request(f"{base}/__down?bytes={size_down}", headers=HTTP_UA), timeout=30) as r:
        got = len(r.read())
    down = got * 8 / (time.perf_counter() - t0) / 1e6

    payload = os.urandom(4_000_000)
    req = urllib.request.Request(f"{base}/__up", data=payload, method="POST", headers={**HTTP_UA, "Content-Type": "application/octet-stream"})
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=30) as r:
        r.read()
    up = len(payload) * 8 / (time.perf_counter() - t0) / 1e6
    return {"ping_ms": min(rtts), "download_mbps": down, "upload_mbps": up}


def get_lan_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


class WebLivePythonServer:
    """Wrapper controlável por GUI (Tkinter) ou linha de comando."""

    def __init__(self, port: int = 3000):
        self.port = port
        self.httpd = None
        self.thread = None
        self.running = False

    def start(self) -> int:
        if self.running:
            return self.port

        for candidate_port in range(self.port, self.port + 15):
            try:
                self.httpd = ThreadingHTTPServer(("0.0.0.0", candidate_port), WebLiveRequestHandler)
                self.port = candidate_port
                self.running = True
                break
            except OSError:
                continue

        if not self.httpd:
            # Caso já exista instância na porta 3000, mantém referência para abrir os links
            return self.port

        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        DB.add_audit_log(f"Servidor Python WebLive Studio Pro iniciado na porta {self.port}", "SYSTEM")
        return self.port

    def stop(self):
        self.running = False
        if self.httpd:
            try:
                self.httpd.shutdown()
                self.httpd.server_close()
            except Exception:
                pass
            self.httpd = None


if __name__ == "__main__":
    srv = WebLivePythonServer(port=int(os.environ.get("PORT", "3000")))
    active_port = srv.start()
    lan_ip = get_lan_ip()
    print("\n=====================================================================")
    print(f"🐍 WEBLIVE STUDIO PRO (PYTHON ENGINE) ATIVO EM: http://localhost:{active_port}")
    print(f"🌐 Acesso na Rede Local (Celular/Tablet)       : http://{lan_ip}:{active_port}")
    print("---------------------------------------------------------------------")
    print(f"🎛️  Painel do Diretor : http://localhost:{active_port}/index.html")
    print(f"📺 Tela OBS (Output) : http://localhost:{active_port}/output.html")
    print(f"🧼 Saída Clean Feed  : http://localhost:{active_port}/output.html?clean=1")
    print(f"📱 Entrada Repórter  : http://{lan_ip}:{active_port}/guest.html?guest=Reporter1")
    print(f"🎬 Extrator yt-dlp   : http://localhost:{active_port}/api/ytdlp?url=...")
    print("=====================================================================\n")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nEncerrando servidor Python WebLive Studio...")
        srv.stop()

