#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
WebLive Studio Pro v3.1 — Motor de Vídeo Real (OpenCV + Pillow + FFmpeg)
===============================================================================
  1. Fontes reais com thread própria, sempre guardando o quadro mais recente (RGB):
     - CameraSource: webcam / câmera virtual (DirectShow) com reconexão automática (#50)
     - MediaSource : arquivo de vídeo local ou link resolvido pelo yt-dlp, com play/pause e loop
  2. ProgramCompositor: monta o PROGRAM real em 1280x720 @ 30fps (layouts single/PiP/grid,
     chroma key, correção de cor, crop, transição AUTO com fade, stinger, replay em câmera lenta)
     e desenha todos os gráficos (GC, placar, ticker, QR Code real, enquete, meta, whiteboard...).
     Também gera o Clean Feed (#43, sem gráficos) e o PREVIEW em 640x360.
  3. FFmpegOutput: envia o Program real ao FFmpeg por pipe para Gravação de Backup (#27, .mkv)
     ou Transmissão RTMP/RTMPS/SRT (YouTube, Twitch, Facebook).

Roda em thread própria: a gravação e a transmissão seguem mesmo que a janela da GUI trave
momentaneamente (ex.: enquanto ela é arrastada no Windows).
"""

import collections
import glob
import os
import queue
import re
import shutil
import subprocess
import threading
import time
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

OUT_W, OUT_H, OUT_FPS = 1280, 720, 30
PVW_W, PVW_H = 640, 360

BASE_DIR = Path(__file__).resolve().parent
RECORDINGS_DIR = BASE_DIR / "gravacoes"

CAMERA_IDS = ("cam1", "cam2")
SOURCE_LABELS = {"cam1": "CÂMERA 1", "cam2": "CÂMERA 2", "media1": "MÍDIA", "guest1": "REPÓRTER (CELULAR)"}
GRID_ORDER = ("cam1", "cam2", "media1", "guest1")

FADE_SECONDS = 0.6
STINGER_SECONDS = 0.7
ALERT_SECONDS = 5.0
LT_ANIM_SECONDS = 0.45
REPLAY_FPS = 15
REPLAY_BUFFER_SECONDS = 10
REPLAY_CLIP_SECONDS = 5
REPLAY_SPEED = 0.5

THEMES = {
    "cyber-grid": ((12, 16, 24), (22, 34, 53)),
    "news-globe": ((8, 22, 43), (22, 40, 70)),
    "stadium-lights": ((8, 36, 23), (20, 60, 40)),
}

# Nomes exibidos na GUI (Português-BR) -> chaves internas; as chaves antigas (projetos v3.0) também valem
LAYOUT_NAMES = {
    "Câmera Única (Tela Cheia)": "single",
    "Janela Sobreposta (PiP)": "pip",
    "Mosaico 4 Câmeras": "grid4",
    "Mosaico 8 Câmeras": "grid8",
}
THEME_NAMES = {
    "Grade Cibernética": "cyber-grid",
    "Globo Telejornal": "news-globe",
    "Iluminação de Estádio": "stadium-lights",
}

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
FFMPEG_MISSING_MSG = (
    "FFmpeg não encontrado.\n\nInstale com o comando:\n    winget install Gyan.FFmpeg\n"
    "ou copie o ffmpeg.exe para a pasta do WebLive Studio e abra o programa novamente."
)

# Emojis e símbolos sem glifo nas fontes do Windows viram "quadradinhos" no ar
_EMOJI_RE = re.compile("[\U0001F000-\U0001FAFF\u2300-\u23FF\u2600-\u27BF\u2B00-\u2BFF\uFE0F\u200D]")


def clean_text(value) -> str:
    return _EMOJI_RE.sub("", str(value or "")).strip()


# =============================================================================
# FFmpeg: localização e listagem de dispositivos
# =============================================================================
_ffmpeg_path = None


def find_ffmpeg():
    """Procura o ffmpeg na pasta do programa, no PATH e na instalação do winget."""
    global _ffmpeg_path
    if _ffmpeg_path and os.path.isfile(_ffmpeg_path):
        return _ffmpeg_path

    candidates = [BASE_DIR / "ffmpeg.exe", BASE_DIR / "ffmpeg" / "bin" / "ffmpeg.exe"]
    found = next((str(c) for c in candidates if c.is_file()), None) or shutil.which("ffmpeg")
    local = os.environ.get("LOCALAPPDATA", "")
    if not found and local:
        link = Path(local) / "Microsoft" / "WinGet" / "Links" / "ffmpeg.exe"
        if link.is_file():
            found = str(link)
        else:
            hits = sorted(glob.glob(os.path.join(local, "Microsoft", "WinGet", "Packages", "Gyan.FFmpeg*", "*", "bin", "ffmpeg.exe")))
            found = hits[-1] if hits else None
    _ffmpeg_path = found
    return found


def list_video_devices():
    """Nomes das câmeras DirectShow na mesma ordem dos índices do OpenCV (vazio se não houver FFmpeg)."""
    ffmpeg = find_ffmpeg()
    if not ffmpeg or os.name != "nt":
        return []
    try:
        res = subprocess.run(
            [ffmpeg, "-hide_banner", "-list_devices", "true", "-f", "dshow", "-i", "dummy"],
            stdin=subprocess.DEVNULL, capture_output=True, timeout=10, creationflags=NO_WINDOW,
        )
    except Exception:
        return []
    text = res.stderr.decode("utf-8", errors="replace")
    return re.findall(r'"([^"]+)" \(video\)', text)


# =============================================================================
# FONTES DE VÍDEO
# =============================================================================
class VideoSource:
    """Fonte com thread própria. `latest()` devolve o quadro RGB mais recente (ou None)."""

    def __init__(self, name: str):
        self.name = name
        self.status = "parada"
        self.fps = 0.0
        self._frame = None
        self._stop = threading.Event()
        self._thread = None
        self._fps_count = 0
        self._fps_t0 = time.perf_counter()

    def start(self):
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name=f"src-{self.name}", daemon=True)
        self._thread.start()
        return self

    def stop(self):
        self._stop.set()
        if self._thread and self._thread is not threading.current_thread():
            self._thread.join(timeout=2.0)
        self._frame = None
        self.status = "parada"

    def latest(self):
        return self._frame

    def _publish(self, rgb):
        # Sempre substitui a referência (nunca altera o array publicado): leitura sem lock é segura
        self._frame = rgb
        self._fps_count += 1
        now = time.perf_counter()
        if now - self._fps_t0 >= 1.0:
            self.fps = self._fps_count / (now - self._fps_t0)
            self._fps_count = 0
            self._fps_t0 = now

    def _run(self):
        raise NotImplementedError


class CameraSource(VideoSource):
    """Webcam, celular (Câmera Virtual do Windows) ou OBS Virtual Camera via DirectShow."""

    def __init__(self, index: int, name: str = ""):
        super().__init__(name or f"Câmera {index}")
        self.index = index

    def _run(self):
        backend = cv2.CAP_DSHOW if os.name == "nt" else cv2.CAP_ANY
        while not self._stop.is_set():
            self.status = "conectando..."
            cap = cv2.VideoCapture(self.index, backend)
            if not cap.isOpened():
                cap.release()
                self.status = "sem sinal (tentando novamente)"
                self._stop.wait(3.0)
                continue

            # MJPG libera 720p a 30fps na maioria das webcams USB (em YUY2 costuma cair para 5-10fps)
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, OUT_W)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, OUT_H)
            cap.set(cv2.CAP_PROP_FPS, OUT_FPS)

            fails = 0
            while not self._stop.is_set():
                ok, frame = cap.read()
                if not ok or frame is None:
                    fails += 1
                    if fails > 30:
                        break
                    time.sleep(0.03)
                    continue
                fails = 0
                self._publish(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                h, w = frame.shape[:2]
                self.status = f"ao vivo {w}x{h} • {self.fps:.0f} fps"
            cap.release()

            if not self._stop.is_set():
                # Auto-Reconexão (#50): câmera desconectada ou ocupada por outro programa
                self._frame = None
                self.status = "sinal perdido (reconectando...)"
                self._stop.wait(1.5)


class MediaSource(VideoSource):
    """Arquivo local ou URL direta (yt-dlp). Toca no ritmo do vídeo, com pausa e loop."""

    def __init__(self, url: str, title: str = "", loop: bool = True):
        super().__init__(title or os.path.basename(url) or "Mídia")
        self.url = url
        self.title = title or os.path.basename(url) or url
        self.loop = loop
        self.paused = False
        self.ended = False
        self.error = ""

    def _run(self):
        attempts = 0
        while not self._stop.is_set():
            self.status = "abrindo..."
            cap = cv2.VideoCapture(self.url, cv2.CAP_FFMPEG)
            if not cap.isOpened():
                cap.release()
                attempts += 1
                if attempts >= 3:
                    self.error = "não foi possível abrir a mídia"
                    self.status = "erro: não foi possível abrir"
                    return
                self._stop.wait(2.0)
                continue

            attempts = 0
            fps = cap.get(cv2.CAP_PROP_FPS)
            period = 1.0 / fps if 1.0 < fps < 121.0 else 1.0 / OUT_FPS
            next_t = time.perf_counter()
            while not self._stop.is_set():
                if self.paused:
                    self.status = "pausado"
                    time.sleep(0.05)
                    next_t = time.perf_counter()
                    continue
                ok, frame = cap.read()
                if not ok or frame is None:
                    break
                h, w = frame.shape[:2]
                if w > OUT_W or h > OUT_H:
                    s = min(OUT_W / w, OUT_H / h)
                    frame = cv2.resize(frame, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA)
                self._publish(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                self.status = f"reproduzindo {w}x{h}"
                next_t += period
                delay = next_t - time.perf_counter()
                if delay > 0:
                    time.sleep(delay)
                elif delay < -0.5:
                    next_t = time.perf_counter()
            cap.release()

            if self._stop.is_set():
                break
            if not self.loop:
                self.ended = True
                self.status = "fim do vídeo"
                return  # mantém o último quadro congelado na tela


# =============================================================================
# FUNÇÕES DE IMAGEM
# =============================================================================
@lru_cache(maxsize=64)
def font(kind: str, size: int):
    names = {
        "regular": ("segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"),
        "bold": ("segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"),
        "mono": ("consolab.ttf", "consola.ttf", "courbd.ttf", "DejaVuSansMono-Bold.ttf"),
    }[kind]
    fonts_dir = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
    for name in names:
        for path in (os.path.join(fonts_dir, name), name):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default(size)


@lru_cache(maxsize=8)
def qr_image(data: str, size: int):
    """QR Code real e escaneável (#9). None se o pacote `qrcode` não estiver instalado."""
    try:
        import qrcode
    except ImportError:
        return None
    qr = qrcode.QRCode(border=2, box_size=10, error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    return img.resize((size, size), Image.NEAREST)


def _fit(frame, w: int, h: int):
    """Redimensiona mantendo a proporção para caber em w x h (sem cortar a imagem)."""
    fh, fw = frame.shape[:2]
    s = min(w / fw, h / fh)
    nw, nh = max(1, int(fw * s)), max(1, int(fh * s))
    if (nw, nh) == (fw, fh):
        return frame
    return cv2.resize(frame, (nw, nh), interpolation=cv2.INTER_AREA if s < 1 else cv2.INTER_LINEAR)


def _color_correct(frame, bright: int, contrast: int, sat: int):
    if bright != 100 or contrast != 100:
        a = contrast / 100.0
        b = (bright - 100) * 2.55 + 128 * (1 - a)
        frame = cv2.convertScaleAbs(frame, alpha=a, beta=b)
    if sat != 100:
        hsv = cv2.cvtColor(frame, cv2.COLOR_RGB2HSV)
        hsv[..., 1] = cv2.convertScaleAbs(hsv[..., 1], alpha=sat / 100.0)
        frame = cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB)
    return frame


def _chroma_key(fg, bg_region, tol: int):
    """Remove o fundo verde (#3): onde a câmera é verde, mostra o fundo da cena."""
    hsv = cv2.cvtColor(fg, cv2.COLOR_RGB2HSV)
    s_min = int(np.clip(150 - tol, 30, 150))
    mask = cv2.inRange(hsv, (35, s_min, 45), (85, 255, 255))
    mask = cv2.medianBlur(mask, 5)
    out = fg.copy()
    out[mask > 0] = bg_region[mask > 0]
    return out


def _ease(p: float) -> float:
    p = max(0.0, min(1.0, p))
    return 1 - (1 - p) ** 3


# =============================================================================
# COMPOSITOR DO PROGRAM
# =============================================================================
class ProgramCompositor:
    """
    Gera a 30fps: `latest_pgm` (Program com gráficos), `latest_clean` (Clean Feed #43) e
    `latest_pvw` (Preview). A GUI só publica um retrato do estado em `state` a cada quadro.
    """

    def __init__(self, sources: dict):
        self.sources = sources
        self.state = None
        self.latest_pgm = None
        self.latest_clean = None
        self.latest_pvw = None
        self.fps = 0.0
        self.last_error = ""
        self._stop = threading.Event()
        self._thread = None
        self._frame_no = 0

        self._replay_buf = collections.deque(maxlen=REPLAY_FPS * REPLAY_BUFFER_SECONDS)
        self._replay_lock = threading.Lock()
        self._replay_queue = queue.Queue(maxsize=3)
        self._replay_last_push = 0.0
        self._replay_token_seen = 0
        self._replay_clip = []
        self._replay_started = 0.0
        self._replay_idx = -1
        self._replay_frame = None

        self._ticker_text = None
        self._ticker_strip = None
        self._bg_cache = {}
        self._slate_cache = {}
        self._label_cache = {}
        self._last_pip_rect = None
        self._pgm_pip_rect = None

    @property
    def replaying(self) -> bool:
        return bool(self._replay_clip)

    def start(self):
        self._thread = threading.Thread(target=self._run, name="compositor", daemon=True)
        self._thread.start()
        threading.Thread(target=self._replay_worker, name="replay-jpeg", daemon=True).start()
        return self

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2.0)

    def _run(self):
        period = 1.0 / OUT_FPS
        next_t = time.perf_counter()
        count, t0 = 0, time.perf_counter()
        while not self._stop.is_set():
            st = self.state
            if st:
                try:
                    self._render(st, time.time())
                    self.last_error = ""
                except Exception as exc:  # um quadro com erro não pode derrubar a saída
                    self.last_error = f"{type(exc).__name__}: {exc}"
            count += 1
            now = time.perf_counter()
            if now - t0 >= 1.0:
                self.fps = count / (now - t0)
                count, t0 = 0, now
            next_t += period
            delay = next_t - time.perf_counter()
            if delay > 0:
                time.sleep(delay)
            else:
                next_t = time.perf_counter()

    # ------------------------------------------------------------------ cenas
    def _render(self, st: dict, t: float):
        scenes = st["scenes"]
        if not scenes:
            return
        pgm = scenes[min(st["pgm_idx"], len(scenes) - 1)]
        pvw = scenes[min(st["pvw_idx"], len(scenes) - 1)]

        live = self._render_scene(pgm, OUT_W, OUT_H, st, t)
        self._pgm_pip_rect = self._last_pip_rect
        fade_p = (t - st["fade_start"]) / FADE_SECONDS
        if 0 <= fade_p < 1 and 0 <= st["fade_from"] < len(scenes):
            old = self._render_scene(scenes[st["fade_from"]], OUT_W, OUT_H, st, t)
            live = cv2.addWeighted(old, 1.0 - fade_p, live, fade_p, 0)

        self._replay_push(live, t)
        base = self._replay_current(st, t)
        if base is None:
            base = live
        self.latest_clean = base

        img = Image.fromarray(base)  # cópia: os gráficos não tocam no Clean Feed
        self._draw_overlays(img, st, t)
        self.latest_pgm = np.asarray(img)

        # Preview a 15fps basta para o monitor do diretor
        self._frame_no += 1
        if self._frame_no % 2 == 0 or self.latest_pvw is None:
            self.latest_pvw = self._render_scene(pvw, PVW_W, PVW_H, st, t)

    def _background(self, theme: str, w: int, h: int, t: float):
        base, line = THEMES.get(THEME_NAMES.get(theme, theme), THEMES["cyber-grid"])
        key = (base, w, h)
        plain = self._bg_cache.get(key)
        if plain is None:
            plain = np.empty((h, w, 3), np.uint8)
            plain[:] = base
            self._bg_cache[key] = plain
        img = plain.copy()
        step = max(16, w // 36)
        off = int(t * 28 * w / OUT_W) % step
        img[:, off::step] = line
        img[off::step, :] = line
        return img

    def _source_frame(self, sid, st):
        src = self.sources.get(sid) if sid else None
        frame = src.latest() if src else None
        if frame is None:
            return None
        if sid in CAMERA_IDS:
            crop = st["crop_top"]
            if crop > 0:
                frame = frame[int(frame.shape[0] * crop / 100.0):]
            frame = _color_correct(frame, st["brightness"], st["contrast"], st["saturation"])
        return frame

    def _place(self, img, sid, x, y, w, h, st, chroma=False, tag=False, frame=None):
        if frame is None:
            frame = self._source_frame(sid, st)
        if frame is None:
            src = self.sources.get(sid) if sid else None
            img[y:y + h, x:x + w] = self._slate_tile(w, h, SOURCE_LABELS.get(sid, "LIVRE"), src.status if src else "")
            return
        fitted = _fit(frame, w, h)
        fh, fw = fitted.shape[:2]
        ox, oy = x + (w - fw) // 2, y + (h - fh) // 2
        region = img[oy:oy + fh, ox:ox + fw]
        if chroma and st["chroma"] and sid in CAMERA_IDS:
            fitted = _chroma_key(fitted, region, st["chroma_tol"])
        region[:] = fitted
        if tag:
            self._blend_label(img, SOURCE_LABELS.get(sid, ""), x, y, w, h)

    def _slate_tile(self, w: int, h: int, label: str, status: str):
        """Tela de 'SEM SINAL' pronta em cache: nada de converter o quadro inteiro para Pillow."""
        key = (w, h, label, status)
        tile = self._slate_cache.get(key)
        if tile is None:
            if len(self._slate_cache) > 64:
                self._slate_cache.clear()
            fs = max(10, int(h * 0.07))
            pil = Image.new("RGB", (w, h), (11, 14, 20))
            d = ImageDraw.Draw(pil)
            d.text((w / 2, h / 2 - fs), "SEM SINAL", font=font("bold", fs + 4), fill=(248, 113, 113), anchor="mm")
            d.text((w / 2, h / 2 + fs * 0.8), f"{label} • {status}" if status else label, font=font("regular", fs), fill=(203, 213, 225), anchor="mm")
            tile = self._slate_cache[key] = np.asarray(pil)
        return tile

    def _blend_label(self, img, label: str, x: int, y: int, w: int, h: int):
        """Etiqueta com o nome da fonte no canto do quadro (mosaico / janela sobreposta)."""
        if not label:
            return
        fs = max(10, int(h * 0.06))
        key = (label, fs)
        patch = self._label_cache.get(key)
        if patch is None:
            f = font("bold", fs)
            tw = int(ImageDraw.Draw(Image.new("L", (1, 1))).textlength(label, font=f))
            pil = Image.new("RGBA", (tw + 12, fs + 12), (0, 0, 0, 170))
            ImageDraw.Draw(pil).text((6, (fs + 12) / 2), label, font=f, fill=(248, 250, 252, 255), anchor="lm")
            arr = np.asarray(pil).astype(np.float32)
            patch = self._label_cache[key] = (arr[..., :3], arr[..., 3:] / 255.0)
        rgb, alpha = patch
        ph, pw = min(rgb.shape[0], h - 12), min(rgb.shape[1], w - 12)
        if ph <= 0 or pw <= 0:
            return
        y0, x0 = y + h - ph - 6, x + 6
        region = img[y0:y0 + ph, x0:x0 + pw]
        a = alpha[:ph, :pw]
        region[:] = (region * (1 - a) + rgb[:ph, :pw] * a).astype(np.uint8)

    def _render_scene(self, scene: dict, w: int, h: int, st: dict, t: float):
        mode = scene.get("layoutMode", "single")
        mode = LAYOUT_NAMES.get(mode, mode)
        self._last_pip_rect = None
        bg_theme = scene.get("bgTheme", "cyber-grid")

        if mode in ("grid4", "grid8"):
            img = self._background(bg_theme, w, h, t)
            cols, rows = (4, 2) if mode == "grid8" else (2, 2)
            pad = max(4, w // 160)
            cw = (w - pad * (cols + 1)) // cols
            ch = (h - pad * (rows + 1)) // rows
            for i in range(cols * rows):
                c, r = i % cols, i // cols
                x0, y0 = pad + c * (cw + pad), pad + r * (ch + pad)
                sid = GRID_ORDER[i] if i < len(GRID_ORDER) else None
                img[y0:y0 + ch, x0:x0 + cw] = (17, 24, 39)
                self._place(img, sid, x0, y0, cw, ch, st, tag=True)
                cv2.rectangle(img, (x0, y0), (x0 + cw - 1, y0 + ch - 1), (229, 57, 53) if i == 0 else (41, 121, 255), 2)
        else:
            sid = scene.get("sourceType", "cam1")
            frame = self._source_frame(sid, st)
            img = None
            if frame is not None and not (st["chroma"] and sid in CAMERA_IDS):
                fitted = _fit(frame, w, h)
                if fitted.shape[:2] == (h, w):
                    # A fonte cobre a tela inteira: o fundo animado nem apareceria
                    img = fitted.copy() if fitted is frame else fitted
            if img is None:
                img = self._background(bg_theme, w, h, t)
                self._place(img, sid, 0, 0, w, h, st, chroma=True, frame=frame)
            if mode == "pip":
                scale = st["pip_scale"] / 100.0
                pw, ph = int(w * scale), int(h * scale)
                px, py = w - pw - int(w * 0.02), h - ph - int(h * 0.1)
                img[py:py + ph, px:px + pw] = (15, 23, 42)
                self._place(img, scene.get("pipSource", "guest1"), px, py, pw, ph, st, tag=True)
                cv2.rectangle(img, (px, py), (px + pw - 1, py + ph - 1), (0, 230, 118), max(2, w // 400))
                self._last_pip_rect = (px, py, pw, ph)
        return img

    # ----------------------------------------------------------------- replay
    def _replay_push(self, frame, t):
        if t - self._replay_last_push < 1.0 / REPLAY_FPS:
            return
        self._replay_last_push = t
        try:
            self._replay_queue.put_nowait(frame)  # o quadro não é alterado depois de renderizado
        except queue.Full:
            pass

    def _replay_worker(self):
        while not self._stop.is_set():
            try:
                frame = self._replay_queue.get(timeout=0.5)
            except queue.Empty:
                continue
            small = cv2.resize(frame, (960, 540), interpolation=cv2.INTER_AREA)
            ok, jpg = cv2.imencode(".jpg", cv2.cvtColor(small, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 85])
            if ok:
                with self._replay_lock:
                    self._replay_buf.append(jpg)

    def _replay_current(self, st, t):
        token = st.get("replay_token", 0)
        if token != self._replay_token_seen:
            self._replay_token_seen = token
            with self._replay_lock:
                self._replay_clip = list(self._replay_buf)[-REPLAY_FPS * REPLAY_CLIP_SECONDS:]
            self._replay_started = t
            self._replay_idx = -1
        if not self._replay_clip:
            return None
        idx = int((t - self._replay_started) * REPLAY_FPS * REPLAY_SPEED)
        if idx >= len(self._replay_clip):
            self._replay_clip = []
            return None
        if idx != self._replay_idx:
            bgr = cv2.imdecode(self._replay_clip[idx], cv2.IMREAD_COLOR)
            self._replay_frame = cv2.cvtColor(cv2.resize(bgr, (OUT_W, OUT_H), interpolation=cv2.INTER_LINEAR), cv2.COLOR_BGR2RGB)
            self._replay_idx = idx
        return self._replay_frame

    # --------------------------------------------------------------- gráficos
    def _ticker_image(self, text: str):
        if text != self._ticker_text:
            f = font("bold", 22)
            tw = int(ImageDraw.Draw(Image.new("L", (1, 1))).textlength(text, font=f)) + 1
            strip = Image.new("RGBA", (max(tw, 1), 44), (0, 0, 0, 0))
            ImageDraw.Draw(strip).text((0, 22), text, font=f, fill=(248, 250, 252, 255), anchor="lm")
            self._ticker_text, self._ticker_strip = text, strip
        return self._ticker_strip

    def _draw_overlays(self, img, st: dict, t: float):
        d = ImageDraw.Draw(img, "RGBA")
        W, H = img.size
        ticker_h = 44 if st["ticker_visible"] else 0
        bottom = H - ticker_h - 20

        # Marca d'água (#6) e Clima (#36) no canto superior direito
        right = W - 24
        wm = clean_text(st["watermark"])
        if wm:
            f = font("bold", 20)
            box = (right - d.textlength(wm, font=f) - 28, 20, right, 58)
            d.rounded_rectangle(box, 8, fill=(15, 23, 42, 200), outline=(71, 85, 105, 255), width=2)
            d.text(((box[0] + box[2]) / 2, 39), wm, font=f, fill="white", anchor="mm")
            right = box[0] - 12
        weather = clean_text(st["weather_text"])
        if st["weather_visible"] and weather:
            f = font("bold", 18)
            box = (right - d.textlength(weather, font=f) - 28, 20, right, 58)
            d.rounded_rectangle(box, 8, fill=(11, 14, 20, 210), outline=(56, 189, 248, 255), width=2)
            d.text(((box[0] + box[2]) / 2, 39), weather, font=f, fill=(56, 189, 248), anchor="mm")

        # Placar Esportivo + Cronômetro (Core #4)
        left_y = 20
        if st["sb_visible"]:
            f_team, f_pts, f_time = font("bold", 22), font("bold", 26), font("mono", 20)
            a, b = clean_text(st["sb_a"]) or "TIME A", clean_text(st["sb_b"]) or "TIME B"
            mins, secs = divmod(int(st["sb_time"]), 60)
            tm = f"{mins:02d}:{secs:02d}"
            x, y, h, sw = 24, left_y, 52, 54
            wa, wb, wt = d.textlength(a, font=f_team), d.textlength(b, font=f_team), d.textlength(tm, font=f_time)
            total = 18 + wa + 14 + sw + 6 + sw + 14 + wb + 18 + wt + 18
            d.rounded_rectangle((x, y, x + total, y + h), 10, fill=(11, 14, 20, 225), outline=(41, 121, 255, 255), width=2)
            cx = x + 18
            d.text((cx, y + h / 2), a, font=f_team, fill="white", anchor="lm")
            cx += wa + 14
            for pts, col in ((st["sb_pa"], (41, 121, 255)), (st["sb_pb"], (229, 57, 53))):
                d.rounded_rectangle((cx, y + 6, cx + sw, y + h - 6), 6, fill=col)
                d.text((cx + sw / 2, y + h / 2), str(pts), font=f_pts, fill="white", anchor="mm")
                cx += sw + 6
            cx += 8
            d.text((cx, y + h / 2), b, font=f_team, fill="white", anchor="lm")
            cx += wb + 18
            d.line((cx - 9, y + 10, cx - 9, y + h - 10), fill=(71, 85, 105), width=2)
            d.text((cx, y + h / 2), tm, font=f_time, fill=(56, 189, 248), anchor="lm")
            left_y = y + h + 12

        # Barra de Meta (#34)
        if st["goal_visible"]:
            x, y, w, h = 24, left_y, 380, 54
            cur, tgt = st["goal_current"], max(1, st["goal_target"])
            pct = max(0.0, min(1.0, cur / tgt))
            d.rounded_rectangle((x, y, x + w, y + h), 10, fill=(11, 14, 20, 225), outline=(0, 230, 118, 255), width=2)
            d.text((x + 16, y + 17), f"META DA LIVE   {cur} / {tgt}", font=font("bold", 17), fill="white", anchor="lm")
            d.rounded_rectangle((x + 16, y + 32, x + w - 16, y + 44), 6, fill=(30, 41, 59))
            if pct > 0:
                d.rounded_rectangle((x + 16, y + 32, x + 16 + max(12, (w - 32) * pct), y + 44), 6, fill=(0, 230, 118))
            left_y = y + h + 12

        # Selo de Replay (#8)
        if self.replaying:
            txt = "REPLAY • CÂMERA LENTA"
            f = font("bold", 22)
            box = (24, left_y, 24 + d.textlength(txt, font=f) + 56, left_y + 46)
            d.rounded_rectangle(box, 10, fill=(229, 57, 53, 235))
            if int(t * 2) % 2 == 0:
                d.ellipse((box[0] + 14, box[1] + 16, box[0] + 28, box[1] + 30), fill="white")
            d.text((box[0] + 38, box[1] + 23), txt, font=f, fill="white", anchor="lm")

        # Enquete Ao Vivo (#32)
        if st["poll_visible"]:
            w, h = 330, 150
            x, y = W - 24 - w, 76
            va, vb = st["poll_a"], st["poll_b"]
            tot = va + vb
            pa = round(va * 100 / tot) if tot else 0
            pb = 100 - pa if tot else 0
            d.rounded_rectangle((x, y, x + w, y + h), 12, fill=(11, 14, 20, 225), outline=(255, 179, 0, 255), width=2)
            d.text((x + 18, y + 24), "ENQUETE AO VIVO", font=font("bold", 18), fill=(255, 179, 0), anchor="lm")
            for i, (label, pct, col) in enumerate(((clean_text(st["poll_a_label"]), pa, (41, 121, 255)), (clean_text(st["poll_b_label"]), pb, (229, 57, 53)))):
                yy = y + 58 + i * 44
                d.text((x + 18, yy), label, font=font("bold", 17), fill="white", anchor="lm")
                d.text((x + w - 18, yy), f"{pct}%", font=font("bold", 17), fill=col, anchor="rm")
                d.rounded_rectangle((x + 18, yy + 12, x + w - 18, yy + 22), 5, fill=(30, 41, 59))
                if pct:
                    d.rounded_rectangle((x + 18, yy + 12, x + 18 + (w - 36) * pct / 100, yy + 22), 5, fill=col)

        # QR Code real (#9)
        if st["qr_visible"] and st["qr_url"]:
            qs = 168
            x, y = W - 24 - qs - 16, bottom - qs - 46
            pip = self._pgm_pip_rect
            if pip and x < pip[0] + pip[2] and y + qs + 46 > pip[1]:
                x = pip[0] - qs - 16 - 16  # ao lado da janela sobreposta, sem cobri-la
            d.rounded_rectangle((x, y, x + qs + 16, y + qs + 46), 10, fill=(255, 255, 255, 255))
            qr = qr_image(st["qr_url"], qs)
            if qr is not None:
                img.paste(qr, (x + 8, y + 8))
            else:
                d.text((x + 8 + qs / 2, y + 8 + qs / 2), "instale: pip install qrcode", font=font("regular", 12), fill="black", anchor="mm")
            d.text((x + 8 + qs / 2, y + qs + 27), "APONTE A CÂMERA", font=font("bold", 15), fill=(15, 23, 42), anchor="mm")

        # Tarjeta / Lower Third (Core #5) com animação de entrada e saída
        y_cursor = bottom
        since = t - st["lt_changed"]
        if st["lt_visible"]:
            p = _ease(since / LT_ANIM_SECONDS)
        else:
            p = 1 - _ease(since / LT_ANIM_SECONDS) if since < LT_ANIM_SECONDS else 0.0
        title, sub = clean_text(st["lt_title"]), clean_text(st["lt_sub"])
        if p > 0 and (title or sub):
            f1, f2 = font("bold", 32), font("regular", 22)
            w = max(d.textlength(title, font=f1), d.textlength(sub, font=f2)) + 64
            h = 96 if sub else 64
            x = 40 - (1 - p) * (w + 60)
            y = y_cursor - h
            d.rectangle((x, y, x + w, y + h), fill=(17, 24, 39, 235))
            d.rectangle((x, y, x + 10, y + h), fill=(229, 57, 53))
            d.text((x + 30, y + 32), title, font=f1, fill="white", anchor="lm")
            if sub:
                d.text((x + 30, y + 70), sub, font=f2, fill=(56, 189, 248), anchor="lm")
            y_cursor = y - 12

        # Comentário em Destaque (#35)
        if st["featured_visible"]:
            author, text = clean_text(st["featured_author"]), clean_text(st["featured_text"])[:90]
            f1, f2 = font("bold", 20), font("regular", 22)
            w = max(d.textlength(author, font=f1), d.textlength(text, font=f2)) + 48
            h = 84
            x, y = 40, y_cursor - h
            d.rounded_rectangle((x, y, x + w, y + h), 12, fill=(15, 23, 42, 235), outline=(56, 189, 248, 255), width=2)
            d.text((x + 24, y + 26), author, font=f1, fill=(56, 189, 248), anchor="lm")
            d.text((x + 24, y + 58), text, font=f2, fill="white", anchor="lm")

        # Ticker Tape / Crawl (#7 e #37)
        if st["ticker_visible"]:
            y0 = H - ticker_h
            d.rectangle((0, y0, W, H), fill=(9, 12, 16, 240))
            d.line((0, y0, W, y0), fill=(229, 57, 53), width=2)
            text = clean_text(st["ticker_text"])
            if text:
                strip = self._ticker_image(text + "     •     ")
                shift = int(t * 120) % strip.width
                x = 140 - shift
                while x < W:
                    img.paste(strip, (x, y0), strip)
                    x += strip.width
            d.rectangle((0, y0, 130, H), fill=(229, 57, 53))
            d.text((65, y0 + 22), "AO VIVO", font=font("bold", 18), fill="white", anchor="mm")

        # Whiteboard / Telestrator (#40)
        for color, pts in st["strokes"]:
            if len(pts) >= 2:
                d.line([(px * W, py * H) for px, py in pts], fill=color, width=6, joint="curve")

        # Alerta de Superchat / Doação (#33)
        since = t - st["alert_start"]
        if 0 <= since < ALERT_SECONDS:
            p = _ease(since / 0.3)
            w, h = 640, 170
            x, y = (W - w) / 2, (H - h) / 2 + (1 - p) * 40
            d.rounded_rectangle((x, y, x + w, y + h), 16, fill=(229, 57, 53, int(240 * p)), outline=(255, 179, 0, int(255 * p)), width=4)
            d.text((W / 2, y + 38), "NOVA DOAÇÃO AO VIVO!", font=font("bold", 26), fill=(255, 235, 59), anchor="mm")
            d.text((W / 2, y + 86), clean_text(st["alert_user"]), font=font("bold", 30), fill="white", anchor="mm")
            d.text((W / 2, y + 132), clean_text(st["alert_msg"])[:60], font=font("regular", 22), fill="white", anchor="mm")

        # Countdown Regressivo (#25)
        if st["countdown_visible"]:
            m, s = divmod(max(0, int(st["countdown_sec"])), 60)
            d.rectangle((0, 0, W, H), fill=(7, 11, 20, 215))
            d.text((W / 2, H / 2 - 80), "A TRANSMISSÃO COMEÇA EM", font=font("bold", 30), fill=(56, 189, 248), anchor="mm")
            d.text((W / 2, H / 2 + 30), f"{m:02d}:{s:02d}", font=font("mono", 140), fill="white", anchor="mm")

        # Transição Stinger (Core #3): painel cobre a tela inteira no meio do efeito, quando a cena troca
        p = (t - st["stinger_start"]) / STINGER_SECONDS
        if 0 <= p < 1:
            pw = int(W * 1.6)
            x = W - p * (W + pw)
            d.rectangle((x - 40, 0, x, H), fill=(255, 179, 0))
            d.rectangle((x, 0, x + pw, H), fill=(41, 121, 255))
            d.rectangle((x + pw, 0, x + pw + 40, H), fill=(255, 179, 0))
            d.text((x + pw / 2, H / 2), "WEBLIVE STUDIO", font=font("bold", 64), fill="white", anchor="mm")


# =============================================================================
# SAÍDAS FFmpeg (Gravação de Backup #27 e Transmissão RTMP)
# =============================================================================
class FFmpegOutput:
    """
    Envia o Program real (rgb24 1280x720 @ 30fps) ao FFmpeg pelo stdin.
    kind="record": grava .mkv (H.264) — kind="rtmp": transmite FLV/MPEG-TS com trilha de áudio silenciosa.
    Uma thread escreve quadros no ritmo do relógio (duplica o último quadro se o compositor atrasar),
    então a duração do arquivo/transmissão bate com o tempo real.
    """

    def __init__(self, kind: str, frame_getter, secret: str = ""):
        self.kind = kind
        self.frame_getter = frame_getter
        self.secret = secret
        self.proc = None
        self.target = ""
        self.started_at = None
        self.log_path = RECORDINGS_DIR / f"ffmpeg_{kind}.log"
        self._log = None
        self._thread = None
        self._stop = threading.Event()
        self._stopping = False

    @property
    def active(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    @property
    def uptime(self) -> int:
        return int(time.time() - self.started_at) if (self.active and self.started_at) else 0

    def _mask(self, text: str) -> str:
        return text.replace(self.secret, "****") if self.secret else text

    def _build_cmd(self, ffmpeg: str, target: str):
        cmd = [
            ffmpeg, "-hide_banner", "-loglevel", "warning", "-nostats", "-y",
            "-f", "rawvideo", "-pix_fmt", "rgb24", "-video_size", f"{OUT_W}x{OUT_H}", "-framerate", str(OUT_FPS), "-i", "pipe:0",
        ]
        if self.kind == "record":
            return cmd + ["-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p", "-g", str(OUT_FPS * 2), target]

        # Plataformas (YouTube/Facebook) exigem trilha de áudio: até o mixer real existir, vai silêncio
        cmd += [
            "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
            "-map", "0:v", "-map", "1:a",
            "-c:v", "libx264", "-preset", "veryfast", "-tune", "zerolatency",
            "-b:v", "4500k", "-maxrate", "4500k", "-bufsize", "9000k",
            "-pix_fmt", "yuv420p", "-g", str(OUT_FPS * 2), "-keyint_min", str(OUT_FPS * 2), "-sc_threshold", "0",
            "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-shortest",
        ]
        if target.startswith("srt://"):
            return cmd + ["-f", "mpegts", target]
        return cmd + ["-f", "flv", "-flvflags", "no_duration_filesize", target]

    def start(self, target: str) -> dict:
        if self.active:
            return {"ok": False, "message": "Esta saída já está ativa."}
        ffmpeg = find_ffmpeg()
        if not ffmpeg:
            return {"ok": False, "message": FFMPEG_MISSING_MSG}
        RECORDINGS_DIR.mkdir(exist_ok=True)
        try:
            self._log = open(self.log_path, "wb")
            self.proc = subprocess.Popen(
                self._build_cmd(ffmpeg, target),
                stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=self._log, creationflags=NO_WINDOW,
            )
        except Exception as exc:
            self._close_log()
            self.proc = None
            return {"ok": False, "message": self._mask(f"Falha ao iniciar o FFmpeg: {exc}")}

        self.target = target
        self.started_at = time.time()
        self._stopping = False
        self._stop.clear()
        self._thread = threading.Thread(target=self._writer, name=f"ffmpeg-{self.kind}", daemon=True)
        self._thread.start()
        return {"ok": True, "mode": "ffmpeg_program", "target": self._mask(target)}

    def _writer(self):
        period = 1.0 / OUT_FPS
        black = bytes(OUT_W * OUT_H * 3)
        start = time.perf_counter()
        n = 0
        while not self._stop.is_set():
            frame = self.frame_getter()
            data = frame.tobytes() if frame is not None and frame.shape == (OUT_H, OUT_W, 3) else black
            try:
                self.proc.stdin.write(data)
            except (BrokenPipeError, OSError, ValueError, AttributeError):
                return  # FFmpeg encerrou: check() informa o motivo
            n += 1
            delay = start + n * period - time.perf_counter()
            if delay > 0:
                time.sleep(delay)
            elif delay < -1.0:
                # Encoder não acompanha: reancora o relógio em vez de despejar uma rajada de quadros
                start, n = time.perf_counter(), 0

    def stop(self, timeout: float = 15.0) -> dict:
        self._stopping = True
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2.0)
        proc = self.proc
        if proc:
            try:
                proc.stdin.close()  # fim do pipe: FFmpeg finaliza o arquivo/stream normalmente
            except Exception:
                pass
            try:
                proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                proc.kill()
        self.proc = None
        self.started_at = None
        self._close_log()
        return {"ok": True}

    def check(self):
        """Se o FFmpeg morreu sozinho (chave errada, rede caiu...), limpa e devolve a mensagem de erro."""
        if self.proc is None or self._stopping or self.proc.poll() is None:
            return None
        code = self.proc.returncode
        self._stop.set()
        self.proc = None
        self.started_at = None
        self._close_log()
        return self._mask(f"FFmpeg encerrou (código {code}). {self.log_tail()}".strip())

    def log_tail(self, max_bytes: int = 700) -> str:
        try:
            data = self.log_path.read_bytes()[-max_bytes:]
        except OSError:
            return ""
        return self._mask(data.decode("utf-8", errors="replace").strip())

    def _close_log(self):
        if self._log:
            try:
                self._log.close()
            except Exception:
                pass
            self._log = None
