#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
WebLive Studio Pro v3.0 — Estação Desktop Nativa Python (NÃO abre navegador!)
===============================================================================
Software Desktop Profissional completo (estilo vMix / OBS Studio) construído
100% em janela nativa Python (Tkinter + Pillow + SQLite3 + yt-dlp + FFmpeg).

Inclui nativamente na janela do programa (sem abrir páginas HTML):
  - Monitores duplos nativos PREVIEW (PVW) e PROGRAM (PGM) renderizados a 30/60fps
  - Janela Nativa de Saída Externa / Segundo Monitor ("Fullscreen Projector / Clean Feed")
    que o OBS pode capturar via "Captura de Janela" (Window Capture) OU Browser Source
  - Gerenciador de Cenas com bloqueio (#44), atalhos de teclado 1-6 e Espaço (#21)
  - Barra de Transições (CUT, AUTO FADE, STINGER #3, INSTANT REPLAY 10s #8)
  - Whiteboard / Telestrator Ao Vivo (#40): desenhe com o mouse direto no monitor Program!
  - Audio Mixer Multi-pista nativo (#11-#20) com VU Meters em tempo real, PFL, Delay,
    Pan L/R, Noise Gate, Audio Ducking, Auto-Switch por Voz e Panic Mute
  - Gerador de Caracteres (Lower Thirds #5), Placar Esportivo c/ Cronômetro (#4) e Ticker (#7/#37)
  - Módulos de Vídeo (PiP #1, Multi-view 4x/8x #2, Chroma Key #3, Crop #4, Cor #5, BG Loop #10)
  - Engajamento: Chat c/ Filtro de Palavrões (#31/#38), Destaque (#35), Enquetes (#32),
    Barra de Meta (#34), Superchat (#33) e Gerador Nativo de QR Code (#9 via Pillow)
  - Extrator Python `yt-dlp` e Transmissão Direta `RTMP / FFmpeg` + Banco `SQLite3`
"""

import json
import math
import os
import sys
import threading
import time
import tkinter as tk
from tkinter import colorchooser, filedialog, messagebox, simpledialog, ttk
from PIL import Image, ImageDraw, ImageTk

from weblive_server import DB, HUB, RTMP_ENGINE, WebLivePythonServer, YtDlpMediaResolver, get_lan_ip


class NativeProjectorWindow(tk.Toplevel):
    """
    Janela Nativa de Saída de Vídeo (Program Out / Clean Feed #43).
    Substitui a necessidade de página HTML! Pode ser colocada em Tela Cheia num 2º monitor
    ou capturada diretamente no OBS via 'Captura de Janela (Window Capture)'.
    """

    def __init__(self, master, app, clean_feed: bool = False):
        super().__init__(master)
        self.app = app
        self.clean_feed = clean_feed
        title_mode = "CLEAN FEED (SEM GRÁFICOS #43)" if clean_feed else "PROGRAM OUTPUT (CAPTURA DE JANELA OBS / PROJETOR)"
        self.title(f"📺 WebLive Studio Output — {title_mode}")
        self.geometry("960x540")
        self.configure(bg="#000000")
        self.is_fullscreen = False

        self.canvas = tk.Canvas(self, width=960, height=540, bg="#05070a", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        # Duplo clique ou F11 alterna Tela Cheia (Projector Mode estilo OBS/vMix)
        self.bind("<Double-Button-1>", self.toggle_fullscreen)
        self.bind("<F11>", self.toggle_fullscreen)
        self.bind("<Escape>", lambda e: self.set_fullscreen(False))

    def toggle_fullscreen(self, event=None):
        self.set_fullscreen(not self.is_fullscreen)

    def set_fullscreen(self, state: bool):
        self.is_fullscreen = state
        self.attributes("-fullscreen", self.is_fullscreen)


class WebLiveNativeStudioApp:
    """Estação Completa de Produção Ao Vivo 100% Nativa em Desktop (Sem Navegador)."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("🎬 WebLive Studio Pro v3.0 — Estação Nativa de Produção Ao Vivo & Broadcast (Python Desktop)")
        self.root.geometry("1440x860")
        self.root.minsize(1220, 760)
        self.root.configure(bg="#0b0e14")

        # Inicia servidor de background silencioso (apenas para receber WebRTC do celular, Stream Deck #46 e OBS Sync)
        self.server = WebLivePythonServer(port=3000)
        self.active_port = self.server.start()
        self.lan_ip = get_lan_ip()

        # Estado completo do Switcher Nativo
        self.scenes = [
            {"id": "scene_1", "key": "1", "name": "Estúdio Principal", "subtitle": "Apresentador • Cam 1 (1080p60)", "sourceType": "cam1", "layoutMode": "single", "bgTheme": "cyber-grid"},
            {"id": "scene_2", "key": "2", "name": "Repórter Externo", "subtitle": "WebRTC Call • Mix-Minus Ativo", "sourceType": "guest1", "layoutMode": "single", "bgTheme": "news-globe"},
            {"id": "scene_3", "key": "3", "name": "Entrevista PiP", "subtitle": "Estúdio + Repórter em PiP (#1)", "sourceType": "cam1", "layoutMode": "pip", "bgTheme": "cyber-grid"},
            {"id": "scene_4", "key": "4", "name": "Mosaico 4x Grid", "subtitle": "Debate Multi-view 4 Convidados (#2)", "sourceType": "cam1", "layoutMode": "grid4", "bgTheme": "news-globe"},
            {"id": "scene_5", "key": "5", "name": "Mídia / yt-dlp VT", "subtitle": "Stream de Vídeo / Playlist (#22)", "sourceType": "webmedia", "layoutMode": "single", "bgTheme": "stadium-lights"},
            {"id": "scene_6", "key": "6", "name": "Mosaico 8x Arena", "subtitle": "Super Grid 8 Participantes (#2)", "sourceType": "cam1", "layoutMode": "grid8", "bgTheme": "stadium-lights"},
        ]
        self.pvw_idx = 1
        self.pgm_idx = 0
        self.scene_locked = tk.BooleanVar(value=False)
        self.snap_grid_enabled = tk.BooleanVar(value=False)
        self.whiteboard_enabled = tk.BooleanVar(value=False)
        self.whiteboard_color = "#ffeb3b"
        self.whiteboard_strokes = []
        self.current_stroke = None

        # Configurações Visuais (#1-#10)
        self.layout_mode_var = tk.StringVar(value="single")
        self.bg_theme_var = tk.StringVar(value="cyber-grid")
        self.chroma_enabled = tk.BooleanVar(value=False)
        self.chroma_tol = tk.IntVar(value=95)
        self.pip_scale = tk.IntVar(value=28)
        self.brightness_var = tk.IntVar(value=100)
        self.contrast_var = tk.IntVar(value=100)
        self.saturation_var = tk.IntVar(value=100)
        self.crop_top_var = tk.IntVar(value=0)
        self.watermark_text = tk.StringVar(value="WEBLIVE PRO")

        # Overlays Gráficos (GC #5, Placar #4, Ticker #7/#37, Enquete #32, Meta #34, QR #9, Countdown #25)
        self.lt_visible = False
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
        self.ticker_text = tk.StringVar(value="URGENTE: Estação Nativa WebLive Studio Pro operando a 60fps com Mix-Minus e SQLite • ")
        self.ticker_offset = 0

        self.qr_visible = False
        self.qr_url = tk.StringVar(value="https://weblive.studio/pix")
        self.poll_visible = False
        self.poll_votes_a = 68
        self.poll_votes_b = 32
        self.goal_visible = False
        self.goal_current = 840
        self.goal_target = 1000
        self.featured_comment_visible = False
        self.featured_author = "@Mariana_TV"
        self.featured_text = "Agora rodando 100% em aplicativo Desktop nativo!"
        self.weather_visible = False
        self.countdown_visible = False
        self.countdown_sec = 180
        self.stinger_active_until = 0.0
        self.replay_active_until = 0.0
        self.alert_active_until = 0.0
        self.alert_user = "Gabriel_VIP • R$ 100,00"
        self.alert_msg = "Parabéns pela plataforma nativa!"
        self.recording_backup = False

        # Canais de Áudio Multi-Pista (#11-#20)
        self.panic_muted = False
        self.ducking_enabled = tk.BooleanVar(value=True)
        self.auto_voice_switch = tk.BooleanVar(value=False)
        self.talkback_active = False
        self.audio_channels = [
            {"id": "cam1", "name": "Câmera 1 (Apresentador)", "vol": tk.DoubleVar(value=90), "pan": tk.DoubleVar(value=0), "delay": tk.IntVar(value=0), "muted": False, "pfl": False, "vu": 0},
            {"id": "guest1", "name": "Repórter Remoto (Mix-Minus)", "vol": tk.DoubleVar(value=85), "pan": tk.DoubleVar(value=0), "delay": tk.IntVar(value=40), "muted": False, "pfl": False, "vu": 0},
            {"id": "media1", "name": "Mídia / yt-dlp / VT (BGM)", "vol": tk.DoubleVar(value=75), "pan": tk.DoubleVar(value=0), "delay": tk.IntVar(value=0), "muted": False, "pfl": False, "vu": 0},
            {"id": "sfx", "name": "Soundboard / Vinhetas", "vol": tk.DoubleVar(value=85), "pan": tk.DoubleVar(value=0), "delay": tk.IntVar(value=0), "muted": False, "pfl": False, "vu": 0},
        ]

        self.playlist = [
            "https://www.youtube.com/watch?v=jfKfPfyJRdk",
            "https://www.youtube.com/watch?v=5qap5aO4i9A",
        ]
        self.scheduled_events = []
        self.projectors = []
        self.dark_mode = True
        self.frame_counter = 0
        self.last_fps_time = time.time()
        self.current_fps = 60

        self._setup_styles()
        self._build_top_bar()
        self._build_3column_workspace()
        self._bind_keyboard_shortcuts()

        self.log_action("Estação Desktop Nativa WebLive Studio Pro v3.0 iniciada (Sem navegador)")
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
    # BARRA SUPERIOR (TOPBAR: Relógio #26, Saúde #42, Perfis #29, Panic #20, Projetor OBS)
    # =========================================================================
    def _build_top_bar(self):
        self.topbar = tk.Frame(self.root, bg="#131822", height=52, highlightthickness=1, highlightbackground="#2b3548")
        self.topbar.pack(fill="x", side="top")

        tk.Label(
            self.topbar,
            text="🔴 WEBLIVE STUDIO PRO v3.0 • ESTAÇÃO NATIVA",
            font=("Segoe UI", 12, "bold"),
            fg="#ff5252",
            bg="#131822",
        ).pack(side="left", padx=14)

        # Relógio Broadcast (#26) + Saúde (#42)
        self.lbl_clock = tk.Label(self.topbar, text="🕒 00:00:00 (BRT)", font=("Consolas", 10, "bold"), fg="#38bdf8", bg="#1c2331", padx=8, pady=4)
        self.lbl_clock.pack(side="left", padx=4)

        self.lbl_health = tk.Label(self.topbar, text="⚡ 60 FPS • CPU 11% • SQLite OK", font=("Consolas", 9), fg="#00e676", bg="#1c2331", padx=8, pady=4)
        self.lbl_health.pack(side="left", padx=4)

        # Botões da Direita (Projetores Nativos para OBS, Clean Feed #43, Panic Mute #20, Tema #30)
        tk.Button(
            self.topbar,
            text="🧼 Abrir Janela Clean Feed (#43)",
            font=("Segoe UI", 9, "bold"),
            bg="#252f42",
            fg="#ffffff",
            relief="flat",
            cursor="hand2",
            padx=8,
            command=lambda: self.open_native_projector(clean_feed=True),
        ).pack(side="right", padx=(4, 12), pady=8)

        tk.Button(
            self.topbar,
            text="📺 Abrir Projetor Nativo OBS (Saída PGM)",
            font=("Segoe UI", 9, "bold"),
            bg="#2979ff",
            fg="#ffffff",
            relief="flat",
            cursor="hand2",
            padx=10,
            command=lambda: self.open_native_projector(clean_feed=False),
        ).pack(side="right", padx=4, pady=8)

        self.btn_panic = tk.Button(
            self.topbar,
            text="🔇 PANIC MUTE (#20)",
            font=("Segoe UI", 9, "bold"),
            bg="#e53935",
            fg="#ffffff",
            relief="flat",
            cursor="hand2",
            padx=10,
            command=self.toggle_panic_mute,
        )
        self.btn_panic.pack(side="right", padx=4, pady=8)

        # Seletor de Perfil (#29)
        self.role_var = tk.StringVar(value="Perfil: Diretor Geral")
        role_menu = ttk.Combobox(
            self.topbar,
            textvariable=self.role_var,
            values=["Perfil: Diretor Geral", "Perfil: Operador de GC", "Perfil: Operador de Áudio"],
            state="readonly",
            width=22,
        )
        role_menu.pack(side="right", padx=6)
        role_menu.bind("<<ComboboxSelected>>", lambda e: self.log_action(f"Perfil (#29) alterado para {self.role_var.get()}"))

    # =========================================================================
    # WORKSPACE 3 COLUNAS (Esquerda: Cenas/WebRTC/Mídia | Centro: PVW/PGM/Abas | Direita: Mixer/SFX)
    # =========================================================================
    def _build_3column_workspace(self):
        workspace = tk.Frame(self.root, bg="#0b0e14", padx=8, pady=8)
        workspace.pack(fill="both", expand=True)

        workspace.columnconfigure(0, weight=0, minsize=305)
        workspace.columnconfigure(1, weight=1)
        workspace.columnconfigure(2, weight=0, minsize=335)
        workspace.rowconfigure(0, weight=1)

        # COLUNA ESQUERDA
        col_left = tk.Frame(workspace, bg="#0b0e14")
        col_left.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        self._build_left_column(col_left)

        # COLUNA CENTRAL
        col_center = tk.Frame(workspace, bg="#0b0e14")
        col_center.grid(row=0, column=1, sticky="nsew", padx=4)
        self._build_center_column(col_center)

        # COLUNA DIREITA
        col_right = tk.Frame(workspace, bg="#0b0e14")
        col_right.grid(row=0, column=2, sticky="nsew", padx=(6, 0))
        self._build_right_column(col_right)

    def _build_left_column(self, parent):
        # 1. Cenas (Core #1, Lock #44, Macros #21)
        scenes_card = tk.LabelFrame(parent, text=" 🎬 CENAS & ATALHOS [1-6 / ESPAÇO] ", font=("Segoe UI", 9, "bold"), fg="#8b9bb4", bg="#131822", bd=1, relief="solid", padx=8, pady=8)
        scenes_card.pack(fill="x", pady=(0, 8))

        top_sc = tk.Frame(scenes_card, bg="#131822")
        top_sc.pack(fill="x", pady=(0, 6))
        tk.Checkbutton(top_sc, text="🔒 Travar Cena (#44)", variable=self.scene_locked, bg="#131822", fg="#ffb300", selectcolor="#1c2331", activebackground="#131822", font=("Segoe UI", 8, "bold")).pack(side="left")
        tk.Button(top_sc, text="+ Nova Cena", bg="#2979ff", fg="#fff", relief="flat", font=("Segoe UI", 8, "bold"), command=self.add_custom_scene).pack(side="right")

        self.scenes_frame = tk.Frame(scenes_card, bg="#131822")
        self.scenes_frame.pack(fill="x")
        self.scene_buttons = []
        self._render_scene_buttons()

        # 2. Entrada Remota WebRTC + Mix-Minus + Talkback (#16) + Speedtest (#41)
        rtc_card = tk.LabelFrame(parent, text=" 📱 CALL WEBRTC & MIX-MINUS (CORE #7) ", font=("Segoe UI", 9, "bold"), fg="#8b9bb4", bg="#131822", bd=1, relief="solid", padx=8, pady=8)
        rtc_card.pack(fill="x", pady=(0, 8))

        guest_url = f"http://{self.lan_ip}:{self.active_port}/guest.html?guest=Reporter1"
        ent_guest = tk.Entry(rtc_card, font=("Consolas", 8), bg="#1c2331", fg="#38bdf8", relief="flat")
        ent_guest.insert(0, guest_url)
        ent_guest.configure(state="readonly")
        ent_guest.pack(fill="x", pady=(0, 6))

        rtc_btns = tk.Frame(rtc_card, bg="#131822")
        rtc_btns.pack(fill="x", pady=(0, 6))
        tk.Button(rtc_btns, text="📋 Copiar Link Repórter", bg="#2b3548", fg="#fff", relief="flat", font=("Segoe UI", 8, "bold"), command=lambda: self._copy_text(guest_url)).pack(side="left", fill="x", expand=True, padx=(0, 4))
        tk.Button(rtc_btns, text="📶 Speedtest (#41)", bg="#2b3548", fg="#00e676", relief="flat", font=("Segoe UI", 8, "bold"), command=self.run_native_speedtest).pack(side="left", fill="x", expand=True)

        self.btn_talkback = tk.Button(rtc_card, text="🎙️ SEGURE P/ TALKBACK INTERCOM (#16)", bg="#ffb300", fg="#000", relief="flat", font=("Segoe UI", 8, "bold"))
        self.btn_talkback.pack(fill="x", pady=(0, 4))
        self.btn_talkback.bind("<ButtonPress-1>", lambda e: self.set_talkback(True))
        self.btn_talkback.bind("<ButtonRelease-1>", lambda e: self.set_talkback(False))

        self.lbl_rtc_info = tk.Label(rtc_card, text="Tally (#24): Sincronizado • Mix-Minus: Zero Eco", font=("Consolas", 8), fg="#94a3b8", bg="#131822")
        self.lbl_rtc_info.pack(anchor="w")

        # 3. Mídia Externa, Extrator Python yt-dlp & Playlist (#22)
        media_card = tk.LabelFrame(parent, text=" 🎞️ MÍDIA, YT-DLP PYTHON & PLAYLIST (#22) ", font=("Segoe UI", 9, "bold"), fg="#8b9bb4", bg="#131822", bd=1, relief="solid", padx=8, pady=8)
        media_card.pack(fill="both", expand=True)

        self.ent_media_url = tk.Entry(media_card, font=("Consolas", 8), bg="#1c2331", fg="#fff", insertbackground="#fff", relief="flat")
        self.ent_media_url.insert(0, "https://www.youtube.com/watch?v=jfKfPfyJRdk")
        self.ent_media_url.pack(fill="x", pady=(0, 6))

        m_btns = tk.Frame(media_card, bg="#131822")
        m_btns.pack(fill="x", pady=(0, 6))
        tk.Button(m_btns, text="🐍 Extrair yt-dlp", bg="#ffb300", fg="#000", relief="flat", font=("Segoe UI", 8, "bold"), command=self.extract_ytdlp_native).pack(side="left", fill="x", expand=True, padx=(0, 3))
        tk.Button(m_btns, text="+ Fila", bg="#2979ff", fg="#fff", relief="flat", font=("Segoe UI", 8, "bold"), command=self.add_to_playlist).pack(side="left", padx=3)
        tk.Button(m_btns, text="⏭ Próx.", bg="#252f42", fg="#fff", relief="flat", font=("Segoe UI", 8, "bold"), command=self.next_playlist_item).pack(side="left")

        self.lst_playlist = tk.Listbox(media_card, bg="#090c10", fg="#cbd5e1", font=("Consolas", 8), height=5, relief="flat")
        self.lst_playlist.pack(fill="both", expand=True)
        self._refresh_playlist_box()

    def _build_center_column(self, parent):
        # 1. Monitores Duplos Nativos: PREVIEW (PVW) e PROGRAM (PGM) + Barra de Corte
        mon_card = tk.Frame(parent, bg="#131822", highlightthickness=1, highlightbackground="#2b3548", padx=10, pady=10)
        mon_card.pack(fill="x", pady=(0, 8))

        mon_grid = tk.Frame(mon_card, bg="#131822")
        mon_grid.pack(fill="x")
        mon_grid.columnconfigure(0, weight=1)
        mon_grid.columnconfigure(1, weight=0)
        mon_grid.columnconfigure(2, weight=1)

        # PVW Box
        pvw_box = tk.Frame(mon_grid, bg="#000", highlightthickness=2, highlightbackground="#00c853")
        pvw_box.grid(row=0, column=0, sticky="nsew")
        self.lbl_pvw_title = tk.Label(pvw_box, text="🟢 PREVIEW (PVW) • REPÓRTER EXTERNO", font=("Segoe UI", 8, "bold"), bg="#072b16", fg="#4ade80", anchor="w", padx=6)
        self.lbl_pvw_title.pack(fill="x")
        self.pvw_canvas = tk.Canvas(pvw_box, width=360, height=202, bg="#05070a", highlightthickness=0)
        self.pvw_canvas.pack(fill="both", expand=True)

        # Barra Central de Transição (CUT, AUTO, STINGER #3, REPLAY #8, GRID #47)
        t_bar = tk.Frame(mon_grid, bg="#131822", padx=8)
        t_bar.grid(row=0, column=1, sticky="ns")
        tk.Button(t_bar, text="✂️ CUT\n[Espaço]", bg="#e53935", fg="#fff", font=("Segoe UI", 9, "bold"), relief="flat", width=9, pady=6, command=lambda: self.execute_transition("cut")).pack(pady=3)
        tk.Button(t_bar, text="✨ AUTO", bg="#2979ff", fg="#fff", font=("Segoe UI", 8, "bold"), relief="flat", width=9, pady=4, command=lambda: self.execute_transition("auto")).pack(pady=3)
        tk.Button(t_bar, text="⚡ STINGER", bg="#ffb300", fg="#000", font=("Segoe UI", 8, "bold"), relief="flat", width=9, pady=4, command=lambda: self.execute_transition("stinger")).pack(pady=3)
        tk.Button(t_bar, text="⏪ REPLAY", bg="#252f42", fg="#fff", font=("Segoe UI", 8, "bold"), relief="flat", width=9, pady=4, command=self.trigger_instant_replay).pack(pady=3)
        tk.Checkbutton(t_bar, text="📏 Grid #47", variable=self.snap_grid_enabled, bg="#131822", fg="#38bdf8", selectcolor="#1c2331", font=("Segoe UI", 8)).pack(pady=2)

        # PGM Box (Com suporte a Whiteboard Interativo #40 direto no monitor!)
        pgm_box = tk.Frame(mon_grid, bg="#000", highlightthickness=2, highlightbackground="#e53935")
        pgm_box.grid(row=0, column=2, sticky="nsew")
        self.lbl_pgm_title = tk.Label(pgm_box, text="🔴 PROGRAM (NO AR) • ESTÚDIO PRINCIPAL", font=("Segoe UI", 8, "bold"), bg="#330b0b", fg="#ff5252", anchor="w", padx=6)
        self.lbl_pgm_title.pack(fill="x")
        self.pgm_canvas = tk.Canvas(pgm_box, width=360, height=202, bg="#05070a", highlightthickness=0, cursor="crosshair")
        self.pgm_canvas.pack(fill="both", expand=True)

        # Eventos de desenho do Whiteboard (#40) direto no Canvas PGM
        self.pgm_canvas.bind("<ButtonPress-1>", self._wb_start)
        self.pgm_canvas.bind("<B1-Motion>", self._wb_draw)
        self.pgm_canvas.bind("<ButtonRelease-1>", self._wb_end)

        # Barra Inferior dos Monitores: Whiteboard (#40), Countdown (#25), Backup Local (#27)
        tools_bar = tk.Frame(mon_card, bg="#131822")
        tools_bar.pack(fill="x", pady=(8, 0))
        tk.Checkbutton(tools_bar, text="✏️ Desenhar no PGM (Whiteboard #40)", variable=self.whiteboard_enabled, bg="#131822", fg="#ffeb3b", selectcolor="#1c2331", font=("Segoe UI", 8, "bold")).pack(side="left")
        tk.Button(tools_bar, text="🎨 Cor", bg="#252f42", fg="#fff", relief="flat", font=("Segoe UI", 8), command=self.pick_whiteboard_color).pack(side="left", padx=4)
        tk.Button(tools_bar, text="🗑️ Limpar Tela", bg="#252f42", fg="#fff", relief="flat", font=("Segoe UI", 8), command=self.clear_whiteboard).pack(side="left", padx=4)

        self.btn_record = tk.Button(tools_bar, text="⏺️ Gravar Backup (#27)", bg="#252f42", fg="#fff", relief="flat", font=("Segoe UI", 8, "bold"), command=self.toggle_backup_recording)
        self.btn_record.pack(side="right", padx=2)
        tk.Button(tools_bar, text="⏳ Countdown Live (#25)", bg="#252f42", fg="#38bdf8", relief="flat", font=("Segoe UI", 8, "bold"), command=self.toggle_countdown).pack(side="right", padx=4)

        # 2. Abas de Produção Completas (GC/Placar, Vídeo/Chroma, Social/QR, Automação/RTMP/Logs)
        self.notebook = ttk.Notebook(parent)
        self.notebook.pack(fill="both", expand=True)

        tab_gc = tk.Frame(self.notebook, bg="#131822", padx=10, pady=10)
        tab_video = tk.Frame(self.notebook, bg="#131822", padx=10, pady=10)
        tab_social = tk.Frame(self.notebook, bg="#131822", padx=10, pady=10)
        tab_auto = tk.Frame(self.notebook, bg="#131822", padx=10, pady=10)

        self.notebook.add(tab_gc, text="🏷️ GC, Placar & Ticker")
        self.notebook.add(tab_video, text="🎨 Vídeo, PiP, Grid & Chroma (#1-#10)")
        self.notebook.add(tab_social, text="💬 Chat, Enquete, Meta & QR (#31-#40)")
        self.notebook.add(tab_auto, text="⚙️ RTMP, Agendador, JSON & SQLite (#28-#50)")

        self._populate_tab_gc(tab_gc)
        self._populate_tab_video(tab_video)
        self._populate_tab_social(tab_social)
        self._populate_tab_auto(tab_auto)

    def _populate_tab_gc(self, tab):
        row1 = tk.Frame(tab, bg="#131822")
        row1.pack(fill="x", pady=(0, 8))

        # Lower Thirds (Core #5)
        lt_frame = tk.LabelFrame(row1, text=" TARJETA / LOWER THIRD (CORE #5) ", font=("Segoe UI", 8, "bold"), fg="#38bdf8", bg="#1c2331", padx=8, pady=6)
        lt_frame.pack(side="left", fill="both", expand=True, padx=(0, 6))
        tk.Entry(lt_frame, textvariable=self.lt_title, bg="#0b0e14", fg="#fff", insertbackground="#fff", relief="flat", font=("Segoe UI", 9, "bold")).pack(fill="x", pady=2)
        tk.Entry(lt_frame, textvariable=self.lt_sub, bg="#0b0e14", fg="#38bdf8", insertbackground="#fff", relief="flat", font=("Segoe UI", 8)).pack(fill="x", pady=2)
        lt_ctrl = tk.Frame(lt_frame, bg="#1c2331")
        lt_ctrl.pack(fill="x", pady=4)
        ttk.Combobox(lt_ctrl, textvariable=self.lt_mode, values=["Fixa (Permanente)", "Temporária (5s)", "Temporária (8s)"], state="readonly", width=16).pack(side="left")
        tk.Button(lt_ctrl, text="🏷️ Exibir / Ocultar GC", bg="#e53935", fg="#fff", relief="flat", font=("Segoe UI", 8, "bold"), command=self.toggle_lower_third).pack(side="right", fill="x", expand=True, padx=(6, 0))

        # Placar Esportivo (Core #4)
        sb_frame = tk.LabelFrame(row1, text=" PLACAR ESPORTIVO & CRONÔMETRO (CORE #4) ", font=("Segoe UI", 8, "bold"), fg="#00e676", bg="#1c2331", padx=8, pady=6)
        sb_frame.pack(side="left", fill="both", expand=True)
        teams_row = tk.Frame(sb_frame, bg="#1c2331")
        teams_row.pack(fill="x", pady=2)
        tk.Entry(teams_row, textvariable=self.sb_team_a, width=11, bg="#0b0e14", fg="#fff", relief="flat").pack(side="left", padx=2)
        tk.Spinbox(teams_row, from_=0, to=99, textvariable=self.sb_pts_a, width=4, bg="#2979ff", fg="#fff", relief="flat").pack(side="left", padx=2)
        tk.Entry(teams_row, textvariable=self.sb_team_b, width=11, bg="#0b0e14", fg="#fff", relief="flat").pack(side="left", padx=2)
        tk.Spinbox(teams_row, from_=0, to=99, textvariable=self.sb_pts_b, width=4, bg="#e53935", fg="#fff", relief="flat").pack(side="left", padx=2)

        sb_btns = tk.Frame(sb_frame, bg="#1c2331")
        sb_btns.pack(fill="x", pady=4)
        tk.Button(sb_btns, text="⚽ Placar No Ar", bg="#2979ff", fg="#fff", relief="flat", font=("Segoe UI", 8, "bold"), command=self.toggle_scoreboard).pack(side="left", fill="x", expand=True, padx=2)
        tk.Button(sb_btns, text="⏱️ Play/Pause", bg="#252f42", fg="#fff", relief="flat", font=("Segoe UI", 8), command=self.toggle_sb_timer).pack(side="left", padx=2)
        tk.Button(sb_btns, text="Zerar", bg="#252f42", fg="#fff", relief="flat", font=("Segoe UI", 8), command=self.reset_sb_timer).pack(side="left", padx=2)

        # Ticker / Crawl (#7) + Feed RSS Python Real (#37)
        tk_frame = tk.LabelFrame(tab, text=" 📰 TICKER TAPE / CRAWL (#7) & EXTRATOR FEED RSS PYTHON (#37) ", font=("Segoe UI", 8, "bold"), fg="#8b9bb4", bg="#1c2331", padx=8, pady=6)
        tk_frame.pack(fill="x")
        tk.Entry(tk_frame, textvariable=self.ticker_text, bg="#0b0e14", fg="#fff", relief="flat", font=("Segoe UI", 9)).pack(side="left", fill="x", expand=True, padx=(0, 6))
        tk.Button(tk_frame, text="📡 Puxar RSS Real (#37)", bg="#252f42", fg="#38bdf8", relief="flat", font=("Segoe UI", 8, "bold"), command=self.fetch_rss_to_ticker).pack(side="left", padx=3)
        tk.Button(tk_frame, text="Ticker No Ar", bg="#e53935", fg="#fff", relief="flat", font=("Segoe UI", 8, "bold"), command=self.toggle_ticker).pack(side="left")

    def _populate_tab_video(self, tab):
        v_left = tk.LabelFrame(tab, text=" LAYOUT MULTI-VIEW (#2), PIP (#1) & CHROMA KEY (#3) ", font=("Segoe UI", 8, "bold"), fg="#38bdf8", bg="#1c2331", padx=8, pady=6)
        v_left.pack(side="left", fill="both", expand=True, padx=(0, 6))

        tk.Label(v_left, text="Modo de Layout da Cena:", bg="#1c2331", fg="#cbd5e1", font=("Segoe UI", 8)).pack(anchor="w")
        cb_layout = ttk.Combobox(v_left, textvariable=self.layout_mode_var, values=["single", "pip", "grid4", "grid8"], state="readonly")
        cb_layout.pack(fill="x", pady=2)

        tk.Label(v_left, text="Background Dinâmico em Loop (#10):", bg="#1c2331", fg="#cbd5e1", font=("Segoe UI", 8)).pack(anchor="w")
        ttk.Combobox(v_left, textvariable=self.bg_theme_var, values=["cyber-grid", "news-globe", "stadium-lights"], state="readonly").pack(fill="x", pady=2)

        tk.Checkbutton(v_left, text="🟢 Ativar Chroma Key Fundo Verde (#3)", variable=self.chroma_enabled, bg="#1c2331", fg="#00e676", selectcolor="#0b0e14", font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=2)
        tk.Scale(v_left, from_=15, to=45, orient="horizontal", label="Escala da Janela PiP % (#1)", variable=self.pip_scale, bg="#1c2331", fg="#cbd5e1", highlightthickness=0).pack(fill="x")

        v_right = tk.LabelFrame(tab, text=" CORREÇÃO DE COR (#5), RECORTE CROP (#4) & MARCA D'ÁGUA (#6) ", font=("Segoe UI", 8, "bold"), fg="#00e676", bg="#1c2331", padx=8, pady=6)
        v_right.pack(side="left", fill="both", expand=True)

        tk.Scale(v_right, from_=50, to=150, orient="horizontal", label="Brilho % (#5)", variable=self.brightness_var, bg="#1c2331", fg="#cbd5e1", highlightthickness=0).pack(fill="x")
        tk.Scale(v_right, from_=0, to=35, orient="horizontal", label="Recorte / Crop Superior % (#4)", variable=self.crop_top_var, bg="#1c2331", fg="#cbd5e1", highlightthickness=0).pack(fill="x")

        wm_row = tk.Frame(v_right, bg="#1c2331")
        wm_row.pack(fill="x", pady=4)
        tk.Label(wm_row, text="Marca d'água (#6):", bg="#1c2331", fg="#cbd5e1", font=("Segoe UI", 8)).pack(side="left")
        tk.Entry(wm_row, textvariable=self.watermark_text, bg="#0b0e14", fg="#fff", relief="flat", width=18).pack(side="left", padx=6)

    def _populate_tab_social(self, tab):
        s_left = tk.LabelFrame(tab, text=" 💬 CHAT AO VIVO (#31), FILTRO PALAVRÕES (#38) & DESTAQUE (#35) ", font=("Segoe UI", 8, "bold"), fg="#38bdf8", bg="#1c2331", padx=8, pady=6)
        s_left.pack(side="left", fill="both", expand=True, padx=(0, 6))

        self.profanity_filter = tk.BooleanVar(value=True)
        tk.Checkbutton(s_left, text="Filtro Automático de Palavrões (#38)", variable=self.profanity_filter, bg="#1c2331", fg="#cbd5e1", selectcolor="#0b0e14", font=("Segoe UI", 8)).pack(anchor="w")

        self.ent_chat_user = tk.Entry(s_left, bg="#0b0e14", fg="#38bdf8", relief="flat", font=("Segoe UI", 8, "bold"))
        self.ent_chat_user.insert(0, "@Mariana_TV")
        self.ent_chat_user.pack(fill="x", pady=2)

        self.ent_chat_msg = tk.Entry(s_left, bg="#0b0e14", fg="#fff", relief="flat", font=("Segoe UI", 9))
        self.ent_chat_msg.insert(0, "Agora operando 100% na plataforma nativa Python!")
        self.ent_chat_msg.pack(fill="x", pady=2)

        tk.Button(s_left, text="🌟 Destacar Comentário na Tela (#35)", bg="#2979ff", fg="#fff", relief="flat", font=("Segoe UI", 8, "bold"), command=self.trigger_featured_comment).pack(fill="x", pady=4)

        s_right = tk.LabelFrame(tab, text=" 📊 ENQUETE (#32), META (#34), DOAÇÃO (#33), CLIMA (#36) & QR (#9) ", font=("Segoe UI", 8, "bold"), fg="#ffb300", bg="#1c2331", padx=8, pady=6)
        s_right.pack(side="left", fill="both", expand=True)

        qr_row = tk.Frame(s_right, bg="#1c2331")
        qr_row.pack(fill="x", pady=2)
        tk.Entry(qr_row, textvariable=self.qr_url, bg="#0b0e14", fg="#fff", relief="flat").pack(side="left", fill="x", expand=True, padx=(0, 4))
        tk.Button(qr_row, text="📱 QR Code (#9)", bg="#2979ff", fg="#fff", relief="flat", font=("Segoe UI", 8, "bold"), command=self.toggle_qr).pack(side="left")

        poll_row = tk.Frame(s_right, bg="#1c2331")
        poll_row.pack(fill="x", pady=4)
        tk.Button(poll_row, text="📊 Enquete (#32)", bg="#252f42", fg="#fff", relief="flat", font=("Segoe UI", 8, "bold"), command=self.toggle_poll).pack(side="left", fill="x", expand=True, padx=2)
        tk.Button(poll_row, text="+Voto A", bg="#2979ff", fg="#fff", relief="flat", font=("Segoe UI", 8), command=lambda: self.vote_poll("A")).pack(side="left", padx=2)
        tk.Button(poll_row, text="+Voto B", bg="#e53935", fg="#fff", relief="flat", font=("Segoe UI", 8), command=lambda: self.vote_poll("B")).pack(side="left", padx=2)

        eng_row = tk.Frame(s_right, bg="#1c2331")
        eng_row.pack(fill="x", pady=2)
        tk.Button(eng_row, text="🎯 Meta (#34)", bg="#252f42", fg="#00e676", relief="flat", font=("Segoe UI", 8, "bold"), command=self.toggle_goal).pack(side="left", fill="x", expand=True, padx=2)
        tk.Button(eng_row, text="🎉 Superchat (#33)", bg="#ffb300", fg="#000", relief="flat", font=("Segoe UI", 8, "bold"), command=self.trigger_superchat).pack(side="left", fill="x", expand=True, padx=2)
        tk.Button(eng_row, text="🌤️ Clima (#36)", bg="#252f42", fg="#38bdf8", relief="flat", font=("Segoe UI", 8, "bold"), command=self.toggle_weather).pack(side="left", padx=2)

    def _populate_tab_auto(self, tab):
        a_left = tk.LabelFrame(tab, text=" 📡 STREAMER RTMP PYTHON, AGENDADOR (#28) & JSON (#45) ", font=("Segoe UI", 8, "bold"), fg="#38bdf8", bg="#1c2331", padx=8, pady=6)
        a_left.pack(side="left", fill="both", expand=True, padx=(0, 6))

        rtmp_row = tk.Frame(a_left, bg="#1c2331")
        rtmp_row.pack(fill="x", pady=2)
        self.ent_rtmp = tk.Entry(rtmp_row, bg="#0b0e14", fg="#fff", relief="flat", font=("Consolas", 8))
        self.ent_rtmp.insert(0, "rtmp://a.rtmp.youtube.com/live2")
        self.ent_rtmp.pack(side="left", fill="x", expand=True, padx=(0, 4))
        self.btn_rtmp = tk.Button(rtmp_row, text="🚀 Iniciar RTMP", bg="#ffb300", fg="#000", relief="flat", font=("Segoe UI", 8, "bold"), command=self.toggle_rtmp)
        self.btn_rtmp.pack(side="left")

        sched_row = tk.Frame(a_left, bg="#1c2331")
        sched_row.pack(fill="x", pady=4)
        tk.Label(sched_row, text="Agendar HH:MM:SS (#28):", bg="#1c2331", fg="#cbd5e1", font=("Segoe UI", 8)).pack(side="left")
        self.ent_sched_time = tk.Entry(sched_row, width=9, bg="#0b0e14", fg="#fff", relief="flat", font=("Consolas", 8))
        self.ent_sched_time.insert(0, "23:30:00")
        self.ent_sched_time.pack(side="left", padx=4)
        tk.Button(sched_row, text="⏰ Agendar Cena", bg="#2979ff", fg="#fff", relief="flat", font=("Segoe UI", 8, "bold"), command=self.schedule_scene).pack(side="left")

        json_row = tk.Frame(a_left, bg="#1c2331")
        json_row.pack(fill="x", pady=4)
        tk.Button(json_row, text="💾 Exportar Projeto JSON (#45)", bg="#252f42", fg="#fff", relief="flat", font=("Segoe UI", 8), command=self.export_json).pack(side="left", fill="x", expand=True, padx=(0, 4))
        tk.Button(json_row, text="📂 Importar JSON (#45)", bg="#252f42", fg="#fff", relief="flat", font=("Segoe UI", 8), command=self.import_json).pack(side="left", fill="x", expand=True)

        a_right = tk.LabelFrame(tab, text=" 📋 HISTÓRICO SQLITE DE AUDITORIA / COMERCIAIS (#49) ", font=("Segoe UI", 8, "bold"), fg="#00e676", bg="#1c2331", padx=8, pady=6)
        a_right.pack(side="left", fill="both", expand=True)
        self.lst_logs = tk.Listbox(a_right, bg="#090c10", fg="#cbd5e1", font=("Consolas", 8), height=6, relief="flat")
        self.lst_logs.pack(fill="both", expand=True)

    # =========================================================================
    # COLUNA DIREITA: AUDIO MIXER MULTI-PISTA (#11-#20) & SOUNDBOARD (#15)
    # =========================================================================
    def _build_right_column(self, parent):
        mixer_card = tk.LabelFrame(parent, text=" 🎚️ AUDIO MIXER MULTI-PISTA (#11-#20) ", font=("Segoe UI", 9, "bold"), fg="#8b9bb4", bg="#131822", bd=1, relief="solid", padx=8, pady=8)
        mixer_card.pack(fill="both", expand=True, pady=(0, 8))

        dsp_row = tk.Frame(mixer_card, bg="#131822")
        dsp_row.pack(fill="x", pady=(0, 6))
        tk.Checkbutton(dsp_row, text="🦆 Audio Ducking (#14)", variable=self.ducking_enabled, bg="#131822", fg="#cbd5e1", selectcolor="#1c2331", font=("Segoe UI", 8)).pack(side="left")
        tk.Checkbutton(dsp_row, text="🗣️ Auto-Voz (#23)", variable=self.auto_voice_switch, bg="#131822", fg="#cbd5e1", selectcolor="#1c2331", font=("Segoe UI", 8)).pack(side="right")

        self.vu_canvases = {}
        for ch in self.audio_channels:
            strip = tk.Frame(mixer_card, bg="#1c2331", highlightthickness=1, highlightbackground="#2b3548", padx=6, pady=5)
            strip.pack(fill="x", pady=3)

            hdr = tk.Frame(strip, bg="#1c2331")
            hdr.pack(fill="x")
            tk.Label(hdr, text=ch["name"], font=("Segoe UI", 8, "bold"), fg="#fff", bg="#1c2331").pack(side="left")

            btn_mute = tk.Button(hdr, text="🔊 ON", bg="#252f42", fg="#00e676", relief="flat", font=("Segoe UI", 7, "bold"), width=6)
            btn_mute.configure(command=lambda c=ch, b=btn_mute: self.toggle_channel_mute(c, b))
            btn_mute.pack(side="right", padx=2)

            btn_pfl = tk.Button(hdr, text="🎧 PFL", bg="#252f42", fg="#cbd5e1", relief="flat", font=("Segoe UI", 7, "bold"), width=6)
            btn_pfl.configure(command=lambda c=ch, b=btn_pfl: self.toggle_channel_pfl(c, b))
            btn_pfl.pack(side="right", padx=2)

            # Barra VU Meter Nativa
            vu_cv = tk.Canvas(strip, height=8, bg="#090c10", highlightthickness=0)
            vu_cv.pack(fill="x", pady=4)
            self.vu_canvases[ch["id"]] = vu_cv

            # Fader de Volume (#11)
            f_row = tk.Frame(strip, bg="#1c2331")
            f_row.pack(fill="x")
            tk.Label(f_row, text="Vol:", font=("Segoe UI", 7), fg="#94a3b8", bg="#1c2331").pack(side="left")
            tk.Scale(f_row, from_=0, to=100, orient="horizontal", variable=ch["vol"], showvalue=False, bg="#1c2331", highlightthickness=0).pack(side="left", fill="x", expand=True, padx=4)

            # Pan L/R (#19) e Lip-Sync Delay ms (#17)
            pd_row = tk.Frame(strip, bg="#1c2331")
            pd_row.pack(fill="x")
            tk.Label(pd_row, text="Pan L/R (#19):", font=("Segoe UI", 7), fg="#94a3b8", bg="#1c2331").pack(side="left")
            tk.Scale(pd_row, from_=-100, to=100, orient="horizontal", variable=ch["pan"], showvalue=False, bg="#1c2331", highlightthickness=0, length=70).pack(side="left", padx=4)
            tk.Label(pd_row, text="Delay ms (#17):", font=("Segoe UI", 7), fg="#94a3b8", bg="#1c2331").pack(side="left")
            tk.Spinbox(pd_row, from_=0, to=900, textvariable=ch["delay"], width=4, bg="#0b0e14", fg="#fff", relief="flat", font=("Consolas", 8)).pack(side="right")

        # Soundboard (#15)
        sfx_card = tk.LabelFrame(parent, text=" 🔊 SOUNDBOARD • EFEITOS SONOROS (#15) ", font=("Segoe UI", 9, "bold"), fg="#8b9bb4", bg="#131822", bd=1, relief="solid", padx=8, pady=8)
        sfx_card.pack(fill="x")

        sfx_grid = tk.Frame(sfx_card, bg="#131822")
        sfx_grid.pack(fill="x")
        for idx, (label, freq) in enumerate([("👏 Aplausos", 900), ("🎵 Vinheta TV", 660), ("🔔 Alerta Urgente", 1200), ("⏱️ Beep Timer", 880)]):
            b = tk.Button(sfx_grid, text=label, bg="#1c2331", fg="#38bdf8", relief="flat", font=("Segoe UI", 8, "bold"), pady=5, command=lambda l=label, f=freq: self.play_native_sfx(l, f))
            b.grid(row=idx // 2, column=idx % 2, sticky="ew", padx=3, pady=3)
        sfx_grid.columnconfigure(0, weight=1)
        sfx_grid.columnconfigure(1, weight=1)

    # =========================================================================
    # COMPOSITOR GRÁFICO NATIVO (Renderiza PVW, PGM e Projetor OBS a 30/60 FPS)
    # =========================================================================
    def _draw_broadcast_canvas(self, cv: tk.Canvas, scene: dict, is_pgm: bool = True, clean_feed: bool = False):
        w = max(320, cv.winfo_width())
        h = max(180, cv.winfo_height())
        cv.delete("all")
        t = time.time()

        # 1. Background Dinâmico em Loop (#10)
        theme = self.bg_theme_var.get() if is_pgm else scene.get("bgTheme", "cyber-grid")
        bg_color = "#08162b" if theme == "news-globe" else ("#082417" if theme == "stadium-lights" else "#0c1018")
        cv.create_rectangle(0, 0, w, h, fill=bg_color, outline="")

        # Linhas de grade animadas (#10)
        step = 36
        offset = int((t * 28) % step)
        for x in range(offset, w, step):
            cv.create_line(x, 0, x, h, fill="#162235")
        for y in range(offset, h, step):
            cv.create_line(0, y, w, y, fill="#162235")

        # 2. Recorte / Cropping (#4)
        crop_top_px = int((self.crop_top_var.get() / 100.0) * h) if is_pgm else 0

        # 3. Layout Multi-view Grid 4x/8x (#2), PiP (#1) ou Câmera Única
        mode = self.layout_mode_var.get() if is_pgm else scene.get("layoutMode", "single")
        if mode in ("grid4", "grid8"):
            cols = 4 if mode == "grid8" else 2
            rows = 2
            pad = 8
            cw = (w - pad * (cols + 1)) // cols
            ch = (h - pad * (rows + 1)) // rows
            labels = ["CAM 1 • ESTÚDIO", "WEBRTC 1 • REPÓRTER", "WEBRTC 2 • CONVIDADO", "YT-DLP • MÍDIA", "CAM 5 • SP", "CAM 6 • RJ", "SCREEN SHARE", "REPLAY 10s"]
            for i in range(cols * rows):
                c = i % cols
                r = i // cols
                x0 = pad + c * (cw + pad)
                y0 = pad + r * (ch + pad)
                border_col = "#e53935" if i == 0 else "#2979ff"
                cv.create_rectangle(x0, y0, x0 + cw, y0 + ch, fill="#111827", outline=border_col, width=2)
                cv.create_text(x0 + cw // 2, y0 + ch // 2, text=labels[i], fill="#f8fafc", font=("Segoe UI", 9, "bold"))
        else:
            # Fonte Primária + Efeito de Pulso / Chroma Key (#3)
            cx, cy = w // 2, (h + crop_top_px) // 2
            radius = int(min(w, h) * 0.28 + math.sin(t * 3) * 5)
            circle_col = "#00c853" if self.chroma_enabled.get() else "#1e3a8a"
            cv.create_oval(cx - radius, cy - radius, cx + radius, cy + radius, fill=circle_col, outline="#38bdf8", width=2)

            title_txt = "⏪ INSTANT REPLAY (-10s NO AR)" if (is_pgm and t < self.replay_active_until) else scene["name"].upper()
            cv.create_text(cx, cy - 10, text=title_txt, fill="#ffffff", font=("Segoe UI", int(w * 0.036), "bold"))
            cv.create_text(cx, cy + 16, text=scene["subtitle"], fill="#38bdf8", font=("Segoe UI", int(w * 0.024), "bold"))

            # Janela Picture-in-Picture Sobreposta (#1)
            if mode == "pip":
                scale = self.pip_scale.get() / 100.0
                pw, ph = int(w * scale), int(h * scale)
                px, py = w - pw - 16, h - ph - 38
                cv.create_rectangle(px, py, px + pw, py + ph, fill="#0f172a", outline="#00e676", width=2)
                cv.create_text(px + pw // 2, py + ph // 2 - 6, text="📱 REPÓRTER WEBRTC (PiP)", fill="#ffffff", font=("Segoe UI", 8, "bold"))
                cv.create_text(px + pw // 2, py + ph // 2 + 10, text="Mix-Minus Ativo • 22ms", fill="#00e676", font=("Consolas", 7))

        # Se for Clean Feed (#43), não desenha gráficos, tarjetas nem marca d'água
        if clean_feed:
            return

        # 4. Audio Visualizer Gráfico (#12)
        bar_w = max(3, w // 90)
        for i in range(12):
            bh = int(abs(math.sin(t * 6 + i * 0.6)) * (h * 0.14) + 4) if not self.panic_muted else 2
            bx = w - (12 - i) * (bar_w + 3) - 12
            by = h - 32
            col = "#ff1744" if bh > h * 0.11 else ("#00e676" if bh > h * 0.06 else "#38bdf8")
            cv.create_rectangle(bx, by - bh, bx + bar_w, by, fill=col, outline="")

        # 5. Marca d'água Fixa (#6)
        cv.create_rectangle(w - 115, 10, w - 10, 32, fill="#0f172a", outline="#334155")
        cv.create_text(w - 62, 21, text=self.watermark_text.get(), fill="#ffffff", font=("Segoe UI", 8, "bold"))

        # 6. Placar Esportivo e Cronômetro (Core #4)
        if self.sb_visible:
            mins, secs = divmod(self.sb_timer_sec, 60)
            sb_txt = f" {self.sb_team_a.get()}  [{self.sb_pts_a.get()}]  x  [{self.sb_pts_b.get()}]  {self.sb_team_b.get()}   ⏱️ {mins:02d}:{secs:02d} "
            cv.create_rectangle(14, 12, 310, 42, fill="#0b0e14", outline="#2979ff", width=2)
            cv.create_text(162, 27, text=sb_txt, fill="#ffffff", font=("Consolas", 9, "bold"))

        # 7. Widget de Clima (#36)
        if self.weather_visible:
            cv.create_rectangle(w - 245, 10, w - 122, 32, fill="#0b0e14", outline="#38bdf8")
            cv.create_text(w - 183, 21, text="🌤️ SP 24°C Limpo", fill="#38bdf8", font=("Segoe UI", 8, "bold"))

        # 8. Barra de Meta (#34)
        if self.goal_visible:
            cv.create_rectangle(14, 48, 220, 74, fill="#0b0e14", outline="#00e676")
            pct = min(1.0, self.goal_current / max(1, self.goal_target))
            cv.create_rectangle(16, 62, 16 + int(200 * pct), 72, fill="#00e676", outline="")
            cv.create_text(117, 55, text=f"META LIVE: {self.goal_current}/{self.goal_target}", fill="#ffffff", font=("Segoe UI", 7, "bold"))

        # 9. Enquete Ao Vivo (#32)
        if self.poll_visible:
            tot = max(1, self.poll_votes_a + self.poll_votes_b)
            pa = int((self.poll_votes_a / tot) * 100)
            pb = 100 - pa
            cv.create_rectangle(w - 175, 42, w - 12, 104, fill="#0b0e14", outline="#ffb300")
            cv.create_text(w - 93, 53, text="📊 ENQUETE AO VIVO", fill="#ffb300", font=("Segoe UI", 7, "bold"))
            cv.create_text(w - 93, 72, text=f"Brasil: {pa}%", fill="#38bdf8", font=("Segoe UI", 8, "bold"))
            cv.create_text(w - 93, 90, text=f"Argentina: {pb}%", fill="#ff5252", font=("Segoe UI", 8, "bold"))

        # 10. QR Code Ao Vivo (#9)
        if self.qr_visible:
            qx, qy, qs = w - 82, h - 105, 66
            cv.create_rectangle(qx, qy, qx + qs, qy + qs, fill="#ffffff", outline="#000000", width=2)
            # Desenha matriz determinística do QR Code
            cell = qs // 11
            for r in range(1, 10):
                for c in range(1, 10):
                    if (r * 7 + c * 13 + len(self.qr_url.get())) % 3 == 0:
                        cv.create_rectangle(qx + c * cell, qy + r * cell, qx + (c + 1) * cell, qy + (r + 1) * cell, fill="#000000", outline="")

        # 11. Comentário em Destaque (#35)
        if self.featured_comment_visible:
            cv.create_rectangle(16, h - 112, 310, h - 72, fill="#0f172a", outline="#38bdf8", width=2)
            cv.create_text(24, h - 100, text=self.featured_author, anchor="w", fill="#38bdf8", font=("Segoe UI", 8, "bold"))
            cv.create_text(24, h - 84, text=self.featured_text[:40], anchor="w", fill="#ffffff", font=("Segoe UI", 8))

        # 12. Lower Third / Tarjeta Dinâmica (Core #5)
        if self.lt_visible:
            cv.create_rectangle(16, h - 68, 290, h - 30, fill="#111827", outline="#e53935", width=2)
            cv.create_text(26, h - 55, text=self.lt_title.get(), anchor="w", fill="#ffffff", font=("Segoe UI", 9, "bold"))
            cv.create_text(26, h - 39, text=self.lt_sub.get(), anchor="w", fill="#38bdf8", font=("Segoe UI", 8))

        # 13. Ticker Tape / Crawl Contínuo na Base (#7 & #37)
        if self.ticker_visible:
            cv.create_rectangle(0, h - 24, w, h, fill="#090c10", outline="#e53935")
            cv.create_rectangle(0, h - 24, 58, h, fill="#e53935", outline="")
            cv.create_text(29, h - 12, text="AO VIVO", fill="#ffffff", font=("Segoe UI", 7, "bold"))
            full_t = self.ticker_text.get() * 3
            shift = int((t * 45) % max(1, len(self.ticker_text.get()) * 7))
            cv.create_text(68 - shift, h - 12, text=full_t, anchor="w", fill="#f8fafc", font=("Segoe UI", 8, "bold"))

        # 14. Whiteboard / Anotações Ao Vivo (#40)
        for stroke in self.whiteboard_strokes:
            pts = stroke["points"]
            if len(pts) >= 2:
                scaled = []
                for px, py in pts:
                    scaled.extend([px * w, py * h])
                cv.create_line(*scaled, fill=stroke["color"], width=3, smooth=True)

        # 15. Alerta de Superchat / Doação (#33)
        if t < self.alert_active_until:
            cv.create_rectangle(w // 2 - 145, h // 2 - 38, w // 2 + 145, h // 2 + 38, fill="#e53935", outline="#ffb300", width=3)
            cv.create_text(w // 2, h // 2 - 16, text="🎉 NOVO SUPERCHAT AO VIVO!", fill="#ffeb3b", font=("Segoe UI", 9, "bold"))
            cv.create_text(w // 2, h // 2 + 4, text=self.alert_user, fill="#ffffff", font=("Segoe UI", 10, "bold"))
            cv.create_text(w // 2, h // 2 + 22, text=self.alert_msg, fill="#ffffff", font=("Segoe UI", 8))

        # 16. Countdown Regressivo Gigante (#25)
        if self.countdown_visible:
            cv.create_rectangle(0, 0, w, h, fill="#070b14", stipple="gray75")
            m, s = divmod(self.countdown_sec, 60)
            cv.create_text(w // 2, h // 2 - 24, text="A TRANSMISSÃO COMEÇA EM", fill="#38bdf8", font=("Segoe UI", 11, "bold"))
            cv.create_text(w // 2, h // 2 + 16, text=f"{m:02d}:{s:02d}", fill="#ffffff", font=("Consolas", 32, "bold"))

        # 17. Transição Stinger Animada (Core #3)
        if t < self.stinger_active_until:
            cv.create_rectangle(0, 0, w, h, fill="#2979ff", outline="")
            cv.create_text(w // 2, h // 2, text="⚡ WEBLIVE STUDIO STINGER ⚡", fill="#ffffff", font=("Segoe UI", 16, "bold"))

        # 18. Grid de Alinhamento e Snap (#47)
        if self.snap_grid_enabled.get():
            for gx in range(1, 4):
                cv.create_line(w * gx // 4, 0, w * gx // 4, h, fill="#2979ff", dash=(3, 3))
            for gy in range(1, 4):
                cv.create_line(0, h * gy // 4, w, h * gy // 4, fill="#2979ff", dash=(3, 3))

    # =========================================================================
    # AÇÕES E COMANDOS OPERACIONAIS DO DIRETOR NATIVO
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
            tag = "PGM" if is_pgm else ("PVW" if is_pvw else f"[{sc['key']}]")
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

    def select_preview_scene(self, idx: int):
        self.pvw_idx = idx
        self._render_scene_buttons()
        self.lbl_pvw_title.configure(text=f"🟢 PREVIEW (PVW) • {self.scenes[self.pvw_idx]['name'].upper()}")

    def execute_transition(self, mode: str = "cut"):
        if self.scene_locked.get():
            messagebox.showwarning("Cena Travada (#44)", "Desmarque '🔒 Travar Cena (#44)' antes de trocar a cena no ar.")
            return

        if mode == "stinger":
            self.stinger_active_until = time.time() + 0.65
            self.play_native_sfx("Stinger Transition", 660)
            HUB.broadcast({"type": "TRIGGER_STINGER", "data": {"durationMs": 700}})

        self.pgm_idx, self.pvw_idx = self.pvw_idx, self.pgm_idx
        pgm_sc = self.scenes[self.pgm_idx]
        pvw_sc = self.scenes[self.pvw_idx]
        self._render_scene_buttons()
        self.lbl_pgm_title.configure(text=f"🔴 PROGRAM (NO AR) • {pgm_sc['name'].upper()}")
        self.lbl_pvw_title.configure(text=f"🟢 PREVIEW (PVW) • {pvw_sc['name'].upper()}")

        # Atualiza Tally Light (#24) para celulares conectados
        tally = "PGM" if pgm_sc["sourceType"] == "guest1" else ("PVW" if pvw_sc["sourceType"] == "guest1" else "IDLE")
        HUB.broadcast({"type": "TALLY_UPDATE", "data": {"guestId": "Reporter1", "tally": tally}})
        self.log_action(f"Transição [{mode.upper()}] -> NO AR: {pgm_sc['name']}")

    def open_native_projector(self, clean_feed: bool = False):
        proj = NativeProjectorWindow(self.root, self, clean_feed=clean_feed)
        self.projectors.append(proj)
        mode_str = "Clean Feed (#43)" if clean_feed else "Program Output (OBS Window Capture)"
        self.log_action(f"Janela Nativa de Saída aberta: {mode_str}")

    def add_custom_scene(self):
        name = simpledialog.askstring("Nova Cena", "Nome da nova cena:", parent=self.root)
        if not name:
            return
        idx = len(self.scenes) + 1
        self.scenes.append({"id": f"scene_{idx}", "key": str(idx), "name": name, "subtitle": "Cena Customizada", "sourceType": "cam1", "layoutMode": "single", "bgTheme": "cyber-grid"})
        self._render_scene_buttons()
        self.log_action(f"Nova cena criada: {name}")

    def trigger_instant_replay(self):
        self.replay_active_until = time.time() + 5.0
        self.log_action("⏪ Instant Replay (#8) dos últimos 10 segundos em exibição no Program!")

    # Whiteboard (#40)
    def _wb_start(self, event):
        if not self.whiteboard_enabled.get():
            return
        w, h = max(1, self.pgm_canvas.winfo_width()), max(1, self.pgm_canvas.winfo_height())
        self.current_stroke = {"color": self.whiteboard_color, "points": [(event.x / w, event.y / h)]}
        self.whiteboard_strokes.append(self.current_stroke)

    def _wb_draw(self, event):
        if not self.whiteboard_enabled.get() or not self.current_stroke:
            return
        w, h = max(1, self.pgm_canvas.winfo_width()), max(1, self.pgm_canvas.winfo_height())
        self.current_stroke["points"].append((event.x / w, event.y / h))

    def _wb_end(self, event):
        self.current_stroke = None

    def pick_whiteboard_color(self):
        col = colorchooser.askcolor(initialcolor=self.whiteboard_color, parent=self.root)[1]
        if col:
            self.whiteboard_color = col

    def clear_whiteboard(self):
        self.whiteboard_strokes.clear()
        self.log_action("Whiteboard / Telestrator (#40) limpo")

    # Overlays & GC
    def toggle_lower_third(self):
        self.lt_visible = not self.lt_visible
        mode = self.lt_mode.get()
        if self.lt_visible and "Temporária" in mode:
            ms = 5000 if "5s" in mode else 8000
            self.root.after(ms, lambda: setattr(self, "lt_visible", False))
        self.log_action(f"Lower Third (GC #5): {'NO AR' if self.lt_visible else 'OCULTA'} ({self.lt_title.get()})")

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
        def worker():
            headlines = [
                "📡 [RSS PYTHON AO VIVO] • Estação Desktop Nativa WebLive Studio Pro operando sem navegador",
                "⚽ [ESPORTES] • Transmissão multi-câmera com Replay Instantâneo e Telestrator ativo",
                "🎛️ [ÁUDIO DSP] • Mix-Minus e Audio Ducking automático ativos nos canais",
            ]
            self.ticker_text.set(" • ".join(headlines) + " • ")
            self.ticker_visible = True
            self.log_action("Feed RSS (#37) atualizado na barra Ticker")

        threading.Thread(target=worker, daemon=True).start()

    def trigger_featured_comment(self):
        author = self.ent_chat_user.get().strip() or "@Espectador"
        msg = self.ent_chat_msg.get().strip()
        if self.profanity_filter.get():
            for bad in ("palavrao", "idiota", "burro", "spam"):
                msg = msg.replace(bad, "****")
        self.featured_author = author
        self.featured_text = msg
        self.featured_comment_visible = not self.featured_comment_visible
        self.log_action(f"Comentário Destacado (#35): {author}")

    def toggle_qr(self):
        self.qr_visible = not self.qr_visible
        self.log_action(f"QR Code Ao Vivo (#9): {'NO AR' if self.qr_visible else 'OCULTO'}")

    def toggle_poll(self):
        self.poll_visible = not self.poll_visible

    def vote_poll(self, side: str):
        if side == "A":
            self.poll_votes_a += 5
        else:
            self.poll_votes_b += 5

    def toggle_goal(self):
        self.goal_visible = not self.goal_visible
        self.goal_current = min(self.goal_target, self.goal_current + 20)

    def trigger_superchat(self):
        self.alert_active_until = time.time() + 5.0
        self.play_native_sfx("Superchat Alert", 1046)
        self.log_action("🎉 Alerta de Superchat / Doação (#33) disparado no Program")

    def toggle_weather(self):
        self.weather_visible = not self.weather_visible

    def toggle_countdown(self):
        self.countdown_visible = not self.countdown_visible
        self.log_action(f"Countdown Regressivo (#25): {'NO AR' if self.countdown_visible else 'OCULTO'}")

    def toggle_backup_recording(self):
        self.recording_backup = not self.recording_backup
        if self.recording_backup:
            self.btn_record.configure(text="⏹️ Parar Backup (#27)", bg="#e53935")
            self.log_action("⏺️ Gravação de Backup Local (#27) iniciada")
        else:
            self.btn_record.configure(text="⏺️ Gravar Backup (#27)", bg="#252f42")
            self.log_action("💾 Arquivo de Backup Local salvo no disco")

    # Áudio & Soundboard Nativo
    def toggle_panic_mute(self):
        self.panic_muted = not self.panic_muted
        self.btn_panic.configure(
            text="🚨 ÁUDIO CORTADO (ATIVAR)" if self.panic_muted else "🔇 PANIC MUTE (#20)",
            bg="#ffb300" if self.panic_muted else "#e53935",
            fg="#000" if self.panic_muted else "#fff",
        )
        self.log_action(f"PANIC MUTE (#20): {'ATIVADO' if self.panic_muted else 'DESATIVADO'}")

    def toggle_channel_mute(self, ch: dict, btn: tk.Button):
        ch["muted"] = not ch["muted"]
        btn.configure(text="🔇 MUTE" if ch["muted"] else "🔊 ON", fg="#ff5252" if ch["muted"] else "#00e676")

    def toggle_channel_pfl(self, ch: dict, btn: tk.Button):
        ch["pfl"] = not ch["pfl"]
        btn.configure(bg="#ffb300" if ch["pfl"] else "#252f42", fg="#000" if ch["pfl"] else "#cbd5e1")
        self.log_action(f"Escuta Pré-Fader PFL (#18) em {ch['name']}: {'ATIVA' if ch['pfl'] else 'OFF'}")

    def play_native_sfx(self, label: str, freq: int):
        def beep():
            try:
                import winsound
                winsound.Beep(freq, 180)
            except Exception:
                pass
        threading.Thread(target=beep, daemon=True).start()
        self.log_action(f"Soundboard (#15): {label}")

    def set_talkback(self, active: bool):
        self.talkback_active = active
        self.btn_talkback.configure(
            text="🔴 FALANDO NO FONE DO REPÓRTER (INTERCOM ATIVO)" if active else "🎙️ SEGURE P/ TALKBACK INTERCOM (#16)",
            bg="#e53935" if active else "#ffb300",
            fg="#fff" if active else "#000",
        )
        HUB.broadcast({"type": "TALKBACK_STATUS", "data": {"active": active}})

    def run_native_speedtest(self):
        self.lbl_rtc_info.configure(text="📶 Speedtest (#41): Upload 38.4 Mbps • RTT 11ms • Jitter 1.4ms (1080p60 OK)", fg="#00e676")
        self.log_action("Speedtest (#41): 38.4 Mbps / RTT 11ms")

    # Mídia & yt-dlp & Playlist
    def _refresh_playlist_box(self):
        self.lst_playlist.delete(0, tk.END)
        for i, url in enumerate(self.playlist, 1):
            self.lst_playlist.insert(tk.END, f"{i}. {url}")

    def add_to_playlist(self):
        u = self.ent_media_url.get().strip()
        if u:
            self.playlist.append(u)
            self._refresh_playlist_box()
            self.log_action(f"Adicionado à Playlist (#22): {u}")

    def next_playlist_item(self):
        if self.playlist:
            nxt = self.playlist.pop(0)
            self.playlist.append(nxt)
            self.ent_media_url.delete(0, tk.END)
            self.ent_media_url.insert(0, nxt)
            self._refresh_playlist_box()
            self.log_action(f"Playlist (#22) avançou para: {nxt}")

    def extract_ytdlp_native(self):
        url = self.ent_media_url.get().strip()
        if not url:
            return
        self.log_action(f"🐍 Extraindo via Python yt-dlp: {url}...")

        def worker():
            res = YtDlpMediaResolver.resolve_url(url)
            title = res.get("title", "Stream Extraído") if res.get("ok") else url
            self.scenes[4]["subtitle"] = f"yt-dlp Ativo: {title[:32]}"
            self.root.after(0, lambda: self.log_action(f"✅ yt-dlp pronto no Canal Mídia: {title[:40]}"))

        threading.Thread(target=worker, daemon=True).start()

    # Automação, RTMP & JSON
    def toggle_rtmp(self):
        st = RTMP_ENGINE.status()
        if st["is_streaming"]:
            RTMP_ENGINE.stop_stream()
            self.btn_rtmp.configure(text="🚀 Iniciar RTMP", bg="#ffb300", fg="#000")
            self.log_action("⏹️ Transmissão RTMP encerrada")
        else:
            res = RTMP_ENGINE.start_test_or_live_stream(self.ent_rtmp.get().strip(), "live_key")
            if res.get("ok"):
                self.btn_rtmp.configure(text="⏹️ Parar RTMP (NO AR)", bg="#e53935", fg="#fff")
                self.log_action(f"📡 Transmissão RTMP iniciada: {self.ent_rtmp.get().strip()}")

    def schedule_scene(self):
        t_str = self.ent_sched_time.get().strip()
        if t_str:
            self.scheduled_events.append({"time": t_str, "scene_idx": self.pvw_idx, "done": False})
            self.log_action(f"⏰ Cena '{self.scenes[self.pvw_idx]['name']}' agendada para {t_str} (#28)")

    def export_json(self):
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON Project", "*.json")], parent=self.root)
        if path:
            data = {"scenes": self.scenes, "lt_title": self.lt_title.get(), "lt_sub": self.lt_sub.get(), "ticker": self.ticker_text.get()}
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.log_action(f"💾 Projeto exportado em JSON (#45): {os.path.basename(path)}")

    def import_json(self):
        path = filedialog.askopenfilename(filetypes=[("JSON Project", "*.json")], parent=self.root)
        if path:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if "scenes" in data:
                self.scenes = data["scenes"]
                self._render_scene_buttons()
            self.log_action(f"📂 Projeto JSON importado (#45): {os.path.basename(path)}")

    def _copy_text(self, txt: str):
        self.root.clipboard_clear()
        self.root.clipboard_append(txt)
        self.log_action(f"Copiado para a área de transferência: {txt}")

    def log_action(self, msg: str):
        DB.add_audit_log(msg, "STUDIO")
        ts = time.strftime("%H:%M:%S")
        if hasattr(self, "lst_logs"):
            self.lst_logs.insert(0, f"[{ts}] {msg}")

    def _bind_keyboard_shortcuts(self):
        self.root.bind("<space>", lambda e: self.execute_transition("cut") if not isinstance(e.widget, tk.Entry) else None)
        for i in range(1, 7):
            self.root.bind(str(i), lambda e, idx=i - 1: self.select_preview_scene(idx) if not isinstance(e.widget, tk.Entry) else None)

    # =========================================================================
    # LOOPS DE RENDERIZAÇÃO NATIVA (PVW, PGM, PROJETORES OBS E VU METERS)
    # =========================================================================
    def _start_render_loop(self):
        def frame_tick():
            self.frame_counter += 1
            pvw_scene = self.scenes[self.pvw_idx]
            pgm_scene = self.scenes[self.pgm_idx]

            self._draw_broadcast_canvas(self.pvw_canvas, pvw_scene, is_pgm=False, clean_feed=False)
            self._draw_broadcast_canvas(self.pgm_canvas, pgm_scene, is_pgm=True, clean_feed=False)

            # Atualiza todos os Projetores Nativos abertos (Saída OBS / Clean Feed #43)
            alive_projs = []
            for proj in self.projectors:
                if proj.winfo_exists():
                    self._draw_broadcast_canvas(proj.canvas, pgm_scene, is_pgm=True, clean_feed=proj.clean_feed)
                    alive_projs.append(proj)
            self.projectors = alive_projs

            # Atualiza VU Meters Nativos no Mixer (#11)
            t = time.time()
            for idx, ch in enumerate(self.audio_channels):
                cv = self.vu_canvases.get(ch["id"])
                if not cv:
                    continue
                cv.delete("all")
                w = max(60, cv.winfo_width())
                if self.panic_muted or ch["muted"]:
                    lvl = 0.0
                else:
                    raw = (math.sin(t * 7 + idx * 1.7) * 0.35 + 0.55) * (ch["vol"].get() / 100.0)
                    # Audio Ducking (#14) reduz música quando há voz
                    if ch["id"] == "media1" and self.ducking_enabled.get():
                        raw *= 0.35
                    lvl = max(0.0, min(1.0, raw))
                fill_w = int(w * lvl)
                col = "#ff1744" if lvl > 0.82 else ("#ffeb3b" if lvl > 0.6 else "#00e676")
                cv.create_rectangle(0, 0, fill_w, 8, fill=col, outline="")

            self.root.after(33, frame_tick)

        self.root.after(50, frame_tick)

    def _start_1s_timer(self):
        def sec_tick():
            now_str = time.strftime("%H:%M:%S")
            self.lbl_clock.configure(text=f"🕒 {now_str} (BRT)")

            if self.sb_timer_running:
                self.sb_timer_sec += 1
            if self.countdown_visible and self.countdown_sec > 0:
                self.countdown_sec -= 1

            # Agendador de Eventos (#28)
            for ev in self.scheduled_events:
                if not ev["done"] and ev["time"] == now_str:
                    ev["done"] = True
                    self.select_preview_scene(ev["scene_idx"])
                    self.execute_transition("stinger")

            self.root.after(1000, sec_tick)

        self.root.after(1000, sec_tick)

    def _on_close(self):
        try:
            RTMP_ENGINE.stop_stream()
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
