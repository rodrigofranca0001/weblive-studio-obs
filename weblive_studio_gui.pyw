#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
WebLive Studio Pro v3.1 — Estação Desktop Nativa Python (100% Português-BR)
===============================================================================
Software Desktop de produção ao vivo (estilo vMix / OBS Studio) em janela nativa Python
(Tkinter + Pillow + OpenCV + FFmpeg + SQLite3 + yt-dlp), com TODOS os menus, barra de menu
superior, botões, abas e painéis em Português-BR!

O vídeo é REAL (motor em weblive_video.py):
  - Câmeras reais (webcam, celular como Câmera Virtual do Windows, OBS Virtual Camera) e mídia
    (arquivo do computador ou link via yt-dlp) com pausa, repetição e fila de vídeos (#22)
  - Compositor do PROGRAMA em 1280x720 @ 30fps: tela cheia / janela sobreposta (#1) / mosaicos (#2),
    fundo verde (#3), recorte (#4), ajuste de cor (#5), transições CORTE SECO / SUAVE / VINHETA,
    replay em câmera lenta (#8) e todos os gráficos (tarjeta #5, placar #4, notícias #7/#37,
    código QR real #9, enquete #32, meta #34, doação #33, clima real #36, desenho na tela #40...)
  - Monitores PRÉVIA e NO AR, projetor / saída limpa (#43) para "Captura de Janela" no OBS
  - Gravação de segurança real em .mkv (#27) e transmissão RTMP real do programa via FFmpeg

Ainda NÃO processam áudio real: mesa de som (#11-#20), efeitos sonoros (#15) e talkback (#16).
O vídeo do repórter pelo celular (WebRTC, #7) ainda não chega à estação desktop.
"""

import json
import os
import queue
import sys
import threading
import time
import tkinter as tk
from tkinter import colorchooser, filedialog, messagebox, simpledialog, ttk

try:
    import cv2
    from PIL import Image, ImageTk

    from weblive_video import (
        LAYOUT_NAMES, RECORDINGS_DIR, STINGER_SECONDS, THEME_NAMES,
        CameraSource, FFmpegOutput, MediaSource, ProgramCompositor, find_ffmpeg, list_video_devices,
    )
except ImportError as _exc:  # pythonw não mostra console: avisa numa janela
    _r = tk.Tk()
    _r.withdraw()
    messagebox.showerror(
        "WebLive Studio — biblioteca ausente",
        f"Falta uma biblioteca Python: {_exc}\n\nInstale com:\n    python -m pip install -r requirements.txt",
    )
    sys.exit(1)

from weblive_server import (
    DB, DEFAULT_RSS_URL, HUB, RTMP_ENGINE, YTDLP_FORMAT_DESKTOP, WebLivePythonServer, YtDlpMediaResolver,
    fetch_rss_headlines, fetch_weather, get_lan_ip, run_speedtest,
)

SOURCE_CHOICES = [("cam1", "Câmera 1"), ("cam2", "Câmera 2"), ("media1", "Mídia / Vídeo"), ("guest1", "Repórter (celular)")]
SOURCE_ID_BY_NAME = {name: sid for sid, name in SOURCE_CHOICES}
SOURCE_NAME_BY_ID = {sid: name for sid, name in SOURCE_CHOICES}
LAYOUT_CHOICES = list(LAYOUT_NAMES)
THEME_CHOICES = list(THEME_NAMES)
LAYOUT_LEGACY = {key: name for name, key in LAYOUT_NAMES.items()}
THEME_LEGACY = {key: name for name, key in THEME_NAMES.items()}
CAMERA_SLOTS = ("cam1", "cam2")
CAM_OFF = "(desligada)"
VIDEO_FILETYPES = [("Vídeos", "*.mp4 *.mov *.mkv *.webm *.avi *.m4v *.ts"), ("Todos os arquivos", "*.*")]
WEATHER_REFRESH_SECONDS = 900


def _int_var(var, default: int = 0) -> int:
    """Lê IntVar/Spinbox sem quebrar quando o campo está vazio ou com texto inválido."""
    try:
        return int(var.get())
    except (tk.TclError, ValueError):
        return default


def _normalize_scene(sc: dict) -> dict:
    """Converte cenas de projetos v3.0 (chaves internas) para os nomes em Português-BR."""
    sc = dict(sc)
    if sc.get("sourceType") == "webmedia":
        sc["sourceType"] = "media1"
    sc["layoutMode"] = LAYOUT_LEGACY.get(sc.get("layoutMode"), sc.get("layoutMode") or LAYOUT_CHOICES[0])
    sc["bgTheme"] = THEME_LEGACY.get(sc.get("bgTheme"), sc.get("bgTheme") or THEME_CHOICES[0])
    sc.setdefault("pipSource", "guest1")
    return sc


class NativeProjectorWindow(tk.Toplevel):
    """
    Janela Nativa de Saída de Vídeo (Saída Principal / Saída Limpa #43).
    Pode ser colocada em Tela Cheia num 2º monitor ou capturada no OBS via 'Captura de Janela'.
    """

    def __init__(self, master, app, clean_feed: bool = False):
        super().__init__(master)
        self.app = app
        self.clean_feed = clean_feed
        title_mode = "SAÍDA LIMPA (SEM GRÁFICOS #43)" if clean_feed else "SAÍDA PRINCIPAL (CAPTURA DE JANELA OBS / PROJETOR)"
        self.title(f"📺 WebLive Studio — {title_mode}")
        self.geometry("960x540")
        self.configure(bg="#000000")
        self.is_fullscreen = False

        self.canvas = tk.Canvas(self, width=960, height=540, bg="#000000", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        # Duplo clique ou F11 alterna Tela Cheia
        self.bind("<Double-Button-1>", self.toggle_fullscreen)
        self.bind("<F11>", self.toggle_fullscreen)
        self.bind("<Escape>", lambda e: self.set_fullscreen(False))

    def toggle_fullscreen(self, event=None):
        self.set_fullscreen(not self.is_fullscreen)

    def set_fullscreen(self, state: bool):
        self.is_fullscreen = state
        self.attributes("-fullscreen", self.is_fullscreen)


class WebLiveNativeStudioApp:
    """Estação Completa de Produção Ao Vivo 100% Nativa em Desktop e 100% em Português-BR."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("🎬 WebLive Studio Pro v3.1 — Estação Nativa de Produção Ao Vivo (Português-BR)")
        self.root.geometry("1440x860")
        self.root.minsize(1220, 760)
        self.root.configure(bg="#0b0e14")

        # Servidor de sincronia em segundo plano (link do celular, API Stream Deck #46, alertas #33)
        self.server = WebLivePythonServer(port=3000)
        self.active_port = self.server.start()
        self.lan_ip = get_lan_ip()
        self._hub_queue = HUB.register()
        self._ui_queue = queue.Queue()

        # Estado completo do Switcher em Português-BR
        self.scenes = [
            {"id": "scene_1", "key": "1", "name": "Estúdio Principal", "subtitle": "Apresentador • Câmera 1", "sourceType": "cam1", "pipSource": "guest1", "layoutMode": "Câmera Única (Tela Cheia)", "bgTheme": "Grade Cibernética"},
            {"id": "scene_2", "key": "2", "name": "Repórter Externo", "subtitle": "Chamada Remota pelo Celular", "sourceType": "guest1", "pipSource": "cam1", "layoutMode": "Câmera Única (Tela Cheia)", "bgTheme": "Globo Telejornal"},
            {"id": "scene_3", "key": "3", "name": "Entrevista Janela Dupla", "subtitle": "Estúdio + Repórter Sobreposto (#1)", "sourceType": "cam1", "pipSource": "guest1", "layoutMode": "Janela Sobreposta (PiP)", "bgTheme": "Grade Cibernética"},
            {"id": "scene_4", "key": "4", "name": "Mosaico 4 Câmeras", "subtitle": "Debate 4 Convidados (#2)", "sourceType": "cam1", "pipSource": "guest1", "layoutMode": "Mosaico 4 Câmeras", "bgTheme": "Globo Telejornal"},
            {"id": "scene_5", "key": "5", "name": "Vídeo / Mídia Externa", "subtitle": "Vídeo Extraído / Lista de Reprodução (#22)", "sourceType": "media1", "pipSource": "cam1", "layoutMode": "Câmera Única (Tela Cheia)", "bgTheme": "Iluminação de Estádio"},
            {"id": "scene_6", "key": "6", "name": "Mosaico 8 Câmeras", "subtitle": "Super Mosaico 8 Participantes (#2)", "sourceType": "cam1", "pipSource": "guest1", "layoutMode": "Mosaico 8 Câmeras", "bgTheme": "Iluminação de Estádio"},
        ]
        self.pvw_idx = 1
        self.pgm_idx = 0
        self.fade_from_idx = -1
        self.fade_start = 0.0
        self.stinger_start = 0.0
        self.replay_token = 0
        self._transition_pending = False
        self.scene_locked = tk.BooleanVar(value=False)
        self.snap_grid_enabled = tk.BooleanVar(value=False)
        self.whiteboard_enabled = tk.BooleanVar(value=False)
        self.whiteboard_color = "#ffeb3b"
        self.whiteboard_strokes = []
        self.current_stroke = None

        # Configurações Visuais em Português-BR (#1-#10) — valem para a cena em PRÉVIA
        self.layout_mode_var = tk.StringVar(value=LAYOUT_CHOICES[0])
        self.bg_theme_var = tk.StringVar(value=THEME_CHOICES[0])
        self.main_source_var = tk.StringVar(value=SOURCE_NAME_BY_ID["cam1"])
        self.pip_source_var = tk.StringVar(value=SOURCE_NAME_BY_ID["guest1"])
        self._loading_scene_fields = False
        self.chroma_enabled = tk.BooleanVar(value=False)
        self.chroma_tol = tk.IntVar(value=60)
        self.pip_scale = tk.IntVar(value=28)
        self.brightness_var = tk.IntVar(value=100)
        self.contrast_var = tk.IntVar(value=100)
        self.saturation_var = tk.IntVar(value=100)
        self.crop_top_var = tk.IntVar(value=0)
        self.watermark_text = tk.StringVar(value="WEBLIVE AO VIVO")

        # Overlays Gráficos em Português-BR
        self.lt_visible = False
        self.lt_changed_at = 0.0
        self._lt_token = 0
        self.lt_title = tk.StringVar(value="DR. CARLOS MENDES")
        self.lt_sub = tk.StringVar(value="Especialista em Transmissões Ao Vivo")
        self.lt_mode = tk.StringVar(value="Fixa (Permanente)")

        self.sb_visible = False
        self.sb_team_a = tk.StringVar(value="BRASIL")
        self.sb_pts_a = tk.IntVar(value=2)
        self.sb_team_b = tk.StringVar(value="ARGENTINA")
        self.sb_pts_b = tk.IntVar(value=1)
        self.sb_timer_sec = 0
        self.sb_timer_running = False

        self.ticker_visible = True
        self.ticker_text = tk.StringVar(value="URGENTE: acompanhe a transmissão ao vivo do WebLive Studio • ")
        self.rss_url_var = tk.StringVar(value=DEFAULT_RSS_URL)

        self.qr_visible = False
        self.qr_url = tk.StringVar(value="https://weblive.studio/pix")
        self.poll_visible = False
        self.poll_votes_a = 0
        self.poll_votes_b = 0
        self.poll_label_a = tk.StringVar(value="Sim")
        self.poll_label_b = tk.StringVar(value="Não")
        self.goal_visible = False
        self.goal_current_var = tk.IntVar(value=0)
        self.goal_target_var = tk.IntVar(value=1000)
        self.featured_comment_visible = False
        self.featured_author = "@Mariana_TV"
        self.featured_text = "Todos os menus em Português-BR na estação nativa!"
        self.weather_visible = False
        self.weather_text = ""
        self.weather_city = tk.StringVar(value="São Paulo")
        self.weather_fetched_at = 0.0
        self.countdown_visible = False
        self.countdown_sec = 180
        self.alert_start = 0.0
        self.alert_user = ""
        self.alert_msg = ""

        # Canais de Áudio Multi-Pista (#11-#20) — interface pronta, processamento de som real é a próxima etapa
        self.panic_muted = False
        self.ducking_enabled = tk.BooleanVar(value=True)
        self.auto_voice_switch = tk.BooleanVar(value=False)
        self.talkback_active = False
        self.audio_channels = [
            {"id": "cam1", "name": "Câmera 1 (Apresentador)", "vol": tk.DoubleVar(value=90), "pan": tk.DoubleVar(value=0), "delay": tk.IntVar(value=0), "muted": False, "pfl": False, "vu": 0},
            {"id": "guest1", "name": "Repórter Remoto (Sem Eco)", "vol": tk.DoubleVar(value=85), "pan": tk.DoubleVar(value=0), "delay": tk.IntVar(value=40), "muted": False, "pfl": False, "vu": 0},
            {"id": "media1", "name": "Mídia / Vídeos / Trilha", "vol": tk.DoubleVar(value=75), "pan": tk.DoubleVar(value=0), "delay": tk.IntVar(value=0), "muted": False, "pfl": False, "vu": 0},
            {"id": "sfx", "name": "Painel de Efeitos / Vinhetas", "vol": tk.DoubleVar(value=85), "pan": tk.DoubleVar(value=0), "delay": tk.IntVar(value=0), "muted": False, "pfl": False, "vu": 0},
        ]

        # Fontes de vídeo reais + compositor do Programa + saídas FFmpeg
        self.camera_names = []
        self.cam_vars = {"cam1": tk.StringVar(value="0 • Câmera 0"), "cam2": tk.StringVar(value=CAM_OFF)}
        self.sources = {"cam1": None, "cam2": None, "media1": None}
        self.compositor = ProgramCompositor(self.sources)
        self.recorder = FFmpegOutput("record", lambda: self.compositor.latest_pgm)
        RTMP_ENGINE.frame_provider = lambda: self.compositor.latest_pgm
        self.rtmp_key_var = tk.StringVar(value="")
        self._rtmp_ui_live = False
        self._speedtest_running = False
        self._last_comp_error = ""
        self._cpu_last = (time.process_time(), time.perf_counter())

        self.playlist = [
            "https://www.youtube.com/watch?v=jfKfPfyJRdk",
            "https://www.youtube.com/watch?v=5qap5aO4i9A",
        ]
        self.media_autoadvance = tk.BooleanVar(value=False)
        self.scheduled_events = []
        self.projectors = []
        self.frame_counter = 0

        self._setup_styles()
        self._build_native_menubar_ptbr()
        self._build_top_bar()
        self._build_status_bar()
        self._build_3column_workspace()
        self._bind_keyboard_shortcuts()
        self._load_scene_fields()
        self._bind_scene_field_traces()

        self.compositor.state = self._snapshot_state()
        self.compositor.start()
        self._set_camera("cam1", 0)
        self._refresh_camera_list()

        self.log_action("Estação Desktop Nativa WebLive Studio Pro v3.1 iniciada (vídeo real 1280x720 @ 30fps)")
        self._start_render_loop()
        self._start_1s_timer()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TNotebook", background="#131822", borderwidth=0)
        style.configure("TNotebook.Tab", background="#1c2331", foreground="#8b9bb4", padding=[10, 5], font=("Segoe UI", 9, "bold"))
        style.map("TNotebook.Tab", background=[("selected", "#2979ff")], foreground=[("selected", "#ffffff")])

    # =========================================================================
    # BARRA DE MENUS SUPERIOR NATIVA DO WINDOWS EM PORTUGUÊS-BR
    # =========================================================================
    def _build_native_menubar_ptbr(self):
        menubar = tk.Menu(self.root)

        # Menu 1: Arquivo
        menu_arquivo = tk.Menu(menubar, tearoff=0)
        menu_arquivo.add_command(label="➕ Nova Cena Personalizada...", command=self.add_custom_scene)
        menu_arquivo.add_separator()
        menu_arquivo.add_command(label="💾 Exportar Projeto Completo (.JSON)...", command=self.export_json)
        menu_arquivo.add_command(label="📂 Importar Projeto Salvo (.JSON)...", command=self.import_json)
        menu_arquivo.add_separator()
        menu_arquivo.add_command(label="🎞️ Abrir Vídeo do Computador...", command=self.open_media_file)
        menu_arquivo.add_command(label="⏺️ Iniciar / Parar Gravação de Segurança Local", command=self.toggle_backup_recording)
        menu_arquivo.add_command(label="📁 Abrir Pasta das Gravações", command=self.open_recordings_folder)
        menu_arquivo.add_separator()
        menu_arquivo.add_command(label="❌ Sair do Programa", command=self._on_close)
        menubar.add_cascade(label="Arquivo", menu=menu_arquivo)

        # Menu 2: Cenas e Transições
        menu_cenas = tk.Menu(menubar, tearoff=0)
        menu_cenas.add_command(label="✂️ Corte Seco Imediato (Atalho: Espaço)", command=lambda: self.execute_transition("CORTE SECO"))
        menu_cenas.add_command(label="✨ Transição Suave Automática", command=lambda: self.execute_transition("SUAVE"))
        menu_cenas.add_command(label="⚡ Transição com Vinheta Animada", command=lambda: self.execute_transition("VINHETA"))
        menu_cenas.add_separator()
        menu_cenas.add_command(label="⏪ Replay em Câmera Lenta (últimos 5 segundos)", command=self.trigger_instant_replay)
        menu_cenas.add_separator()
        for i, sc in enumerate(self.scenes):
            menu_cenas.add_command(label=f"Selecionar Cena {i+1}: {sc['name']}", command=lambda idx=i: self.select_preview_scene(idx))
        menubar.add_cascade(label="Cenas e Cortes", menu=menu_cenas)

        # Menu 3: Gráficos e Interatividade
        menu_graficos = tk.Menu(menubar, tearoff=0)
        menu_graficos.add_command(label="🏷️ Mostrar / Ocultar Tarjeta (GC)", command=self.toggle_lower_third)
        menu_graficos.add_command(label="⚽ Mostrar / Ocultar Placar Esportivo", command=self.toggle_scoreboard)
        menu_graficos.add_command(label="📰 Mostrar / Ocultar Barra de Notícias", command=self.toggle_ticker)
        menu_graficos.add_command(label="📡 Atualizar Notícias Reais da Internet", command=self.fetch_rss_to_ticker)
        menu_graficos.add_separator()
        menu_graficos.add_command(label="📱 Mostrar / Ocultar Código QR na Tela", command=self.toggle_qr)
        menu_graficos.add_command(label="📊 Mostrar / Ocultar Enquete Ao Vivo", command=self.toggle_poll)
        menu_graficos.add_command(label="🎯 Mostrar / Ocultar Barra de Meta", command=self.toggle_goal)
        menu_graficos.add_command(label="🎉 Disparar Alerta de Doação / Superchat", command=self.trigger_superchat)
        menu_graficos.add_command(label="🌤️ Mostrar / Ocultar Previsão do Tempo", command=self.toggle_weather)
        menu_graficos.add_command(label="⏳ Mostrar / Ocultar Contagem Regressiva", command=self.toggle_countdown)
        menubar.add_cascade(label="Gráficos na Tela", menu=menu_graficos)

        # Menu 4: Áudio e Efeitos
        menu_audio = tk.Menu(menubar, tearoff=0)
        menu_audio.add_command(label="🔇 Silenciar Tudo — Botão de Pânico", command=self.toggle_panic_mute)
        menu_audio.add_separator()
        menu_audio.add_command(label="👏 Tocar Efeito: Aplausos", command=lambda: self.play_native_sfx("Aplausos", 900))
        menu_audio.add_command(label="🎵 Tocar Efeito: Vinheta de TV", command=lambda: self.play_native_sfx("Vinheta de TV", 660))
        menu_audio.add_command(label="🔔 Tocar Efeito: Alerta Urgente", command=lambda: self.play_native_sfx("Alerta Urgente", 1200))
        menu_audio.add_command(label="⏱️ Tocar Efeito: Sinal de Cronômetro", command=lambda: self.play_native_sfx("Sinal Sonoro", 880))
        menubar.add_cascade(label="Áudio e Efeitos", menu=menu_audio)

        # Menu 5: Saídas de Vídeo (OBS)
        menu_saidas = tk.Menu(menubar, tearoff=0)
        menu_saidas.add_command(label="📺 Abrir Projetor de Saída Principal (Para Captura de Janela no OBS)", command=lambda: self.open_native_projector(clean_feed=False))
        menu_saidas.add_command(label="🧼 Abrir Projetor de Saída Limpa — Sem Gráficos (#43)", command=lambda: self.open_native_projector(clean_feed=True))
        menu_saidas.add_separator()
        menu_saidas.add_command(label="🚀 Iniciar / Parar Transmissão Externa (YouTube/Twitch)", command=self.toggle_rtmp)
        menubar.add_cascade(label="Saídas para OBS e Transmissão", menu=menu_saidas)

        # Menu 6: Ajuda
        menu_ajuda = tk.Menu(menubar, tearoff=0)
        menu_ajuda.add_command(
            label="📘 Como Usar no OBS Studio",
            command=lambda: messagebox.showinfo(
                "Como Capturar no OBS Studio",
                "1. Clique em 'Saídas para OBS e Transmissão' -> 'Abrir Projetor de Saída Principal'.\n"
                "2. No OBS Studio, adicione uma fonte de 'Captura de Janela'.\n"
                "3. Selecione a janela '📺 WebLive Studio — SAÍDA PRINCIPAL'.\n"
                "4. Dica: Dê duplo clique ou aperte F11 no projetor para Tela Cheia!",
            ),
        )
        menu_ajuda.add_command(
            label="📡 Como Transmitir Direto (YouTube/Twitch)",
            command=lambda: messagebox.showinfo(
                "Transmissão Direta",
                "1. Na aba 'Transmissão', informe o servidor RTMP e a chave da plataforma.\n"
                "   YouTube: rtmp://a.rtmp.youtube.com/live2  •  Twitch: rtmp://live.twitch.tv/app\n"
                "2. Clique em 'Iniciar Transmissão'. Vai ao ar o PROGRAMA real em 1280x720 @ 30fps.\n"
                "3. O áudio ainda sai em silêncio: a mesa de som real é a próxima etapa.\n"
                "Requer FFmpeg instalado (winget install Gyan.FFmpeg).",
            ),
        )
        menu_ajuda.add_command(
            label="ℹ️ Sobre o WebLive Studio Pro",
            command=lambda: messagebox.showinfo(
                "Sobre o Programa",
                "WebLive Studio Pro v3.1 (Edição Nativa Português-BR)\n"
                "Estação de Produção Ao Vivo com câmeras e vídeos reais, corte de cenas, gráficos,\n"
                "gravação local e transmissão RTMP via FFmpeg.",
            ),
        )
        menubar.add_cascade(label="Ajuda", menu=menu_ajuda)

        self.root.config(menu=menubar)

    # =========================================================================
    # BARRA SUPERIOR (Relógio #26, Saúde #42, Perfis #29, Silenciar #20, Projetor OBS)
    # =========================================================================
    def _build_top_bar(self):
        self.topbar = tk.Frame(self.root, bg="#131822", height=52, highlightthickness=1, highlightbackground="#2b3548")
        self.topbar.pack(fill="x", side="top")

        tk.Label(
            self.topbar,
            text="🔴 WEBLIVE STUDIO PRO • ESTAÇÃO DE PRODUÇÃO AO VIVO",
            font=("Segoe UI", 11, "bold"),
            fg="#ff5252",
            bg="#131822",
        ).pack(side="left", padx=12)

        self.lbl_clock = tk.Label(self.topbar, text="🕒 00:00:00 (Brasília)", font=("Consolas", 9, "bold"), fg="#38bdf8", bg="#1c2331", padx=8, pady=4)
        self.lbl_clock.pack(side="left", padx=4)

        tk.Button(
            self.topbar,
            text="🧼 Abrir Janela Saída Limpa (#43)",
            font=("Segoe UI", 8, "bold"),
            bg="#252f42",
            fg="#ffffff",
            relief="flat",
            cursor="hand2",
            padx=8,
            command=lambda: self.open_native_projector(clean_feed=True),
        ).pack(side="right", padx=(4, 10), pady=8)

        tk.Button(
            self.topbar,
            text="📺 Abrir Projetor para OBS (Saída no Ar)",
            font=("Segoe UI", 8, "bold"),
            bg="#2979ff",
            fg="#ffffff",
            relief="flat",
            cursor="hand2",
            padx=10,
            command=lambda: self.open_native_projector(clean_feed=False),
        ).pack(side="right", padx=4, pady=8)

        self.btn_panic = tk.Button(
            self.topbar,
            text="🔇 SILENCIAR TUDO (#20)",
            font=("Segoe UI", 8, "bold"),
            bg="#e53935",
            fg="#ffffff",
            relief="flat",
            cursor="hand2",
            padx=10,
            command=self.toggle_panic_mute,
        )
        self.btn_panic.pack(side="right", padx=4, pady=8)

        self.role_var = tk.StringVar(value="Perfil: Diretor Geral")
        role_menu = ttk.Combobox(
            self.topbar,
            textvariable=self.role_var,
            values=["Perfil: Diretor Geral", "Perfil: Operador de Caracteres (GC)", "Perfil: Operador de Som"],
            state="readonly",
            width=26,
        )
        role_menu.pack(side="right", padx=6)
        role_menu.bind("<<ComboboxSelected>>", lambda e: self.log_action(f"Perfil de acesso (#29) alterado para {self.role_var.get()}"))

    # =========================================================================
    # BARRA DE STATUS INFERIOR (Saúde #42: QPS da saída, processador, GRAVANDO / AO VIVO)
    # =========================================================================
    def _build_status_bar(self):
        bar = tk.Frame(self.root, bg="#131822", highlightthickness=1, highlightbackground="#2b3548")
        bar.pack(fill="x", side="bottom")
        self.lbl_health = tk.Label(bar, text="⚡ iniciando vídeo...", font=("Consolas", 9, "bold"), fg="#00e676", bg="#131822", padx=10, pady=3)
        self.lbl_health.pack(side="left")
        ffmpeg_ok = find_ffmpeg() is not None
        tk.Label(
            bar,
            text="FFmpeg: pronto para gravar e transmitir" if ffmpeg_ok else "⚠️ FFmpeg não encontrado: gravação e transmissão indisponíveis (winget install Gyan.FFmpeg)",
            font=("Consolas", 8), fg="#64748b" if ffmpeg_ok else "#ffb300", bg="#131822", padx=10,
        ).pack(side="right")

    # =========================================================================
    # ÁREA DE TRABALHO EM 3 COLUNAS (100% PORTUGUÊS-BR)
    # =========================================================================
    def _build_3column_workspace(self):
        workspace = tk.Frame(self.root, bg="#0b0e14", padx=8, pady=8)
        workspace.pack(fill="both", expand=True)

        workspace.columnconfigure(0, weight=0, minsize=310)
        workspace.columnconfigure(1, weight=1)
        workspace.columnconfigure(2, weight=0, minsize=340)
        workspace.rowconfigure(0, weight=1)

        col_left = tk.Frame(workspace, bg="#0b0e14")
        col_left.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        self._build_left_column(col_left)

        col_center = tk.Frame(workspace, bg="#0b0e14")
        col_center.grid(row=0, column=1, sticky="nsew", padx=4)
        self._build_center_column(col_center)

        col_right = tk.Frame(workspace, bg="#0b0e14")
        col_right.grid(row=0, column=2, sticky="nsew", padx=(6, 0))
        self._build_right_column(col_right)

    def _build_left_column(self, parent):
        # 1. Cenas
        scenes_card = tk.LabelFrame(parent, text=" 🎬 CENAS E ATALHOS [TECLAS 1 A 6 / ESPAÇO] ", font=("Segoe UI", 9, "bold"), fg="#8b9bb4", bg="#131822", bd=1, relief="solid", padx=8, pady=8)
        scenes_card.pack(fill="x", pady=(0, 8))

        top_sc = tk.Frame(scenes_card, bg="#131822")
        top_sc.pack(fill="x", pady=(0, 6))
        tk.Checkbutton(top_sc, text="🔒 Travar Cena (#44)", variable=self.scene_locked, bg="#131822", fg="#ffb300", selectcolor="#1c2331", activebackground="#131822", font=("Segoe UI", 8, "bold")).pack(side="left")
        tk.Button(top_sc, text="+ Nova Cena", bg="#2979ff", fg="#fff", relief="flat", font=("Segoe UI", 8, "bold"), command=self.add_custom_scene).pack(side="right")

        self.scenes_frame = tk.Frame(scenes_card, bg="#131822")
        self.scenes_frame.pack(fill="x")
        self.scene_buttons = []
        self._render_scene_buttons()

        # 2. Câmeras reais (webcam, celular como câmera virtual, OBS Virtual Camera)
        cam_card = tk.LabelFrame(parent, text=" 📷 CÂMERAS E FONTES DE VÍDEO ", font=("Segoe UI", 9, "bold"), fg="#8b9bb4", bg="#131822", bd=1, relief="solid", padx=8, pady=6)
        cam_card.pack(fill="x", pady=(0, 8))
        cam_card.columnconfigure(1, weight=1)
        self.cam_combos, self.cam_status_labels = {}, {}
        for row, slot in enumerate(CAMERA_SLOTS):
            tk.Label(cam_card, text=f"{SOURCE_NAME_BY_ID[slot]}:", bg="#131822", fg="#cbd5e1", font=("Segoe UI", 8, "bold")).grid(row=row * 2, column=0, sticky="w")
            cb = ttk.Combobox(cam_card, textvariable=self.cam_vars[slot], state="readonly", width=28)
            cb.grid(row=row * 2, column=1, sticky="ew", padx=(6, 0), pady=(2, 0))
            cb.bind("<<ComboboxSelected>>", lambda e, s=slot: self._on_camera_selected(s))
            lbl = tk.Label(cam_card, text="desligada", bg="#131822", fg="#64748b", font=("Consolas", 7), anchor="w")
            lbl.grid(row=row * 2 + 1, column=1, sticky="ew", padx=(6, 0))
            self.cam_combos[slot], self.cam_status_labels[slot] = cb, lbl
        tk.Button(cam_card, text="🔄 Procurar Câmeras", bg="#252f42", fg="#fff", relief="flat", font=("Segoe UI", 8), command=self._refresh_camera_list).grid(row=4, column=0, columnspan=2, sticky="ew", pady=(4, 0))

        # 3. Convidado Remoto / Celular
        rtc_card = tk.LabelFrame(parent, text=" 📱 CONVIDADO REMOTO E RETORNO SEM ECO (#7) ", font=("Segoe UI", 9, "bold"), fg="#8b9bb4", bg="#131822", bd=1, relief="solid", padx=8, pady=8)
        rtc_card.pack(fill="x", pady=(0, 8))

        guest_url = f"http://{self.lan_ip}:{self.active_port}/guest.html?guest=Reporter1"
        ent_guest = tk.Entry(rtc_card, font=("Consolas", 8), bg="#1c2331", fg="#38bdf8", relief="flat")
        ent_guest.insert(0, guest_url)
        ent_guest.configure(state="readonly")
        ent_guest.pack(fill="x", pady=(0, 6))

        rtc_btns = tk.Frame(rtc_card, bg="#131822")
        rtc_btns.pack(fill="x", pady=(0, 6))
        tk.Button(rtc_btns, text="📋 Copiar Link do Celular", bg="#2b3548", fg="#fff", relief="flat", font=("Segoe UI", 8, "bold"), command=lambda: self._copy_text(guest_url)).pack(side="left", fill="x", expand=True, padx=(0, 4))
        tk.Button(rtc_btns, text="📶 Testar Internet (#41)", bg="#2b3548", fg="#00e676", relief="flat", font=("Segoe UI", 8, "bold"), command=self.run_native_speedtest).pack(side="left", fill="x", expand=True)

        self.btn_talkback = tk.Button(rtc_card, text="🎙️ SEGURE PARA FALAR COM O REPÓRTER (#16)", bg="#ffb300", fg="#000", relief="flat", font=("Segoe UI", 8, "bold"))
        self.btn_talkback.pack(fill="x", pady=(0, 4))
        self.btn_talkback.bind("<ButtonPress-1>", lambda e: self.set_talkback(True))
        self.btn_talkback.bind("<ButtonRelease-1>", lambda e: self.set_talkback(False))

        self.lbl_rtc_info = tk.Label(rtc_card, text="ℹ️ O vídeo do celular ainda não entra no PROGRAMA desta estação (próxima etapa).", font=("Consolas", 8), fg="#94a3b8", bg="#131822", wraplength=285, justify="left")
        self.lbl_rtc_info.pack(anchor="w")

        # 4. Vídeos da Internet / do Computador e Lista de Reprodução (#22)
        media_card = tk.LabelFrame(parent, text=" 🎞️ VÍDEOS (INTERNET OU COMPUTADOR) E FILA (#22) ", font=("Segoe UI", 9, "bold"), fg="#8b9bb4", bg="#131822", bd=1, relief="solid", padx=8, pady=8)
        media_card.pack(fill="both", expand=True)

        self.ent_media_url = tk.Entry(media_card, font=("Consolas", 8), bg="#1c2331", fg="#fff", insertbackground="#fff", relief="flat")
        self.ent_media_url.insert(0, "https://www.youtube.com/watch?v=jfKfPfyJRdk")
        self.ent_media_url.pack(fill="x", pady=(0, 6))

        m_btns = tk.Frame(media_card, bg="#131822")
        m_btns.pack(fill="x", pady=(0, 4))
        tk.Button(m_btns, text="🐍 Carregar Link", bg="#ffb300", fg="#000", relief="flat", font=("Segoe UI", 8, "bold"), command=self.extract_ytdlp_native).pack(side="left", fill="x", expand=True, padx=(0, 3))
        tk.Button(m_btns, text="📂 Do Computador", bg="#2979ff", fg="#fff", relief="flat", font=("Segoe UI", 8, "bold"), command=self.open_media_file).pack(side="left", padx=3)
        self.btn_media_pause = tk.Button(m_btns, text="⏸ Pausar", bg="#252f42", fg="#fff", relief="flat", font=("Segoe UI", 8, "bold"), command=self.toggle_media_pause)
        self.btn_media_pause.pack(side="left")

        q_btns = tk.Frame(media_card, bg="#131822")
        q_btns.pack(fill="x", pady=(0, 4))
        tk.Button(q_btns, text="+ Adicionar à Fila", bg="#252f42", fg="#fff", relief="flat", font=("Segoe UI", 8, "bold"), command=self.add_to_playlist).pack(side="left", padx=(0, 3))
        tk.Button(q_btns, text="⏭ Próximo", bg="#252f42", fg="#fff", relief="flat", font=("Segoe UI", 8, "bold"), command=self.next_playlist_item).pack(side="left", padx=3)
        tk.Checkbutton(q_btns, text="Avançar sozinho", variable=self.media_autoadvance, bg="#131822", fg="#cbd5e1", selectcolor="#1c2331", activebackground="#131822", font=("Segoe UI", 8)).pack(side="left", padx=3)

        self.lbl_media_status = tk.Label(media_card, text="Nenhum vídeo carregado no canal MÍDIA", font=("Consolas", 7), fg="#64748b", bg="#131822", anchor="w", wraplength=285, justify="left")
        self.lbl_media_status.pack(fill="x", pady=(0, 4))

        self.lst_playlist = tk.Listbox(media_card, bg="#090c10", fg="#cbd5e1", font=("Consolas", 8), height=4, relief="flat")
        self.lst_playlist.pack(fill="both", expand=True)
        self._refresh_playlist_box()

    def _build_center_column(self, parent):
        # 1. Monitores Duplos: PRÉVIA e NO AR
        mon_card = tk.Frame(parent, bg="#131822", highlightthickness=1, highlightbackground="#2b3548", padx=10, pady=10)
        mon_card.pack(fill="x", pady=(0, 8))

        mon_grid = tk.Frame(mon_card, bg="#131822")
        mon_grid.pack(fill="x")
        mon_grid.columnconfigure(0, weight=1)
        mon_grid.columnconfigure(1, weight=0)
        mon_grid.columnconfigure(2, weight=1)

        pvw_box = tk.Frame(mon_grid, bg="#000", highlightthickness=2, highlightbackground="#00c853")
        pvw_box.grid(row=0, column=0, sticky="nsew")
        self.lbl_pvw_title = tk.Label(pvw_box, text="🟢 PRÉVIA (PREPARAÇÃO) • REPÓRTER EXTERNO", font=("Segoe UI", 8, "bold"), bg="#072b16", fg="#4ade80", anchor="w", padx=6)
        self.lbl_pvw_title.pack(fill="x")
        self.pvw_canvas = tk.Canvas(pvw_box, width=360, height=202, bg="#000000", highlightthickness=0)
        self.pvw_canvas.pack(fill="both", expand=True)

        # Barra Central de Transição em Português-BR
        t_bar = tk.Frame(mon_grid, bg="#131822", padx=8)
        t_bar.grid(row=0, column=1, sticky="ns")
        tk.Button(t_bar, text="✂️ CORTAR\n[Espaço]", bg="#e53935", fg="#fff", font=("Segoe UI", 8, "bold"), relief="flat", width=10, pady=6, command=lambda: self.execute_transition("CORTE SECO")).pack(pady=3)
        tk.Button(t_bar, text="✨ SUAVE", bg="#2979ff", fg="#fff", font=("Segoe UI", 8, "bold"), relief="flat", width=10, pady=4, command=lambda: self.execute_transition("SUAVE")).pack(pady=3)
        tk.Button(t_bar, text="⚡ VINHETA", bg="#ffb300", fg="#000", font=("Segoe UI", 8, "bold"), relief="flat", width=10, pady=4, command=lambda: self.execute_transition("VINHETA")).pack(pady=3)
        tk.Button(t_bar, text="⏪ REPLAY", bg="#252f42", fg="#fff", font=("Segoe UI", 8, "bold"), relief="flat", width=10, pady=4, command=self.trigger_instant_replay).pack(pady=3)
        tk.Checkbutton(t_bar, text="📏 Grade #47", variable=self.snap_grid_enabled, bg="#131822", fg="#38bdf8", selectcolor="#1c2331", font=("Segoe UI", 8)).pack(pady=2)

        pgm_box = tk.Frame(mon_grid, bg="#000", highlightthickness=2, highlightbackground="#e53935")
        pgm_box.grid(row=0, column=2, sticky="nsew")
        self.lbl_pgm_title = tk.Label(pgm_box, text="🔴 NO AR (PROGRAMA) • ESTÚDIO PRINCIPAL", font=("Segoe UI", 8, "bold"), bg="#330b0b", fg="#ff5252", anchor="w", padx=6)
        self.lbl_pgm_title.pack(fill="x")
        self.pgm_canvas = tk.Canvas(pgm_box, width=360, height=202, bg="#000000", highlightthickness=0, cursor="crosshair")
        self.pgm_canvas.pack(fill="both", expand=True)

        self.pgm_canvas.bind("<ButtonPress-1>", self._wb_start)
        self.pgm_canvas.bind("<B1-Motion>", self._wb_draw)
        self.pgm_canvas.bind("<ButtonRelease-1>", self._wb_end)
        for cv in (self.pvw_canvas, self.pgm_canvas):
            cv.bind("<Configure>", lambda e, c=cv: self._keep_16x9(c, e))

        # Barra Inferior dos Monitores em Português-BR
        tools_bar = tk.Frame(mon_card, bg="#131822")
        tools_bar.pack(fill="x", pady=(8, 0))
        tk.Checkbutton(tools_bar, text="✏️ Desenhar na Tela Ao Vivo (Quadro Branco #40)", variable=self.whiteboard_enabled, bg="#131822", fg="#ffeb3b", selectcolor="#1c2331", font=("Segoe UI", 8, "bold")).pack(side="left")
        tk.Button(tools_bar, text="🎨 Escolher Cor", bg="#252f42", fg="#fff", relief="flat", font=("Segoe UI", 8), command=self.pick_whiteboard_color).pack(side="left", padx=4)
        tk.Button(tools_bar, text="🗑️ Limpar Desenho", bg="#252f42", fg="#fff", relief="flat", font=("Segoe UI", 8), command=self.clear_whiteboard).pack(side="left", padx=4)

        self.btn_record = tk.Button(tools_bar, text="⏺️ Gravar Cópia Local (#27)", bg="#252f42", fg="#fff", relief="flat", font=("Segoe UI", 8, "bold"), command=self.toggle_backup_recording)
        self.btn_record.pack(side="right", padx=2)
        tk.Button(tools_bar, text="⏳ Contagem Regressiva (#25)", bg="#252f42", fg="#38bdf8", relief="flat", font=("Segoe UI", 8, "bold"), command=self.toggle_countdown).pack(side="right", padx=4)

        # 2. Abas de Produção Completas em Português-BR
        self.notebook = ttk.Notebook(parent)
        self.notebook.pack(fill="both", expand=True)

        tab_gc = tk.Frame(self.notebook, bg="#131822", padx=10, pady=10)
        tab_video = tk.Frame(self.notebook, bg="#131822", padx=10, pady=10)
        tab_social = tk.Frame(self.notebook, bg="#131822", padx=10, pady=10)
        tab_auto = tk.Frame(self.notebook, bg="#131822", padx=10, pady=10)

        self.notebook.add(tab_gc, text="🏷️ Tarjetas, Placar e Notícias")
        self.notebook.add(tab_video, text="🎨 Vídeo, Mosaico e Fundo Verde (#1-#10)")
        self.notebook.add(tab_social, text="💬 Bate-Papo, Enquete, Meta e Código QR (#31-#40)")
        self.notebook.add(tab_auto, text="⚙️ Transmissão, Agendador e Histórico (#28-#50)")

        self._populate_tab_gc(tab_gc)
        self._populate_tab_video(tab_video)
        self._populate_tab_social(tab_social)
        self._populate_tab_auto(tab_auto)

    def _populate_tab_gc(self, tab):
        row1 = tk.Frame(tab, bg="#131822")
        row1.pack(fill="x", pady=(0, 8))

        lt_frame = tk.LabelFrame(row1, text=" TARJETA DE IDENTIFICAÇÃO / CRÉDITOS (#5) ", font=("Segoe UI", 8, "bold"), fg="#38bdf8", bg="#1c2331", padx=8, pady=6)
        lt_frame.pack(side="left", fill="both", expand=True, padx=(0, 6))
        tk.Entry(lt_frame, textvariable=self.lt_title, bg="#0b0e14", fg="#fff", insertbackground="#fff", relief="flat", font=("Segoe UI", 9, "bold")).pack(fill="x", pady=2)
        tk.Entry(lt_frame, textvariable=self.lt_sub, bg="#0b0e14", fg="#38bdf8", insertbackground="#fff", relief="flat", font=("Segoe UI", 8)).pack(fill="x", pady=2)
        lt_ctrl = tk.Frame(lt_frame, bg="#1c2331")
        lt_ctrl.pack(fill="x", pady=4)
        ttk.Combobox(lt_ctrl, textvariable=self.lt_mode, values=["Fixa (Permanente)", "Temporária (5 segundos)", "Temporária (8 segundos)"], state="readonly", width=20).pack(side="left")
        tk.Button(lt_ctrl, text="🏷️ Mostrar / Ocultar Tarjeta", bg="#e53935", fg="#fff", relief="flat", font=("Segoe UI", 8, "bold"), command=self.toggle_lower_third).pack(side="right", fill="x", expand=True, padx=(6, 0))

        sb_frame = tk.LabelFrame(row1, text=" PLACAR ESPORTIVO E CRONÔMETRO (#4) ", font=("Segoe UI", 8, "bold"), fg="#00e676", bg="#1c2331", padx=8, pady=6)
        sb_frame.pack(side="left", fill="both", expand=True)
        teams_row = tk.Frame(sb_frame, bg="#1c2331")
        teams_row.pack(fill="x", pady=2)
        tk.Entry(teams_row, textvariable=self.sb_team_a, width=11, bg="#0b0e14", fg="#fff", relief="flat").pack(side="left", padx=2)
        tk.Spinbox(teams_row, from_=0, to=99, textvariable=self.sb_pts_a, width=4, bg="#2979ff", fg="#fff", relief="flat").pack(side="left", padx=2)
        tk.Entry(teams_row, textvariable=self.sb_team_b, width=11, bg="#0b0e14", fg="#fff", relief="flat").pack(side="left", padx=2)
        tk.Spinbox(teams_row, from_=0, to=99, textvariable=self.sb_pts_b, width=4, bg="#e53935", fg="#fff", relief="flat").pack(side="left", padx=2)

        sb_btns = tk.Frame(sb_frame, bg="#1c2331")
        sb_btns.pack(fill="x", pady=4)
        tk.Button(sb_btns, text="⚽ Placar no Ar", bg="#2979ff", fg="#fff", relief="flat", font=("Segoe UI", 8, "bold"), command=self.toggle_scoreboard).pack(side="left", fill="x", expand=True, padx=2)
        tk.Button(sb_btns, text="⏱️ Iniciar / Pausar", bg="#252f42", fg="#fff", relief="flat", font=("Segoe UI", 8), command=self.toggle_sb_timer).pack(side="left", padx=2)
        tk.Button(sb_btns, text="Zerar Tempo", bg="#252f42", fg="#fff", relief="flat", font=("Segoe UI", 8), command=self.reset_sb_timer).pack(side="left", padx=2)

        tk_frame = tk.LabelFrame(tab, text=" 📰 BARRA DE NOTÍCIAS ROLANTE (#7) E BUSCADOR DE MANCHETES (#37) ", font=("Segoe UI", 8, "bold"), fg="#8b9bb4", bg="#1c2331", padx=8, pady=6)
        tk_frame.pack(fill="x")
        tk_line = tk.Frame(tk_frame, bg="#1c2331")
        tk_line.pack(fill="x")
        tk.Entry(tk_line, textvariable=self.ticker_text, bg="#0b0e14", fg="#fff", relief="flat", font=("Segoe UI", 9)).pack(side="left", fill="x", expand=True, padx=(0, 6))
        tk.Button(tk_line, text="📡 Buscar Notícias (#37)", bg="#252f42", fg="#38bdf8", relief="flat", font=("Segoe UI", 8, "bold"), command=self.fetch_rss_to_ticker).pack(side="left", padx=3)
        tk.Button(tk_line, text="Barra no Ar", bg="#e53935", fg="#fff", relief="flat", font=("Segoe UI", 8, "bold"), command=self.toggle_ticker).pack(side="left")
        rss_line = tk.Frame(tk_frame, bg="#1c2331")
        rss_line.pack(fill="x", pady=(6, 0))
        tk.Label(rss_line, text="Endereço do feed RSS:", bg="#1c2331", fg="#94a3b8", font=("Segoe UI", 8)).pack(side="left")
        tk.Entry(rss_line, textvariable=self.rss_url_var, bg="#0b0e14", fg="#cbd5e1", relief="flat", font=("Consolas", 8)).pack(side="left", fill="x", expand=True, padx=(6, 0))

    def _populate_tab_video(self, tab):
        v_left = tk.LabelFrame(tab, text=" CENA EM PRÉVIA: FORMATO DE TELA, MOSAICO (#2), JANELA DUPLA (#1) E FUNDO VERDE (#3) ", font=("Segoe UI", 8, "bold"), fg="#38bdf8", bg="#1c2331", padx=8, pady=6)
        v_left.pack(side="left", fill="both", expand=True, padx=(0, 6))
        v_left.columnconfigure(1, weight=1)

        fields = (
            ("Disposição das Câmeras:", self.layout_mode_var, LAYOUT_CHOICES),
            ("Fundo Animado (#10):", self.bg_theme_var, THEME_CHOICES),
            ("Fonte Principal:", self.main_source_var, [n for _, n in SOURCE_CHOICES]),
            ("Fonte da Janela Sobreposta:", self.pip_source_var, [n for _, n in SOURCE_CHOICES]),
        )
        for row, (label, var, values) in enumerate(fields):
            tk.Label(v_left, text=label, bg="#1c2331", fg="#cbd5e1", font=("Segoe UI", 8)).grid(row=row, column=0, sticky="w", pady=2)
            ttk.Combobox(v_left, textvariable=var, values=values, state="readonly").grid(row=row, column=1, sticky="ew", padx=(6, 0), pady=2)

        tk.Checkbutton(v_left, text="🟢 Remover Fundo Verde — Chroma Key (#3)", variable=self.chroma_enabled, bg="#1c2331", fg="#00e676", selectcolor="#0b0e14", font=("Segoe UI", 8, "bold")).grid(row=4, column=0, columnspan=2, sticky="w", pady=2)
        tk.Scale(v_left, from_=0, to=120, orient="horizontal", label="Sensibilidade do Fundo Verde (#3)", variable=self.chroma_tol, bg="#1c2331", fg="#cbd5e1", highlightthickness=0).grid(row=5, column=0, columnspan=2, sticky="ew")
        tk.Scale(v_left, from_=15, to=45, orient="horizontal", label="Tamanho da Janela Sobreposta % (#1)", variable=self.pip_scale, bg="#1c2331", fg="#cbd5e1", highlightthickness=0).grid(row=6, column=0, columnspan=2, sticky="ew")

        v_right = tk.LabelFrame(tab, text=" AJUSTE DE COR DAS CÂMERAS (#5), RECORTE DE BORDAS (#4) E MARCA D'ÁGUA (#6) ", font=("Segoe UI", 8, "bold"), fg="#00e676", bg="#1c2331", padx=8, pady=6)
        v_right.pack(side="left", fill="both", expand=True)

        tk.Scale(v_right, from_=50, to=150, orient="horizontal", label="Brilho da Imagem % (#5)", variable=self.brightness_var, bg="#1c2331", fg="#cbd5e1", highlightthickness=0).pack(fill="x")
        tk.Scale(v_right, from_=50, to=150, orient="horizontal", label="Contraste % (#5)", variable=self.contrast_var, bg="#1c2331", fg="#cbd5e1", highlightthickness=0).pack(fill="x")
        tk.Scale(v_right, from_=0, to=200, orient="horizontal", label="Saturação % (#5)", variable=self.saturation_var, bg="#1c2331", fg="#cbd5e1", highlightthickness=0).pack(fill="x")
        tk.Scale(v_right, from_=0, to=35, orient="horizontal", label="Recorte da Borda Superior % (#4)", variable=self.crop_top_var, bg="#1c2331", fg="#cbd5e1", highlightthickness=0).pack(fill="x")

        wm_row = tk.Frame(v_right, bg="#1c2331")
        wm_row.pack(fill="x", pady=4)
        tk.Label(wm_row, text="Texto da Marca d'água (#6):", bg="#1c2331", fg="#cbd5e1", font=("Segoe UI", 8)).pack(side="left")
        tk.Entry(wm_row, textvariable=self.watermark_text, bg="#0b0e14", fg="#fff", relief="flat", width=18).pack(side="left", padx=6)

    def _populate_tab_social(self, tab):
        s_left = tk.LabelFrame(tab, text=" 💬 BATE-PAPO AO VIVO (#31), FILTRO DE PALAVRÕES (#38) E DESTAQUE (#35) ", font=("Segoe UI", 8, "bold"), fg="#38bdf8", bg="#1c2331", padx=8, pady=6)
        s_left.pack(side="left", fill="both", expand=True, padx=(0, 6))

        self.profanity_filter = tk.BooleanVar(value=True)
        tk.Checkbutton(s_left, text="Bloquear Palavrões Automaticamente (#38)", variable=self.profanity_filter, bg="#1c2331", fg="#cbd5e1", selectcolor="#0b0e14", font=("Segoe UI", 8)).pack(anchor="w")

        self.ent_chat_user = tk.Entry(s_left, bg="#0b0e14", fg="#38bdf8", relief="flat", font=("Segoe UI", 8, "bold"))
        self.ent_chat_user.insert(0, "@Mariana_TV")
        self.ent_chat_user.pack(fill="x", pady=2)

        self.ent_chat_msg = tk.Entry(s_left, bg="#0b0e14", fg="#fff", relief="flat", font=("Segoe UI", 9))
        self.ent_chat_msg.insert(0, "Todos os menus agora estão em Português-BR!")
        self.ent_chat_msg.pack(fill="x", pady=2)

        tk.Button(s_left, text="🌟 Exibir Comentário em Destaque na Tela (#35)", bg="#2979ff", fg="#fff", relief="flat", font=("Segoe UI", 8, "bold"), command=self.trigger_featured_comment).pack(fill="x", pady=4)
        tk.Label(s_left, text="O alerta de doação manual (#33) usa o nome e a mensagem acima.\nAlertas automáticos chegam pela API /api/webhook/alert.", bg="#1c2331", fg="#64748b", font=("Segoe UI", 7), justify="left").pack(anchor="w")

        s_right = tk.LabelFrame(tab, text=" 📊 ENQUETE (#32), META (#34), DOAÇÃO (#33), CLIMA (#36) E CÓDIGO QR (#9) ", font=("Segoe UI", 8, "bold"), fg="#ffb300", bg="#1c2331", padx=8, pady=6)
        s_right.pack(side="left", fill="both", expand=True)

        qr_row = tk.Frame(s_right, bg="#1c2331")
        qr_row.pack(fill="x", pady=2)
        tk.Entry(qr_row, textvariable=self.qr_url, bg="#0b0e14", fg="#fff", relief="flat").pack(side="left", fill="x", expand=True, padx=(0, 4))
        tk.Button(qr_row, text="📱 Código QR (#9)", bg="#2979ff", fg="#fff", relief="flat", font=("Segoe UI", 8, "bold"), command=self.toggle_qr).pack(side="left")

        poll_opts = tk.Frame(s_right, bg="#1c2331")
        poll_opts.pack(fill="x", pady=(4, 0))
        tk.Label(poll_opts, text="Opções da enquete:", bg="#1c2331", fg="#cbd5e1", font=("Segoe UI", 8)).pack(side="left")
        tk.Entry(poll_opts, textvariable=self.poll_label_a, width=12, bg="#0b0e14", fg="#fff", relief="flat").pack(side="left", padx=4)
        tk.Label(poll_opts, text="x", bg="#1c2331", fg="#cbd5e1", font=("Segoe UI", 8)).pack(side="left")
        tk.Entry(poll_opts, textvariable=self.poll_label_b, width=12, bg="#0b0e14", fg="#fff", relief="flat").pack(side="left", padx=4)
        tk.Button(poll_opts, text="Zerar Votos", bg="#252f42", fg="#fff", relief="flat", font=("Segoe UI", 8), command=self.reset_poll).pack(side="left", padx=2)

        poll_row = tk.Frame(s_right, bg="#1c2331")
        poll_row.pack(fill="x", pady=4)
        tk.Button(poll_row, text="📊 Enquete na Tela (#32)", bg="#252f42", fg="#fff", relief="flat", font=("Segoe UI", 8, "bold"), command=self.toggle_poll).pack(side="left", fill="x", expand=True, padx=2)
        tk.Button(poll_row, text="+Voto Opção A", bg="#2979ff", fg="#fff", relief="flat", font=("Segoe UI", 8), command=lambda: self.vote_poll("A")).pack(side="left", padx=2)
        tk.Button(poll_row, text="+Voto Opção B", bg="#e53935", fg="#fff", relief="flat", font=("Segoe UI", 8), command=lambda: self.vote_poll("B")).pack(side="left", padx=2)

        goal_row = tk.Frame(s_right, bg="#1c2331")
        goal_row.pack(fill="x", pady=2)
        tk.Label(goal_row, text="Meta (#34): atual", bg="#1c2331", fg="#cbd5e1", font=("Segoe UI", 8)).pack(side="left")
        tk.Spinbox(goal_row, from_=0, to=10_000_000, increment=10, textvariable=self.goal_current_var, width=8, bg="#0b0e14", fg="#fff", relief="flat").pack(side="left", padx=4)
        tk.Label(goal_row, text="de", bg="#1c2331", fg="#cbd5e1", font=("Segoe UI", 8)).pack(side="left")
        tk.Spinbox(goal_row, from_=1, to=10_000_000, increment=10, textvariable=self.goal_target_var, width=8, bg="#0b0e14", fg="#fff", relief="flat").pack(side="left", padx=4)

        eng_row = tk.Frame(s_right, bg="#1c2331")
        eng_row.pack(fill="x", pady=2)
        tk.Button(eng_row, text="🎯 Barra de Meta (#34)", bg="#252f42", fg="#00e676", relief="flat", font=("Segoe UI", 8, "bold"), command=self.toggle_goal).pack(side="left", fill="x", expand=True, padx=2)
        tk.Button(eng_row, text="🎉 Alerta Doação (#33)", bg="#ffb300", fg="#000", relief="flat", font=("Segoe UI", 8, "bold"), command=self.trigger_superchat).pack(side="left", fill="x", expand=True, padx=2)
        tk.Button(eng_row, text="🌤️ Clima (#36)", bg="#252f42", fg="#38bdf8", relief="flat", font=("Segoe UI", 8, "bold"), command=self.toggle_weather).pack(side="left", padx=2)

        weather_row = tk.Frame(s_right, bg="#1c2331")
        weather_row.pack(fill="x", pady=2)
        tk.Label(weather_row, text="Cidade do clima (#36):", bg="#1c2331", fg="#cbd5e1", font=("Segoe UI", 8)).pack(side="left")
        tk.Entry(weather_row, textvariable=self.weather_city, bg="#0b0e14", fg="#fff", relief="flat").pack(side="left", fill="x", expand=True, padx=4)

    def _populate_tab_auto(self, tab):
        a_left = tk.LabelFrame(tab, text=" 📡 TRANSMISSÃO DIRETA (RTMP), AGENDADOR (#28) E PROJETO (#45) ", font=("Segoe UI", 8, "bold"), fg="#38bdf8", bg="#1c2331", padx=8, pady=6)
        a_left.pack(side="left", fill="both", expand=True, padx=(0, 6))

        rtmp_row = tk.Frame(a_left, bg="#1c2331")
        rtmp_row.pack(fill="x", pady=2)
        tk.Label(rtmp_row, text="Servidor:", bg="#1c2331", fg="#cbd5e1", font=("Segoe UI", 8), width=8, anchor="w").pack(side="left")
        self.ent_rtmp = tk.Entry(rtmp_row, bg="#0b0e14", fg="#fff", relief="flat", font=("Consolas", 8))
        self.ent_rtmp.insert(0, "rtmp://a.rtmp.youtube.com/live2")
        self.ent_rtmp.pack(side="left", fill="x", expand=True)

        key_row = tk.Frame(a_left, bg="#1c2331")
        key_row.pack(fill="x", pady=2)
        tk.Label(key_row, text="Chave:", bg="#1c2331", fg="#cbd5e1", font=("Segoe UI", 8), width=8, anchor="w").pack(side="left")
        tk.Entry(key_row, textvariable=self.rtmp_key_var, show="•", bg="#0b0e14", fg="#fff", relief="flat", font=("Consolas", 8)).pack(side="left", fill="x", expand=True, padx=(0, 4))
        self.btn_rtmp = tk.Button(key_row, text="🚀 Iniciar Transmissão", bg="#ffb300", fg="#000", relief="flat", font=("Segoe UI", 8, "bold"), command=self.toggle_rtmp)
        self.btn_rtmp.pack(side="left")

        sched_row = tk.Frame(a_left, bg="#1c2331")
        sched_row.pack(fill="x", pady=4)
        tk.Label(sched_row, text="Trocar Cena às (HH:MM:SS) (#28):", bg="#1c2331", fg="#cbd5e1", font=("Segoe UI", 8)).pack(side="left")
        self.ent_sched_time = tk.Entry(sched_row, width=9, bg="#0b0e14", fg="#fff", relief="flat", font=("Consolas", 8))
        self.ent_sched_time.insert(0, "23:30:00")
        self.ent_sched_time.pack(side="left", padx=4)
        tk.Button(sched_row, text="⏰ Agendar Entrada", bg="#2979ff", fg="#fff", relief="flat", font=("Segoe UI", 8, "bold"), command=self.schedule_scene).pack(side="left")

        json_row = tk.Frame(a_left, bg="#1c2331")
        json_row.pack(fill="x", pady=4)
        tk.Button(json_row, text="💾 Salvar Projeto (.JSON) (#45)", bg="#252f42", fg="#fff", relief="flat", font=("Segoe UI", 8), command=self.export_json).pack(side="left", fill="x", expand=True, padx=(0, 4))
        tk.Button(json_row, text="📂 Abrir Projeto (.JSON) (#45)", bg="#252f42", fg="#fff", relief="flat", font=("Segoe UI", 8), command=self.import_json).pack(side="left", fill="x", expand=True)

        a_right = tk.LabelFrame(tab, text=" 📋 HISTÓRICO DE OPERAÇÃO E EXIBIÇÃO DE COMERCIAIS (#49) ", font=("Segoe UI", 8, "bold"), fg="#00e676", bg="#1c2331", padx=8, pady=6)
        a_right.pack(side="left", fill="both", expand=True)
        self.lst_logs = tk.Listbox(a_right, bg="#090c10", fg="#cbd5e1", font=("Consolas", 8), height=6, relief="flat")
        self.lst_logs.pack(fill="both", expand=True)

    # =========================================================================
    # COLUNA DIREITA: MESA DE SOM MULTI-PISTA (#11-#20) E PAINEL DE EFEITOS (#15)
    # =========================================================================
    def _build_right_column(self, parent):
        mixer_card = tk.LabelFrame(parent, text=" 🎚️ MESA DE SOM MULTI-PISTA (#11-#20) ", font=("Segoe UI", 9, "bold"), fg="#8b9bb4", bg="#131822", bd=1, relief="solid", padx=8, pady=8)
        mixer_card.pack(fill="both", expand=True, pady=(0, 8))

        tk.Label(
            mixer_card,
            text="⚠️ Áudio real ainda não implementado: os controles abaixo ainda não processam som e a transmissão sai em silêncio.",
            bg="#2a1f05", fg="#ffb300", font=("Segoe UI", 7, "bold"), wraplength=310, justify="left", padx=6, pady=4,
        ).pack(fill="x", pady=(0, 6))

        dsp_row = tk.Frame(mixer_card, bg="#131822")
        dsp_row.pack(fill="x", pady=(0, 6))
        tk.Checkbutton(dsp_row, text="🦆 Abaixar Trilha ao Falar (#14)", variable=self.ducking_enabled, bg="#131822", fg="#cbd5e1", selectcolor="#1c2331", font=("Segoe UI", 8)).pack(side="left")
        tk.Checkbutton(dsp_row, text="🗣️ Corte Automático p/ Voz (#23)", variable=self.auto_voice_switch, bg="#131822", fg="#cbd5e1", selectcolor="#1c2331", font=("Segoe UI", 8)).pack(side="right")

        self.vu_canvases = {}
        for ch in self.audio_channels:
            strip = tk.Frame(mixer_card, bg="#1c2331", highlightthickness=1, highlightbackground="#2b3548", padx=6, pady=5)
            strip.pack(fill="x", pady=3)

            hdr = tk.Frame(strip, bg="#1c2331")
            hdr.pack(fill="x")
            tk.Label(hdr, text=ch["name"], font=("Segoe UI", 8, "bold"), fg="#fff", bg="#1c2331").pack(side="left")

            btn_mute = tk.Button(hdr, text="🔊 ATIVO", bg="#252f42", fg="#00e676", relief="flat", font=("Segoe UI", 7, "bold"), width=8)
            btn_mute.configure(command=lambda c=ch, b=btn_mute: self.toggle_channel_mute(c, b))
            btn_mute.pack(side="right", padx=2)

            btn_pfl = tk.Button(hdr, text="🎧 ESCUTA", bg="#252f42", fg="#cbd5e1", relief="flat", font=("Segoe UI", 7, "bold"), width=8)
            btn_pfl.configure(command=lambda c=ch, b=btn_pfl: self.toggle_channel_pfl(c, b))
            btn_pfl.pack(side="right", padx=2)

            # Medidor de nível: fica vazio até existir captura de áudio real (nada de animação falsa)
            vu_cv = tk.Canvas(strip, height=8, bg="#090c10", highlightthickness=0)
            vu_cv.pack(fill="x", pady=4)
            self.vu_canvases[ch["id"]] = vu_cv

            f_row = tk.Frame(strip, bg="#1c2331")
            f_row.pack(fill="x")
            tk.Label(f_row, text="Volume:", font=("Segoe UI", 7), fg="#94a3b8", bg="#1c2331").pack(side="left")
            tk.Scale(f_row, from_=0, to=100, orient="horizontal", variable=ch["vol"], showvalue=False, bg="#1c2331", highlightthickness=0).pack(side="left", fill="x", expand=True, padx=4)

            pd_row = tk.Frame(strip, bg="#1c2331")
            pd_row.pack(fill="x")
            tk.Label(pd_row, text="Balanço E/D (#19):", font=("Segoe UI", 7), fg="#94a3b8", bg="#1c2331").pack(side="left")
            tk.Scale(pd_row, from_=-100, to=100, orient="horizontal", variable=ch["pan"], showvalue=False, bg="#1c2331", highlightthickness=0, length=65).pack(side="left", padx=4)
            tk.Label(pd_row, text="Atraso ms (#17):", font=("Segoe UI", 7), fg="#94a3b8", bg="#1c2331").pack(side="left")
            tk.Spinbox(pd_row, from_=0, to=900, textvariable=ch["delay"], width=4, bg="#0b0e14", fg="#fff", relief="flat", font=("Consolas", 8)).pack(side="right")

        sfx_card = tk.LabelFrame(parent, text=" 🔊 PAINEL DE EFEITOS SONOROS (#15) ", font=("Segoe UI", 9, "bold"), fg="#8b9bb4", bg="#131822", bd=1, relief="solid", padx=8, pady=8)
        sfx_card.pack(fill="x")

        sfx_grid = tk.Frame(sfx_card, bg="#131822")
        sfx_grid.pack(fill="x")
        for idx, (label, freq) in enumerate([("👏 Aplausos", 900), ("🎵 Vinheta de TV", 660), ("🔔 Alerta Urgente", 1200), ("⏱️ Sinal de Tempo", 880)]):
            b = tk.Button(sfx_grid, text=label, bg="#1c2331", fg="#38bdf8", relief="flat", font=("Segoe UI", 8, "bold"), pady=5, command=lambda l=label, f=freq: self.play_native_sfx(l, f))
            b.grid(row=idx // 2, column=idx % 2, sticky="ew", padx=3, pady=3)
        sfx_grid.columnconfigure(0, weight=1)
        sfx_grid.columnconfigure(1, weight=1)
        tk.Label(sfx_card, text="(por enquanto são bipes no alto-falante deste PC; não vão para a transmissão)", bg="#131822", fg="#64748b", font=("Segoe UI", 7)).pack(anchor="w", pady=(4, 0))

    # =========================================================================
    # EXIBIÇÃO DOS QUADROS REAIS (PRÉVIA, NO AR e Projetores) — o compositor roda em weblive_video.py
    # =========================================================================
    def _show_frame(self, cv: tk.Canvas, frame):
        if frame is None:
            return
        cw, ch = cv.winfo_width(), cv.winfo_height()
        if cw < 16 or ch < 16:
            return
        fh, fw = frame.shape[:2]
        s = min(cw / fw, ch / fh)
        dw, dh = max(1, int(fw * s)), max(1, int(fh * s))
        small = cv2.resize(frame, (dw, dh), interpolation=cv2.INTER_AREA if s < 1 else cv2.INTER_LINEAR)
        photo = ImageTk.PhotoImage(Image.fromarray(small))
        x0, y0 = (cw - dw) // 2, (ch - dh) // 2
        item = getattr(cv, "_wl_item", None)
        if item is None:
            cv._wl_item = cv.create_image(x0, y0, anchor="nw", image=photo)
        else:
            cv.coords(item, x0, y0)
            cv.itemconfigure(item, image=photo)
        cv._wl_photo = photo  # mantém a referência, senão o Tk descarta a imagem
        cv._wl_rect = (x0, y0, dw, dh)

    @staticmethod
    def _keep_16x9(cv: tk.Canvas, event):
        """Monitores sempre em 16:9 (sem faixas pretas) conforme a largura da coluna."""
        want = max(120, int(event.width * 9 / 16))
        if abs(event.height - want) > 2:
            cv.configure(height=want)

    def _draw_guides(self, cv: tk.Canvas):
        """Grade de Alinhamento (#47): só nos monitores do diretor, nunca na saída."""
        cv.delete("guide")
        if not self.snap_grid_enabled.get():
            return
        x0, y0, dw, dh = getattr(cv, "_wl_rect", (0, 0, cv.winfo_width(), cv.winfo_height()))
        for i in range(1, 4):
            x, y = x0 + dw * i // 4, y0 + dh * i // 4
            cv.create_line(x, y0, x, y0 + dh, fill="#2979ff", dash=(3, 3), tags="guide")
            cv.create_line(x0, y, x0 + dw, y, fill="#2979ff", dash=(3, 3), tags="guide")
        cv.create_rectangle(x0 + dw * 0.05, y0 + dh * 0.05, x0 + dw * 0.95, y0 + dh * 0.95, outline="#ffb300", dash=(2, 4), tags="guide")

    def _snapshot_state(self) -> dict:
        """Retrato do estado para o compositor (lido em outra thread: só tipos Python simples)."""
        return {
            "scenes": [dict(s) for s in self.scenes],
            "pgm_idx": self.pgm_idx,
            "pvw_idx": self.pvw_idx,
            "fade_from": self.fade_from_idx,
            "fade_start": self.fade_start,
            "stinger_start": self.stinger_start,
            "replay_token": self.replay_token,
            "chroma": bool(self.chroma_enabled.get()),
            "chroma_tol": _int_var(self.chroma_tol, 60),
            "pip_scale": _int_var(self.pip_scale, 28),
            "brightness": _int_var(self.brightness_var, 100),
            "contrast": _int_var(self.contrast_var, 100),
            "saturation": _int_var(self.saturation_var, 100),
            "crop_top": _int_var(self.crop_top_var, 0),
            "watermark": self.watermark_text.get(),
            "lt_visible": self.lt_visible,
            "lt_changed": self.lt_changed_at,
            "lt_title": self.lt_title.get(),
            "lt_sub": self.lt_sub.get(),
            "sb_visible": self.sb_visible,
            "sb_a": self.sb_team_a.get(),
            "sb_b": self.sb_team_b.get(),
            "sb_pa": _int_var(self.sb_pts_a),
            "sb_pb": _int_var(self.sb_pts_b),
            "sb_time": self.sb_timer_sec,
            "ticker_visible": self.ticker_visible,
            "ticker_text": self.ticker_text.get(),
            "qr_visible": self.qr_visible,
            "qr_url": self.qr_url.get().strip(),
            "poll_visible": self.poll_visible,
            "poll_a_label": self.poll_label_a.get() or "Opção A",
            "poll_b_label": self.poll_label_b.get() or "Opção B",
            "poll_a": self.poll_votes_a,
            "poll_b": self.poll_votes_b,
            "goal_visible": self.goal_visible,
            "goal_current": _int_var(self.goal_current_var),
            "goal_target": max(1, _int_var(self.goal_target_var, 1)),
            "featured_visible": self.featured_comment_visible,
            "featured_author": self.featured_author,
            "featured_text": self.featured_text,
            "weather_visible": self.weather_visible,
            "weather_text": self.weather_text,
            "countdown_visible": self.countdown_visible,
            "countdown_sec": self.countdown_sec,
            "alert_start": self.alert_start,
            "alert_user": self.alert_user,
            "alert_msg": self.alert_msg,
            "strokes": [(s["color"], tuple(s["points"])) for s in self.whiteboard_strokes],
        }

    # =========================================================================
    # AÇÕES E COMANDOS OPERACIONAIS (100% PORTUGUÊS-BR)
    # =========================================================================
    def _render_scene_buttons(self):
        for w in self.scenes_frame.winfo_children():
            w.destroy()
        self.scene_buttons.clear()

        for idx, sc in enumerate(self.scenes):
            is_pgm = idx == self.pgm_idx
            is_pvw = idx == self.pvw_idx
            bg = "#8e1b1b" if is_pgm else ("#0d4722" if is_pvw else "#1c2331")
            fg = "#ffffff" if (is_pgm or is_pvw) else "#cbd5e1"
            tag = "NO AR" if is_pgm else ("PRÉVIA" if is_pvw else f"[{sc['key']}]")
            btn = tk.Button(
                self.scenes_frame,
                text=f"{tag} • {sc['name']}",
                bg=bg,
                fg=fg,
                relief="flat",
                font=("Segoe UI", 8, "bold"),
                anchor="w",
                padx=6,
                pady=5,
                cursor="hand2",
                command=lambda i=idx: self.select_preview_scene(i),
            )
            btn.grid(row=idx // 2, column=idx % 2, sticky="ew", padx=3, pady=3)
            self.scene_buttons.append(btn)

        self.scenes_frame.columnconfigure(0, weight=1)
        self.scenes_frame.columnconfigure(1, weight=1)

    def _update_monitor_titles(self):
        self.lbl_pgm_title.configure(text=f"🔴 NO AR (PROGRAMA) • {self.scenes[self.pgm_idx]['name'].upper()}")
        self.lbl_pvw_title.configure(text=f"🟢 PRÉVIA (PREPARAÇÃO) • {self.scenes[self.pvw_idx]['name'].upper()}")

    def _load_scene_fields(self):
        """Os ajustes da aba Vídeo editam a cena em PRÉVIA: carrega os valores dela nos campos."""
        sc = self.scenes[self.pvw_idx]
        self._loading_scene_fields = True
        try:
            self.layout_mode_var.set(sc.get("layoutMode", LAYOUT_CHOICES[0]))
            self.bg_theme_var.set(sc.get("bgTheme", THEME_CHOICES[0]))
            self.main_source_var.set(SOURCE_NAME_BY_ID.get(sc.get("sourceType"), SOURCE_NAME_BY_ID["cam1"]))
            self.pip_source_var.set(SOURCE_NAME_BY_ID.get(sc.get("pipSource"), SOURCE_NAME_BY_ID["guest1"]))
        finally:
            self._loading_scene_fields = False

    def _bind_scene_field_traces(self):
        for var, key in ((self.layout_mode_var, "layoutMode"), (self.bg_theme_var, "bgTheme"), (self.main_source_var, "sourceType"), (self.pip_source_var, "pipSource")):
            var.trace_add("write", lambda *_a, v=var, k=key: self._on_scene_field_changed(k, v))

    def _on_scene_field_changed(self, key: str, var: tk.StringVar):
        if self._loading_scene_fields:
            return
        value = var.get()
        if key in ("sourceType", "pipSource"):
            value = SOURCE_ID_BY_NAME.get(value, value)
        self.scenes[self.pvw_idx][key] = value

    def select_preview_scene(self, idx: int):
        if not 0 <= idx < len(self.scenes):
            return
        self.pvw_idx = idx
        self._render_scene_buttons()
        self._update_monitor_titles()
        self._load_scene_fields()

    def execute_transition(self, mode: str = "CORTE SECO"):
        if self.scene_locked.get():
            messagebox.showwarning("Cena Travada (#44)", "Desmarque '🔒 Travar Cena (#44)' antes de trocar a cena que está no ar.")
            return
        if self._transition_pending:
            return

        if mode == "VINHETA":
            # A vinheta cobre a tela inteira no meio do efeito: a cena troca nesse instante
            self.stinger_start = time.time()
            self._transition_pending = True
            self.play_native_sfx("Vinheta de Transição", 660)
            HUB.broadcast({"type": "TRIGGER_STINGER", "data": {"durationMs": int(STINGER_SECONDS * 1000)}})
            self.root.after(int(STINGER_SECONDS * 500), lambda: self._swap_program(mode))
            return
        if mode == "SUAVE":
            self.fade_from_idx = self.pgm_idx
            self.fade_start = time.time()
        self._swap_program(mode)

    def _swap_program(self, mode: str):
        self._transition_pending = False
        self.pgm_idx, self.pvw_idx = self.pvw_idx, self.pgm_idx
        pgm_sc = self.scenes[self.pgm_idx]
        pvw_sc = self.scenes[self.pvw_idx]
        self._render_scene_buttons()
        self._update_monitor_titles()
        self._load_scene_fields()

        tally = "PGM" if pgm_sc["sourceType"] == "guest1" else ("PVW" if pvw_sc["sourceType"] == "guest1" else "IDLE")
        HUB.broadcast({"type": "TALLY_UPDATE", "data": {"guestId": "Reporter1", "tally": tally}})
        self.log_action(f"Transição [{mode}] -> ENTROU NO AR: {pgm_sc['name']}")

    def open_native_projector(self, clean_feed: bool = False):
        proj = NativeProjectorWindow(self.root, self, clean_feed=clean_feed)
        self.projectors.append(proj)
        mode_str = "Saída Limpa sem Gráficos (#43)" if clean_feed else "Saída Principal (Para Captura de Janela no OBS)"
        self.log_action(f"Projetor Nativo aberto: {mode_str}")

    def add_custom_scene(self):
        name = simpledialog.askstring("Nova Cena", "Digite o nome da nova cena:", parent=self.root)
        if not name:
            return
        idx = len(self.scenes) + 1
        self.scenes.append({"id": f"scene_{idx}", "key": str(idx), "name": name, "subtitle": "Cena Personalizada", "sourceType": "cam1", "pipSource": "guest1", "layoutMode": LAYOUT_CHOICES[0], "bgTheme": THEME_CHOICES[0]})
        self._render_scene_buttons()
        self.log_action(f"Nova cena criada: {name}")

    def trigger_instant_replay(self):
        self.replay_token += 1
        self.log_action("⏪ Replay Imediato (#8): últimos 5 segundos do programa em câmera lenta no ar")

    def _wb_point(self, event):
        """Converte o clique para coordenadas 0-1 da imagem exibida (descontando as bordas pretas)."""
        x0, y0, dw, dh = getattr(self.pgm_canvas, "_wl_rect", (0, 0, max(1, self.pgm_canvas.winfo_width()), max(1, self.pgm_canvas.winfo_height())))
        return (min(1.0, max(0.0, (event.x - x0) / max(1, dw))), min(1.0, max(0.0, (event.y - y0) / max(1, dh))))

    def _wb_start(self, event):
        if not self.whiteboard_enabled.get():
            return
        self.current_stroke = {"color": self.whiteboard_color, "points": [self._wb_point(event)]}
        self.whiteboard_strokes.append(self.current_stroke)

    def _wb_draw(self, event):
        if not self.whiteboard_enabled.get() or not self.current_stroke:
            return
        self.current_stroke["points"].append(self._wb_point(event))

    def _wb_end(self, event):
        self.current_stroke = None

    def pick_whiteboard_color(self):
        col = colorchooser.askcolor(initialcolor=self.whiteboard_color, title="Escolher Cor do Pincel", parent=self.root)[1]
        if col:
            self.whiteboard_color = col

    def clear_whiteboard(self):
        self.whiteboard_strokes.clear()
        self.log_action("Desenhos da tela (#40) apagados")

    def toggle_lower_third(self):
        self._set_lower_third(not self.lt_visible)
        mode = self.lt_mode.get()
        if self.lt_visible and "Temporária" in mode:
            ms = 5000 if "5" in mode else 8000
            self._lt_token += 1
            self.root.after(ms, lambda tok=self._lt_token: self._auto_hide_lower_third(tok))
        self.log_action(f"Tarjeta de Identificação (#5): {'NO AR' if self.lt_visible else 'OCULTA'} ({self.lt_title.get()})")

    def _set_lower_third(self, visible: bool):
        self.lt_visible = visible
        self.lt_changed_at = time.time()  # o compositor anima a entrada/saída a partir deste instante

    def _auto_hide_lower_third(self, token: int):
        if token == self._lt_token and self.lt_visible:
            self._set_lower_third(False)

    def toggle_scoreboard(self):
        self.sb_visible = not self.sb_visible
        self.log_action(f"Placar Esportivo (#4): {'NO AR' if self.sb_visible else 'OCULTO'}")

    def toggle_sb_timer(self):
        self.sb_timer_running = not self.sb_timer_running

    def reset_sb_timer(self):
        self.sb_timer_sec = 0

    def toggle_ticker(self):
        self.ticker_visible = not self.ticker_visible

    def fetch_rss_to_ticker(self):
        url = self.rss_url_var.get().strip() or DEFAULT_RSS_URL
        self.log_action(f"📡 Buscando manchetes reais (#37): {url}")

        def worker():
            try:
                headlines = fetch_rss_headlines(url)
            except Exception as exc:
                self._ui(lambda e=exc: self._rss_failed(url, e))
                return
            self._ui(lambda: self._rss_ok(headlines))

        threading.Thread(target=worker, daemon=True).start()

    def _rss_ok(self, headlines):
        self.ticker_text.set(" • ".join(headlines))
        self.ticker_visible = True
        self.log_action(f"✅ {len(headlines)} manchetes reais (#37) na barra de notícias")

    def _rss_failed(self, url, exc):
        self.log_action(f"❌ Feed de notícias indisponível (#37): {exc}")
        messagebox.showerror("Notícias indisponíveis", f"Não foi possível ler o feed:\n{url}\n\n{exc}")

    def trigger_featured_comment(self):
        author = self.ent_chat_user.get().strip() or "@Espectador"
        msg = self.ent_chat_msg.get().strip()
        if self.profanity_filter.get():
            for bad in ("palavrao", "idiota", "burro", "spam"):
                msg = msg.replace(bad, "****")
        self.featured_author = author
        self.featured_text = msg
        self.featured_comment_visible = not self.featured_comment_visible
        self.log_action(f"Comentário em Destaque (#35): {author}")

    def toggle_qr(self):
        self.qr_visible = not self.qr_visible
        self.log_action(f"Código QR Ao Vivo (#9): {'NO AR' if self.qr_visible else 'OCULTO'}")

    def toggle_poll(self):
        self.poll_visible = not self.poll_visible

    def vote_poll(self, side: str):
        if side == "A":
            self.poll_votes_a += 1
        else:
            self.poll_votes_b += 1

    def reset_poll(self):
        self.poll_votes_a = self.poll_votes_b = 0
        self.log_action("Votos da enquete (#32) zerados")

    def toggle_goal(self):
        self.goal_visible = not self.goal_visible

    def trigger_superchat(self):
        user = self.ent_chat_user.get().strip() or "Apoiador"
        self._show_alert(user, self.ent_chat_msg.get().strip())
        self.log_action(f"🎉 Alerta de Doação / Superchat (#33) exibido no ar: {user}")

    def _show_alert(self, user: str, msg: str):
        self.alert_user, self.alert_msg = user, msg
        self.alert_start = time.time()
        self.play_native_sfx("Alerta de Doação", 1046)

    def toggle_weather(self):
        if self.weather_visible:
            self.weather_visible = False
            self.log_action("Previsão do Tempo (#36): OCULTA")
            return
        self._fetch_weather(show=True)

    def _fetch_weather(self, show: bool):
        city = self.weather_city.get().strip() or "São Paulo"
        self.weather_fetched_at = time.time()

        def worker():
            try:
                text = fetch_weather(city)
            except Exception as exc:
                self._ui(lambda e=exc: self._weather_failed(city, e, show))
                return
            self._ui(lambda: self._weather_ok(text, show))

        threading.Thread(target=worker, daemon=True).start()

    def _weather_ok(self, text: str, show: bool):
        self.weather_text = text
        if show:
            self.weather_visible = True
            self.log_action(f"🌤️ Previsão do Tempo (#36) no ar: {text}")

    def _weather_failed(self, city: str, exc, show: bool):
        self.log_action(f"❌ Clima indisponível para {city} (#36): {exc}")
        if show:
            messagebox.showerror("Clima indisponível", f"Não foi possível obter o clima de {city}.\n\n{exc}")

    def toggle_countdown(self):
        self.countdown_visible = not self.countdown_visible
        if self.countdown_visible and self.countdown_sec <= 0:
            self.countdown_sec = 180
        self.log_action(f"Contagem Regressiva (#25): {'NO AR' if self.countdown_visible else 'OCULTA'}")

    # Gravação de Segurança Real (#27)
    def toggle_backup_recording(self):
        if self.recorder.active:
            path = self.recorder.target
            self.btn_record.configure(text="⏳ Finalizando arquivo...", state="disabled")

            def worker():
                self.recorder.stop()
                self._ui(lambda: self._recording_stopped(path))

            threading.Thread(target=worker, daemon=True).start()
            return

        path = RECORDINGS_DIR / time.strftime("WebLive_%Y-%m-%d_%H-%M-%S.mkv")
        res = self.recorder.start(str(path))
        if not res["ok"]:
            messagebox.showerror("Gravação não iniciada", res["message"])
            return
        self.btn_record.configure(text="⏹️ Parar Gravação (#27)", bg="#e53935")
        self.log_action(f"⏺️ Gravação de segurança (#27) iniciada: {path.name}")

    def _recording_stopped(self, path: str):
        self.btn_record.configure(text="⏺️ Gravar Cópia Local (#27)", bg="#252f42", state="normal")
        size = os.path.getsize(path) if os.path.isfile(path) else 0
        self.log_action(f"💾 Gravação salva: {os.path.basename(path)} ({size / 1e6:.1f} MB) em {RECORDINGS_DIR}")

    def open_recordings_folder(self):
        RECORDINGS_DIR.mkdir(exist_ok=True)
        try:
            os.startfile(str(RECORDINGS_DIR))
        except (AttributeError, OSError) as exc:
            messagebox.showinfo("Pasta das Gravações", f"{RECORDINGS_DIR}\n\n({exc})")

    def toggle_panic_mute(self):
        self.panic_muted = not self.panic_muted
        self.btn_panic.configure(
            text="🚨 SOM CORTADO (REATIVAR)" if self.panic_muted else "🔇 SILENCIAR TUDO (#20)",
            bg="#ffb300" if self.panic_muted else "#e53935",
            fg="#000" if self.panic_muted else "#fff",
        )
        self.log_action(f"SILENCIAR DE EMERGÊNCIA (#20): {'ATIVADO' if self.panic_muted else 'DESATIVADO'}")

    def toggle_channel_mute(self, ch: dict, btn: tk.Button):
        ch["muted"] = not ch["muted"]
        btn.configure(text="🔇 MUDO" if ch["muted"] else "🔊 ATIVO", fg="#ff5252" if ch["muted"] else "#00e676")

    def toggle_channel_pfl(self, ch: dict, btn: tk.Button):
        ch["pfl"] = not ch["pfl"]
        btn.configure(bg="#ffb300" if ch["pfl"] else "#252f42", fg="#000" if ch["pfl"] else "#cbd5e1")
        self.log_action(f"Escuta Prévia no Fone (#18) em {ch['name']}: {'LIGADA' if ch['pfl'] else 'DESLIGADA'}")

    def play_native_sfx(self, label: str, freq: int):
        def beep():
            try:
                import winsound
                winsound.Beep(freq, 180)
            except Exception:
                pass
        threading.Thread(target=beep, daemon=True).start()
        self.log_action(f"Efeito Sonoro (#15): {label}")

    def set_talkback(self, active: bool):
        self.talkback_active = active
        self.btn_talkback.configure(
            text="🔴 FALANDO NO FONE DO REPÓRTER (FORA DO AR)" if active else "🎙️ SEGURE PARA FALAR COM O REPÓRTER (#16)",
            bg="#e53935" if active else "#ffb300",
            fg="#fff" if active else "#000",
        )
        HUB.broadcast({"type": "TALKBACK_STATUS", "data": {"active": active}})

    # Teste de Internet Real (#41)
    def run_native_speedtest(self):
        if self._speedtest_running:
            return
        self._speedtest_running = True
        self.lbl_rtc_info.configure(text="📶 Testando a internet (#41)... aguarde uns 15 segundos", fg="#ffb300")

        def worker():
            try:
                result = run_speedtest()
            except Exception as exc:
                self._ui(lambda e=exc: self._speedtest_done(None, str(e)))
                return
            self._ui(lambda: self._speedtest_done(result, ""))

        threading.Thread(target=worker, daemon=True).start()

    def _speedtest_done(self, r, err: str):
        self._speedtest_running = False
        if err:
            self.lbl_rtc_info.configure(text=f"❌ Teste de internet falhou: {err[:90]}", fg="#ff5252")
            self.log_action(f"Teste de Velocidade (#41) falhou: {err}")
            return
        ok = r["upload_mbps"] >= 6.0
        verdict = "envio suficiente p/ 720p30" if ok else "envio baixo p/ 720p30 (recomendado: 6 Mbps)"
        txt = f"📶 Baixar {r['download_mbps']:.1f} Mbps • Enviar {r['upload_mbps']:.1f} Mbps • {r['ping_ms']:.0f} ms — {verdict}"
        self.lbl_rtc_info.configure(text=txt, fg="#00e676" if ok else "#ffb300")
        self.log_action(f"Teste de Velocidade (#41): {txt[2:]}")

    # Mídia: arquivo do computador ou link (yt-dlp) no canal MÍDIA
    def _refresh_playlist_box(self):
        self.lst_playlist.delete(0, tk.END)
        for i, url in enumerate(self.playlist, 1):
            self.lst_playlist.insert(tk.END, f"{i}. {url}")

    def add_to_playlist(self):
        u = self.ent_media_url.get().strip()
        if u:
            self.playlist.append(u)
            self._refresh_playlist_box()
            self.log_action(f"Vídeo adicionado à Fila (#22): {u}")

    def next_playlist_item(self):
        if self.playlist:
            nxt = self.playlist.pop(0)
            self.playlist.append(nxt)
            self.ent_media_url.delete(0, tk.END)
            self.ent_media_url.insert(0, nxt)
            self._refresh_playlist_box()
            self.log_action(f"Fila de Vídeos (#22) avançou para: {nxt}")
            self._load_media(nxt)

    def extract_ytdlp_native(self):
        url = self.ent_media_url.get().strip()
        if url:
            self._load_media(url)

    def open_media_file(self):
        path = filedialog.askopenfilename(title="Abrir Vídeo do Computador", filetypes=VIDEO_FILETYPES, parent=self.root)
        if path:
            self.ent_media_url.delete(0, tk.END)
            self.ent_media_url.insert(0, path)
            self._load_media(path)

    def _load_media(self, target: str):
        is_file = os.path.isfile(target)
        loop = not self.media_autoadvance.get()
        self.lbl_media_status.configure(text=f"⏳ Carregando: {target[:70]}", fg="#ffb300")
        self.log_action(f"🎞️ Carregando vídeo no canal MÍDIA: {target}")

        def worker():
            url, title = target, os.path.basename(target)
            if not is_file:
                res = YtDlpMediaResolver.resolve_url(target, YTDLP_FORMAT_DESKTOP)
                if not res.get("ok"):
                    err = res.get("error", "erro desconhecido")
                    self._ui(lambda: self._media_failed(target, err))
                    return
                url, title = res["direct_url"], res.get("title") or target
            src = MediaSource(url, title, loop=loop).start()
            old = self.sources.get("media1")
            self.sources["media1"] = src
            if old:
                old.stop()
            self._ui(lambda: self._media_loaded(title))

        threading.Thread(target=worker, daemon=True).start()

    def _media_loaded(self, title: str):
        self.btn_media_pause.configure(text="⏸ Pausar")
        self.log_action(f"✅ Vídeo no canal MÍDIA: {title[:70]} (sem áudio por enquanto)")

    def _media_failed(self, target: str, err: str):
        self.lbl_media_status.configure(text="❌ Não foi possível carregar o vídeo", fg="#ff5252")
        self.log_action(f"❌ Falha ao carregar vídeo: {err[:160]}")
        messagebox.showerror("Não foi possível carregar o vídeo", f"{target}\n\n{err[:600]}")

    def toggle_media_pause(self):
        src = self.sources.get("media1")
        if not src:
            messagebox.showinfo("Mídia", "Nenhum vídeo carregado no canal MÍDIA.")
            return
        src.paused = not src.paused
        self.btn_media_pause.configure(text="▶ Continuar" if src.paused else "⏸ Pausar")
        self.log_action(f"Mídia {'PAUSADA' if src.paused else 'REPRODUZINDO'}: {src.title[:60]}")

    # Câmeras reais
    def _camera_choices(self):
        names = self.camera_names or [f"Câmera {i}" for i in range(4)]
        return [f"{i} • {n}" for i, n in enumerate(names)]

    @staticmethod
    def _parse_cam_index(value):
        try:
            return int(str(value).split("•")[0].strip())
        except ValueError:
            return None

    def _refresh_camera_list(self):
        def worker():
            names = list_video_devices()
            self._ui(lambda: self._apply_camera_list(names))

        threading.Thread(target=worker, daemon=True).start()

    def _apply_camera_list(self, names):
        self.camera_names = names
        choices = self._camera_choices()
        self.cam_combos["cam1"]["values"] = choices
        self.cam_combos["cam2"]["values"] = [CAM_OFF] + choices
        for slot in CAMERA_SLOTS:
            src = self.sources.get(slot)
            if src is not None and src.index < len(names):
                src.name = names[src.index]
            self._sync_camera_var(slot)
        if names:
            self.log_action(f"📷 {len(names)} câmera(s) encontrada(s): {', '.join(names)}")
        else:
            self.log_action("📷 Lista de câmeras indisponível (FFmpeg ausente): usando os dispositivos 0 a 3")

    def _sync_camera_var(self, slot: str):
        src = self.sources.get(slot)
        if src is None:
            self.cam_vars[slot].set(CAM_OFF)
            return
        choices = self._camera_choices()
        self.cam_vars[slot].set(choices[src.index] if src.index < len(choices) else f"{src.index} • Câmera {src.index}")

    def _on_camera_selected(self, slot: str):
        value = self.cam_vars[slot].get()
        idx = None if value == CAM_OFF else self._parse_cam_index(value)
        other = "cam2" if slot == "cam1" else "cam1"
        other_src = self.sources.get(other)
        if idx is not None and other_src is not None and other_src.index == idx:
            messagebox.showwarning("Câmera já em uso", f"Este dispositivo já está na {SOURCE_NAME_BY_ID[other]}. Escolha outro.")
            self._sync_camera_var(slot)
            return
        self._set_camera(slot, idx)

    def _set_camera(self, slot: str, idx):
        old = self.sources.get(slot)
        if old is not None and old.index == idx:
            return
        self.sources[slot] = None
        if old is not None:
            threading.Thread(target=old.stop, daemon=True).start()
        if idx is None:
            self.log_action(f"📷 {SOURCE_NAME_BY_ID[slot]} desligada")
            return
        name = self.camera_names[idx] if idx < len(self.camera_names) else f"Câmera {idx}"
        self.sources[slot] = CameraSource(idx, name).start()
        self.log_action(f"📷 {SOURCE_NAME_BY_ID[slot]} ligada no dispositivo {idx}: {name}")

    # Transmissão RTMP Real do Programa
    def toggle_rtmp(self):
        if RTMP_ENGINE.is_streaming:
            self.btn_rtmp.configure(text="⏳ Encerrando...", state="disabled")

            def worker():
                RTMP_ENGINE.stop_stream()
                self._ui(self._rtmp_stopped)

            threading.Thread(target=worker, daemon=True).start()
            return

        url = self.ent_rtmp.get().strip()
        res = RTMP_ENGINE.start_stream(url, self.rtmp_key_var.get())
        if not res.get("ok"):
            messagebox.showerror("Transmissão não iniciada", res.get("message", "Erro desconhecido"))
            return
        self._rtmp_ui_live = True
        self.btn_rtmp.configure(text="⏹️ Parar Transmissão (NO AR)", bg="#e53935", fg="#fff")
        HUB.broadcast({"type": "RTMP_STATUS", "data": RTMP_ENGINE.status()})
        self.log_action(f"📡 Transmissão iniciada para {url} (programa real 1280x720 @ 30fps, áudio em silêncio)")

    def _rtmp_stopped(self, reason: str = ""):
        self._rtmp_ui_live = False
        self.btn_rtmp.configure(text="🚀 Iniciar Transmissão", bg="#ffb300", fg="#000", state="normal")
        HUB.broadcast({"type": "RTMP_STATUS", "data": RTMP_ENGINE.status()})
        self.log_action(reason or "⏹️ Transmissão Externa encerrada")

    def schedule_scene(self):
        t_str = self.ent_sched_time.get().strip()
        if t_str:
            self.scheduled_events.append({"time": t_str, "scene_idx": self.pvw_idx, "done": False})
            self.log_action(f"⏰ Cena '{self.scenes[self.pvw_idx]['name']}' agendada para {t_str} (#28)")

    def export_json(self):
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("Arquivo de Projeto JSON", "*.json")], title="Salvar Projeto Como", parent=self.root)
        if path:
            data = {"scenes": self.scenes, "lt_title": self.lt_title.get(), "lt_sub": self.lt_sub.get(), "ticker": self.ticker_text.get()}
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.log_action(f"💾 Projeto salvo em JSON (#45): {os.path.basename(path)}")

    def import_json(self):
        path = filedialog.askopenfilename(filetypes=[("Arquivo de Projeto JSON", "*.json")], title="Abrir Projeto Salvo", parent=self.root)
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError) as exc:
            messagebox.showerror("Projeto inválido", f"Não foi possível abrir o projeto:\n{exc}")
            return
        scenes = [_normalize_scene(s) for s in data.get("scenes", []) if isinstance(s, dict)]
        if scenes:
            self.scenes = scenes
            self.pgm_idx = 0
            self.pvw_idx = 1 if len(scenes) > 1 else 0
            self._render_scene_buttons()
            self._update_monitor_titles()
            self._load_scene_fields()
        for key, var in (("lt_title", self.lt_title), ("lt_sub", self.lt_sub), ("ticker", self.ticker_text)):
            if isinstance(data.get(key), str):
                var.set(data[key])
        self.log_action(f"📂 Projeto JSON carregado (#45): {os.path.basename(path)}")

    def _copy_text(self, txt: str):
        self.root.clipboard_clear()
        self.root.clipboard_append(txt)
        self.log_action(f"Copiado para a área de transferência: {txt}")

    def log_action(self, msg: str):
        DB.add_audit_log(msg, "ESTUDIO")
        ts = time.strftime("%H:%M:%S")
        if hasattr(self, "lst_logs"):
            self.lst_logs.insert(0, f"[{ts}] {msg}")

    def _bind_keyboard_shortcuts(self):
        typing = (tk.Entry, tk.Spinbox, ttk.Entry)  # não troca de cena enquanto o operador digita
        self.root.bind("<space>", lambda e: self.execute_transition("CORTE SECO") if not isinstance(e.widget, typing) else None)
        for i in range(1, 7):
            self.root.bind(str(i), lambda e, idx=i - 1: self.select_preview_scene(idx) if not isinstance(e.widget, typing) else None)

    # =========================================================================
    # COMUNICAÇÃO ENTRE THREADS, API DO SERVIDOR E LAÇOS DE ATUALIZAÇÃO
    # =========================================================================
    def _ui(self, fn):
        """Agenda `fn` na thread da interface (threads de trabalho nunca tocam no Tk)."""
        self._ui_queue.put(fn)

    def _drain_ui_queue(self):
        while True:
            try:
                fn = self._ui_queue.get_nowait()
            except queue.Empty:
                return
            try:
                fn()
            except Exception as exc:
                self.log_action(f"⚠️ Erro interno: {exc}")

    def _drain_hub_events(self):
        """Alertas do webhook (#33) e comandos do Stream Deck (#46) recebidos pelo servidor."""
        for _ in range(50):
            try:
                raw = self._hub_queue.get_nowait()
            except queue.Empty:
                return
            try:
                msg = json.loads(raw.decode("utf-8").removeprefix("data: ").strip())
            except (ValueError, UnicodeDecodeError):
                continue
            if msg.get("type") == "WEBHOOK_ALERT":
                user = str(msg.get("user") or "Apoiador")
                amount = str(msg.get("amount") or "")
                self._show_alert(f"{user} • {amount}" if amount else user, str(msg.get("message") or msg.get("msg") or ""))
                self.log_action(f"🎉 Alerta de doação recebido pela API (#33): {user} {amount}")
            elif msg.get("type") == "STREAMDECK_COMMAND":
                self._handle_streamdeck(str(msg.get("action", "")).lower(), str(msg.get("target", "")))

    def _handle_streamdeck(self, action: str, target: str):
        actions = {
            "cut": lambda: self.execute_transition("CORTE SECO"),
            "auto": lambda: self.execute_transition("SUAVE"),
            "stinger": lambda: self.execute_transition("VINHETA"),
            "replay": self.trigger_instant_replay,
            "gc": self.toggle_lower_third,
            "placar": self.toggle_scoreboard,
            "ticker": self.toggle_ticker,
            "gravar": self.toggle_backup_recording,
        }
        if action in ("scene", "preview"):
            try:
                idx = int(target) - 1
            except ValueError:
                idx = -1
            if not 0 <= idx < len(self.scenes):
                self.log_action(f"Stream Deck API (#46): cena inválida '{target}'")
                return
            self.select_preview_scene(idx)
            if action == "scene":
                self.execute_transition("CORTE SECO")
        elif action in actions:
            actions[action]()
        else:
            self.log_action(f"Stream Deck API (#46): ação desconhecida '{action}'")
            return
        self.log_action(f"Stream Deck API (#46) executou: {action} {target}".strip())

    def _start_render_loop(self):
        def frame_tick():
            try:
                self.frame_counter += 1
                self._drain_ui_queue()
                self._drain_hub_events()
                self.compositor.state = self._snapshot_state()

                self._show_frame(self.pvw_canvas, self.compositor.latest_pvw)
                self._show_frame(self.pgm_canvas, self.compositor.latest_pgm)
                self._draw_guides(self.pvw_canvas)
                self._draw_guides(self.pgm_canvas)

                alive_projs = []
                for proj in self.projectors:
                    if proj.winfo_exists():
                        self._show_frame(proj.canvas, self.compositor.latest_clean if proj.clean_feed else self.compositor.latest_pgm)
                        alive_projs.append(proj)
                self.projectors = alive_projs
            finally:
                self.root.after(33, frame_tick)

        self.root.after(50, frame_tick)

    def _update_status_labels(self):
        for slot in CAMERA_SLOTS:
            src = self.sources.get(slot)
            text = f"{src.status}" if src else "desligada"
            color = "#00e676" if src and src.status.startswith("ao vivo") else ("#64748b" if not src else "#ffb300")
            self.cam_status_labels[slot].configure(text=text, fg=color)

        media = self.sources.get("media1")
        if media:
            color = "#ff5252" if media.status.startswith("erro") else ("#00e676" if media.status.startswith("reproduzindo") else "#ffb300")
            self.lbl_media_status.configure(text=f"{media.status} • {media.title[:60]}", fg=color)

        now_cpu, now_wall = time.process_time(), time.perf_counter()
        cpu = (now_cpu - self._cpu_last[0]) / max(1e-6, now_wall - self._cpu_last[1]) / (os.cpu_count() or 1) * 100
        self._cpu_last = (now_cpu, now_wall)
        parts = [f"⚡ Saída {self.compositor.fps:.0f} QPS", f"Processador {cpu:.0f}%"]
        if self.recorder.active:
            m, s = divmod(self.recorder.uptime, 60)
            parts.append(f"⏺ GRAVANDO {m:02d}:{s:02d}")
        if RTMP_ENGINE.is_streaming:
            m, s = divmod(RTMP_ENGINE.output.uptime, 60)
            parts.append(f"📡 AO VIVO {m:02d}:{s:02d}")
        self.lbl_health.configure(text=" • ".join(parts), fg="#ff5252" if RTMP_ENGINE.is_streaming or self.recorder.active else "#00e676")

        err = self.compositor.last_error
        if err and err != self._last_comp_error:
            self.log_action(f"⚠️ Erro no compositor de vídeo: {err}")
        self._last_comp_error = err

    def _check_outputs(self):
        err = self.recorder.check()
        if err:
            self.btn_record.configure(text="⏺️ Gravar Cópia Local (#27)", bg="#252f42", state="normal")
            self.log_action(f"❌ Gravação interrompida: {err[:200]}")
            messagebox.showerror("Gravação interrompida", err)

        err = RTMP_ENGINE.check()
        if err:
            self._rtmp_stopped(f"❌ Transmissão interrompida: {err[:200]}")
            messagebox.showerror("Transmissão interrompida", err)
        elif self._rtmp_ui_live != RTMP_ENGINE.is_streaming and str(self.btn_rtmp.cget("state")) == "normal":
            # Iniciada ou parada pela API web (/api/rtmp/*): sincroniza o botão
            if RTMP_ENGINE.is_streaming:
                self._rtmp_ui_live = True
                self.btn_rtmp.configure(text="⏹️ Parar Transmissão (NO AR)", bg="#e53935", fg="#fff")
            else:
                self._rtmp_stopped()

    def _check_media_end(self):
        media = self.sources.get("media1")
        if media is None:
            return
        media.loop = not self.media_autoadvance.get()
        if media.ended and self.media_autoadvance.get() and self.playlist:
            media.ended = False
            self.next_playlist_item()

    def _start_1s_timer(self):
        def sec_tick():
            try:
                now_str = time.strftime("%H:%M:%S")
                self.lbl_clock.configure(text=f"🕒 {now_str} (Brasília)")

                if self.sb_timer_running:
                    self.sb_timer_sec += 1
                if self.countdown_visible and self.countdown_sec > 0:
                    self.countdown_sec -= 1

                for ev in self.scheduled_events:
                    if not ev["done"] and ev["time"] == now_str:
                        ev["done"] = True
                        self.select_preview_scene(ev["scene_idx"])
                        self.execute_transition("VINHETA")

                if self.weather_visible and time.time() - self.weather_fetched_at > WEATHER_REFRESH_SECONDS:
                    self._fetch_weather(show=False)

                self._update_status_labels()
                self._check_outputs()
                self._check_media_end()
            finally:
                self.root.after(1000, sec_tick)

        self.root.after(1000, sec_tick)

    def _on_close(self):
        if self.recorder.active or RTMP_ENGINE.is_streaming:
            if not messagebox.askyesno("Encerrar o WebLive Studio", "Há uma gravação ou transmissão em andamento.\nEncerrar mesmo assim? (a gravação será finalizada e salva)"):
                return
        try:
            RTMP_ENGINE.stop_stream()
            self.recorder.stop()
            self.compositor.stop()
            for src in list(self.sources.values()):
                if src:
                    src.stop()
            self.server.stop()
        except Exception:
            pass
        self.root.destroy()
        sys.exit(0)


def main():
    root = tk.Tk()
    WebLiveNativeStudioApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
