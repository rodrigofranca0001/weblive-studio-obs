#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
WebLive Studio Pro v2.0 — Estação Desktop Nativa Python (Tkinter Broadcast GUI)
===============================================================================
Interface Gráfica Profissional em Python (sem terminal) para controle da
Estação de Transmissão:
  - Inicia automaticamente o Servidor Broadcast Python Multithreaded (`weblive_server.py`)
  - Exibe Telemetria Ao Vivo (Clientes Conectados, IP da Rede Local p/ Celulares, Status SQLite)
  - Controle de Transmissão Direta RTMP / SRT (YouTube Live, Twitch, Facebook, Custom RTMP)
  - Extrator Rápido de Mídia `yt-dlp` integrado na janela desktop
  - Botões de 1 clique para:
      * 🎛️ Painel do Diretor (Director Interface)
      * 📺 Tela OBS Studio (Browser Source 1920x1080)
      * 🧼 Saída Clean Feed (Gravação limpa sem GC/Tarjetas)
      * 📱 Link do Repórter WebRTC (com IP da rede local pronto para celular)
  - Visualizador em tempo real dos Logs de Auditoria SQLite (#49)
"""

import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk
import webbrowser

from weblive_server import DB, HUB, RTMP_ENGINE, WebLivePythonServer, YtDlpMediaResolver, get_lan_ip


class WebLiveStudioDesktopApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("🐍 WebLive Studio Pro v2.0 — Plataforma Python de Transmissão Ao Vivo & OBS")
        self.root.geometry("820x620")
        self.root.configure(bg="#0b0e14")
        self.root.resizable(False, False)

        self.server = WebLivePythonServer(port=3000)
        self.active_port = self.server.start()
        self.lan_ip = get_lan_ip()

        self._build_ui()
        self._start_telemetry_loop()

        # Abre automaticamente o Painel do Diretor após 600ms
        self.root.after(600, self.open_director)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        # Top Header Broadcast
        header = tk.Frame(self.root, bg="#131822", height=68, highlightthickness=1, highlightbackground="#2b3548")
        header.pack(fill="x", side="top")

        lbl_title = tk.Label(
            header,
            text="🔴 WEBLIVE STUDIO PRO v2.0 • PYTHON BROADCAST ENGINE",
            font=("Segoe UI", 13, "bold"),
            fg="#ff5252",
            bg="#131822",
        )
        lbl_title.pack(anchor="w", padx=18, pady=(10, 2))

        self.lbl_subtitle = tk.Label(
            header,
            text=f"Servidor Python Ativo: http://localhost:{self.active_port}   |   IP Rede Local (Celular WebRTC): http://{self.lan_ip}:{self.active_port}",
            font=("Consolas", 9, "bold"),
            fg="#38bdf8",
            bg="#131822",
        )
        self.lbl_subtitle.pack(anchor="w", padx=18, pady=(0, 10))

        # Container Principal
        main_frame = tk.Frame(self.root, bg="#0b0e14", padx=18, pady=14)
        main_frame.pack(fill="both", expand=True)

        # 1. Bloco de Ações Rápidas (1 Clique)
        actions_card = tk.LabelFrame(
            main_frame,
            text=" 🎬 CENTRAL DE OPERAÇÃO RÁPIDA (1 CLIQUE) ",
            font=("Segoe UI", 9, "bold"),
            fg="#8b9bb4",
            bg="#131822",
            bd=1,
            relief="solid",
            padx=14,
            pady=12,
        )
        actions_card.pack(fill="x", pady=(0, 12))

        btn_director = tk.Button(
            actions_card,
            text="🎛️ ABRIR PAINEL DO DIRETOR (SWITCHER COMPLETO)",
            font=("Segoe UI", 10, "bold"),
            bg="#2979ff",
            fg="#ffffff",
            activebackground="#1c54b2",
            activeforeground="#ffffff",
            relief="flat",
            cursor="hand2",
            height=2,
            command=self.open_director,
        )
        btn_director.pack(fill="x", pady=(0, 8))

        row_btns = tk.Frame(actions_card, bg="#131822")
        row_btns.pack(fill="x")

        tk.Button(
            row_btns,
            text="📺 Abrir Tela OBS (Output 1080p)",
            font=("Segoe UI", 9, "bold"),
            bg="#e53935",
            fg="#ffffff",
            relief="flat",
            cursor="hand2",
            height=2,
            command=self.open_output,
        ).pack(side="left", fill="x", expand=True, padx=(0, 6))

        tk.Button(
            row_btns,
            text="🧼 Abrir Saída Clean Feed (#43)",
            font=("Segoe UI", 9, "bold"),
            bg="#252f42",
            fg="#ffffff",
            relief="flat",
            cursor="hand2",
            height=2,
            command=self.open_clean_feed,
        ).pack(side="left", fill="x", expand=True, padx=6)

        tk.Button(
            row_btns,
            text="📱 Abrir Link Repórter WebRTC",
            font=("Segoe UI", 9, "bold"),
            bg="#00c853",
            fg="#000000",
            relief="flat",
            cursor="hand2",
            height=2,
            command=self.open_guest,
        ).pack(side="left", fill="x", expand=True, padx=(6, 0))

        # Linha de cópia rápida para Browser Source do OBS e Celular
        urls_frame = tk.Frame(actions_card, bg="#131822")
        urls_frame.pack(fill="x", pady=(10, 0))

        tk.Label(urls_frame, text="URL OBS Browser Source:", font=("Segoe UI", 9), fg="#cbd5e1", bg="#131822").pack(side="left")
        self.ent_obs_url = tk.Entry(urls_frame, font=("Consolas", 10, "bold"), bg="#1c2331", fg="#38bdf8", relief="flat", width=36)
        self.ent_obs_url.insert(0, f"http://localhost:{self.active_port}/output.html")
        self.ent_obs_url.configure(state="readonly")
        self.ent_obs_url.pack(side="left", padx=8)

        tk.Button(
            urls_frame,
            text="📋 Copiar URL OBS",
            font=("Segoe UI", 8, "bold"),
            bg="#2b3548",
            fg="#ffffff",
            relief="flat",
            cursor="hand2",
            command=self.copy_obs_url,
        ).pack(side="left", padx=(0, 8))

        tk.Button(
            urls_frame,
            text="📱 Copiar Link Celular (LAN)",
            font=("Segoe UI", 8, "bold"),
            bg="#2b3548",
            fg="#00e676",
            relief="flat",
            cursor="hand2",
            command=self.copy_guest_lan_url,
        ).pack(side="left")

        # 2. Bloco Duplo: Transmissão RTMP / FFmpeg + Extrator Python yt-dlp
        mid_frame = tk.Frame(main_frame, bg="#0b0e14")
        mid_frame.pack(fill="x", pady=(0, 12))

        # Coluna Esquerda: Encoder RTMP / FFmpeg Nativo
        rtmp_card = tk.LabelFrame(
            mid_frame,
            text=" 📡 TRANSMISSÃO DIRETA RTMP / FFMPEG (YOUTUBE / TWITCH) ",
            font=("Segoe UI", 9, "bold"),
            fg="#8b9bb4",
            bg="#131822",
            bd=1,
            relief="solid",
            padx=12,
            pady=10,
        )
        rtmp_card.pack(side="left", fill="both", expand=True, padx=(0, 6))

        tk.Label(rtmp_card, text="Servidor RTMP:", font=("Segoe UI", 8), fg="#94a3b8", bg="#131822").pack(anchor="w")
        self.ent_rtmp_url = tk.Entry(rtmp_card, font=("Consolas", 9), bg="#1c2331", fg="#ffffff", insertbackground="#ffffff", relief="flat")
        self.ent_rtmp_url.insert(0, "rtmp://a.rtmp.youtube.com/live2")
        self.ent_rtmp_url.pack(fill="x", pady=(2, 6))

        tk.Label(rtmp_card, text="Chave de Transmissão (Stream Key):", font=("Segoe UI", 8), fg="#94a3b8", bg="#131822").pack(anchor="w")
        self.ent_stream_key = tk.Entry(rtmp_card, font=("Consolas", 9), bg="#1c2331", fg="#ffffff", insertbackground="#ffffff", show="*", relief="flat")
        self.ent_stream_key.insert(0, "xxxx-xxxx-xxxx-xxxx")
        self.ent_stream_key.pack(fill="x", pady=(2, 8))

        self.btn_rtmp_toggle = tk.Button(
            rtmp_card,
            text="🚀 Iniciar Pipeline RTMP Python",
            font=("Segoe UI", 9, "bold"),
            bg="#ffb300",
            fg="#000000",
            relief="flat",
            cursor="hand2",
            command=self.toggle_rtmp_stream,
        )
        self.btn_rtmp_toggle.pack(fill="x")

        # Coluna Direita: Extrator Nativo yt-dlp Python
        ytdlp_card = tk.LabelFrame(
            mid_frame,
            text=" 🎞️ EXTRATOR PYTHON YT-DLP (YOUTUBE / IG / TWITCH DIRECT) ",
            font=("Segoe UI", 9, "bold"),
            fg="#8b9bb4",
            bg="#131822",
            bd=1,
            relief="solid",
            padx=12,
            pady=10,
        )
        ytdlp_card.pack(side="left", fill="both", expand=True, padx=(6, 0))

        tk.Label(ytdlp_card, text="URL do Vídeo ou Live Externa:", font=("Segoe UI", 8), fg="#94a3b8", bg="#131822").pack(anchor="w")
        self.ent_ytdlp_url = tk.Entry(ytdlp_card, font=("Consolas", 9), bg="#1c2331", fg="#ffffff", insertbackground="#ffffff", relief="flat")
        self.ent_ytdlp_url.insert(0, "https://www.youtube.com/watch?v=jfKfPfyJRdk")
        self.ent_ytdlp_url.pack(fill="x", pady=(2, 6))

        self.lbl_ytdlp_status = tk.Label(
            ytdlp_card,
            text="Extrai o stream MP4/HLS limpo via Python yt-dlp e envia ao Ar.",
            font=("Segoe UI", 8),
            fg="#38bdf8",
            bg="#131822",
            anchor="w",
        )
        self.lbl_ytdlp_status.pack(fill="x", pady=(0, 8))

        tk.Button(
            ytdlp_card,
            text="⚡ Extrair c/ yt-dlp e Jogar no Ar (OBS)",
            font=("Segoe UI", 9, "bold"),
            bg="#2979ff",
            fg="#ffffff",
            relief="flat",
            cursor="hand2",
            command=self.extract_and_play_ytdlp,
        ).pack(fill="x")

        # 3. Painel Inferior: Monitor de Auditoria SQLite & Telemetria Python (#49)
        log_card = tk.LabelFrame(
            main_frame,
            text=" 📋 BANCO DE DADOS SQLITE NATIVO • LOG DE AUDITORIA & TELEMETRIA EM TEMPO REAL (#49) ",
            font=("Segoe UI", 9, "bold"),
            fg="#8b9bb4",
            bg="#131822",
            bd=1,
            relief="solid",
            padx=12,
            pady=8,
        )
        log_card.pack(fill="both", expand=True)

        self.lbl_telemetry = tk.Label(
            log_card,
            text="Clientes SSE Conectados: 0  |  Banco SQLite: weblive_studio.db (OK)  |  Status RTMP: Standby",
            font=("Consolas", 9, "bold"),
            fg="#00e676",
            bg="#131822",
            anchor="w",
        )
        self.lbl_telemetry.pack(fill="x", pady=(0, 6))

        self.txt_logs = tk.Listbox(
            log_card,
            font=("Consolas", 9),
            bg="#090c10",
            fg="#cbd5e1",
            selectbackground="#2979ff",
            relief="flat",
            height=7,
        )
        self.txt_logs.pack(fill="both", expand=True)

    def open_director(self):
        webbrowser.open(f"http://localhost:{self.active_port}/index.html")

    def open_output(self):
        webbrowser.open(f"http://localhost:{self.active_port}/output.html")

    def open_clean_feed(self):
        webbrowser.open(f"http://localhost:{self.active_port}/output.html?clean=1")

    def open_guest(self):
        webbrowser.open(f"http://localhost:{self.active_port}/guest.html?guest=Reporter1")

    def copy_obs_url(self):
        url = f"http://localhost:{self.active_port}/output.html"
        self.root.clipboard_clear()
        self.root.clipboard_append(url)
        messagebox.showinfo("URL OBS Copiada", f"Copiado para a área de transferência:\n{url}")

    def copy_guest_lan_url(self):
        url = f"http://{self.lan_ip}:{self.active_port}/guest.html?guest=Reporter1"
        self.root.clipboard_clear()
        self.root.clipboard_append(url)
        messagebox.showinfo("Link do Repórter Copiado", f"Envie este link para o celular na mesma rede:\n{url}")

    def toggle_rtmp_stream(self):
        st = RTMP_ENGINE.status()
        if st["is_streaming"]:
            RTMP_ENGINE.stop_stream()
            self.btn_rtmp_toggle.configure(text="🚀 Iniciar Pipeline RTMP Python", bg="#ffb300", fg="#000000")
        else:
            url = self.ent_rtmp_url.get().strip()
            key = self.ent_stream_key.get().strip()
            res = RTMP_ENGINE.start_test_or_live_stream(url, key)
            if res.get("ok"):
                self.btn_rtmp_toggle.configure(text="⏹️ Parar Transmissão RTMP Python (NO AR)", bg="#e53935", fg="#ffffff")
            else:
                messagebox.showwarning("Aviso RTMP", res.get("message", "Erro ao iniciar stream"))

    def extract_and_play_ytdlp(self):
        target_url = self.ent_ytdlp_url.get().strip()
        if not target_url:
            return
        self.lbl_ytdlp_status.configure(text="⏳ Extraindo stream direto via Python yt-dlp...", fg="#ffb300")

        def worker():
            info = YtDlpMediaResolver.resolve_url(target_url)
            if info.get("ok"):
                title = info.get("title", "Vídeo")[:42]
                play_url = info.get("direct_url") or target_url
                HUB.broadcast({"type": "WEBMEDIA_CONTROL", "data": {"action": "play", "url": play_url, "title": title}})
                DB.add_audit_log(f"yt-dlp enviou ao ar: {title}", "MEDIA")
                self.root.after(0, lambda: self.lbl_ytdlp_status.configure(text=f"✅ No Ar: {title}", fg="#00e676"))
            else:
                HUB.broadcast({"type": "WEBMEDIA_CONTROL", "data": {"action": "play", "url": target_url}})
                self.root.after(0, lambda: self.lbl_ytdlp_status.configure(text="▶ Enviado em modo Embed Padrão para o OBS", fg="#38bdf8"))

        threading.Thread(target=worker, daemon=True).start()

    def _start_telemetry_loop(self):
        def update_ui():
            clients = HUB.client_count()
            rtmp_st = RTMP_ENGINE.status()
            rtmp_txt = f"TRANSMITINDO ({rtmp_st['uptime_sec']}s)" if rtmp_st["is_streaming"] else "Standby"
            self.lbl_telemetry.configure(
                text=f"Clientes Conectados (Abas/OBS/Mobile): {clients}   |   Banco SQLite: OK   |   Encoder RTMP: {rtmp_txt}"
            )

            logs = DB.get_recent_logs(15)
            self.txt_logs.delete(0, tk.END)
            for item in logs:
                self.txt_logs.insert(tk.END, f"[{item['time']}] [{item['category']}] {item['msg']}")

            self.root.after(1500, update_ui)

        self.root.after(500, update_ui)

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
    WebLiveStudioDesktopApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
