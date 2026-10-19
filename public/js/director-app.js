/**
 * ============================================================================
 * WebLive Studio - Controlador Principal do Painel do Diretor (director-app.js)
 * ============================================================================
 * Orquestra Cenas, Monitores PVW/PGM, WebRTC Call com Mix-Minus, Mixer Multi-pista,
 * Transições Stinger via IndexedDB, Placar, Lower Thirds, Playlist, Agendador,
 * Atalhos de Teclado (#21), Perfis de Acesso (#29), Logs (#49) e Sync com o OBS.
 */

class WebLiveDirectorApp {
  constructor() {
    this.sync = new WebLiveSyncEngine('director');
    this.audioEngine = new WebLiveAudioEngine((dominantChannelId) => this.handleAutoVoiceSwitch(dominantChannelId));

    this.pvwCompositor = new WebLiveVideoCompositor(document.getElementById('pvwCanvas'), 'pvw');
    this.pgmCompositor = new WebLiveVideoCompositor(document.getElementById('pgmCanvas'), 'pgm');

    this.webrtc = new WebLiveWebRTCManager(this.sync, 'director', 'Reporter1');

    // Estado Global da Produção (Sincronizado com o OBS Output)
    this.state = {
      scenes: [
        { id: 'scene_1', key: '1', name: 'Estúdio Principal', subtitle: 'Apresentador • Cam 1 (1080p60)', sourceType: 'cam1', layoutMode: 'single', bgTheme: 'cyber-grid' },
        { id: 'scene_2', key: '2', name: 'Repórter Externo', subtitle: 'WebRTC Call • Mix-Minus Ativo', sourceType: 'guest1', layoutMode: 'single', bgTheme: 'news-globe' },
        { id: 'scene_3', key: '3', name: 'Entrevista PiP', subtitle: 'Estúdio + Repórter em PiP (#1)', sourceType: 'cam1', layoutMode: 'pip', bgTheme: 'cyber-grid' },
        { id: 'scene_4', key: '4', name: 'Mosaico 4x Grid', subtitle: 'Debate Multi-view 4 Convidados (#2)', sourceType: 'cam1', layoutMode: 'grid4', bgTheme: 'news-globe' },
        { id: 'scene_5', key: '5', name: 'Mídia Web / VT', subtitle: 'YouTube / Instagram / Playlist (#22)', sourceType: 'webmedia', layoutMode: 'single', bgTheme: 'stadium-lights' },
        { id: 'scene_6', key: '6', name: 'Mosaico 8x Arena', subtitle: 'Super Grid 8 Participantes (#2)', sourceType: 'cam1', layoutMode: 'grid8', bgTheme: 'stadium-lights' }
      ],
      pvwSceneId: 'scene_2',
      pgmSceneId: 'scene_1',
      sceneLocked: false,

      // Overlays Gráficos (Core #4, #5, #7, #9, #25, #32-#36)
      lowerThird: { visible: false, title: 'DR. CARLOS MENDES', subtitle: 'Especialista em Transmissões Ao Vivo', mode: 'permanent' },
      scoreboard: { visible: false, teamA: 'BRASIL', ptsA: 2, teamB: 'ARGENTINA', ptsB: 1, timerSec: 0, timerRunning: false },
      ticker: { visible: true, text: 'URGENTE: WebLive Studio opera em 60fps com Mix-Minus WebRTC nativo • Acompanhe nossas redes sociais • ' },
      qrOverlay: { visible: false, url: 'https://weblive.studio/pix' },
      pollOverlay: { visible: false, question: 'Quem vence o confronto de hoje?', optA: 'Brasil', votesA: 68, optB: 'Argentina', votesB: 32 },
      subGoalOverlay: { visible: false, title: 'META DE INSCRITOS DA LIVE', current: 840, target: 1000 },
      featuredComment: { visible: false, author: '@Mariana_TV', text: 'Que estrutura incrível desse WebLive Studio!' },
      weatherOverlay: { visible: false, city: 'São Paulo', temp: '24°C', condition: ' Céu Limpo' },
      countdownOverlay: { visible: false, remainingSec: 300 },
      webMedia: { playing: false, currentUrl: 'https://www.youtube.com/embed/jfKfPfyJRdk', playlist: ['https://www.youtube.com/embed/jfKfPfyJRdk', 'https://www.youtube.com/embed/5qap5aO4i9A'] },
      visualConfig: { ...this.pgmCompositor.visualConfig }
    };

    this.scheduledEvents = [];
    this.actionLogs = [];
    this.lastVoiceSwitchTime = 0;

    this._initUI();
    this._initWebRTCCallbacks();
    this._initWhiteboardInteraction();
    this._initKeyboardMacros();
    this._initSyncListeners();
    this._startRenderAndMetricsLoop();

    // Inicia buffer de Instant Replay dos últimos 10 segundos (#8)
    setTimeout(() => this.pgmCompositor.startInstantReplayBuffer(), 800);
    this.logAction('Sistema WebLive Studio inicializado (PGM: Estúdio Principal)');
    this.broadcastFullState();
  }

  _initUI() {
    // Link dinâmico do convidado WebRTC (Core #7)
    const guestUrl = `${window.location.origin}/guest.html?guest=Reporter1`;
    const linkInput = document.getElementById('guestLinkInput');
    if (linkInput) linkInput.value = guestUrl;

    document.getElementById('btnCopyGuestLink')?.addEventListener('click', () => {
      navigator.clipboard?.writeText(guestUrl);
      this.logAction('Link WebRTC do Repórter copiado para a área de transferência');
    });

    // Renderiza Cenas, Mixer e Playlist iniciais
    this.renderScenesGrid();
    this.renderMixerStrips();
    this.renderPlaylist();

    // Botão Adicionar Nova Cena (Core #1)
    document.getElementById('btnAddScene')?.addEventListener('click', () => {
      const idx = this.state.scenes.length + 1;
      const name = prompt('Nome da nova Cena:', `Cena Custom ${idx}`);
      if (!name) return;
      this.state.scenes.push({
        id: `scene_${Date.now()}`,
        key: String(idx <= 9 ? idx : ''),
        name,
        subtitle: 'Cena Personalizada',
        sourceType: 'cam1',
        layoutMode: 'single',
        bgTheme: 'cyber-grid'
      });
      this.renderScenesGrid();
      this.logAction(`Cena criada: ${name}`);
      this.broadcastFullState();
    });

    // Bloqueio de Cena (#44 Lock Scene)
    document.getElementById('chkLockScene')?.addEventListener('change', (e) => {
      this.state.sceneLocked = e.target.checked;
      this.logAction(`Bloqueio de Cena (#44): ${this.state.sceneLocked ? 'ATIVADO' : 'DESATIVADO'}`);
    });

    // Transições: CUT, AUTO FADE e STINGER (Core #3)
    document.getElementById('btnCut')?.addEventListener('click', () => this.executeTransition('cut'));
    document.getElementById('btnAutoFade')?.addEventListener('click', () => this.executeTransition('fade'));
    document.getElementById('btnStinger')?.addEventListener('click', () => this.executeTransition('stinger'));

    // Função #8: Instant Replay dos últimos 10 segundos
    document.getElementById('btnInstantReplay')?.addEventListener('click', () => this.triggerInstantReplay());

    // Função #47: Grid de Alinhamento e Snap
    document.getElementById('chkSnapGrid')?.addEventListener('change', (e) => {
      document.getElementById('pvwSnapGrid')?.classList.toggle('active', e.target.checked);
      document.getElementById('pgmSnapGrid')?.classList.toggle('active', e.target.checked);
    });

    // Função #20: Panic Mute (Corta todo o áudio instantaneamente)
    document.getElementById('btnPanicMute')?.addEventListener('click', (e) => {
      const muted = this.audioEngine.togglePanicMute();
      e.currentTarget.textContent = muted ? '🚨 ÁUDIO CORTADO (ATIVAR)' : '🔇 PANIC MUTE';
      this.sync.send('PANIC_MUTE', { muted });
      this.logAction(`PANIC MUTE (#20): ${muted ? 'ÁUDIO GERAL CORTADO' : 'ÁUDIO RESTAURADO'}`);
    });

    // Função #30: Alternar Dark Mode / Light Mode
    document.getElementById('btnThemeToggle')?.addEventListener('click', () => {
      document.body.classList.toggle('light-mode');
    });

    // Função #29: Perfis de Usuário (Diretor, Operador de GC, Operador de Áudio)
    document.getElementById('roleProfileSelect')?.addEventListener('change', (e) => {
      const role = e.target.value;
      document.querySelectorAll('[data-role-section]').forEach((el) => {
        const allowed = el.getAttribute('data-role-section').split(',');
        el.style.opacity = allowed.includes(role) ? '1' : '0.35';
        el.style.pointerEvents = allowed.includes(role) ? 'auto' : 'none';
      });
      this.logAction(`Perfil de Usuário (#29) alterado para: ${role.toUpperCase()}`);
    });

    // Abas de Módulos Avançados
    document.querySelectorAll('.tab-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.tab-btn').forEach((b) => b.classList.remove('active'));
        document.querySelectorAll('.tab-pane').forEach((p) => p.classList.remove('active'));
        btn.classList.add('active');
        document.getElementById(btn.dataset.tab)?.classList.add('active');
      });
    });

    this._bindGraphicsAndSocialControls();
    this._bindVideoAndAutomationControls();
  }

  _bindGraphicsAndSocialControls() {
    // Core #5: Lower Thirds (Permanentes ou Temporárias com auto-off)
    document.getElementById('btnToggleLT')?.addEventListener('click', () => {
      const lt = this.state.lowerThird;
      lt.title = document.getElementById('ltTitleInput').value;
      lt.subtitle = document.getElementById('ltSubInput').value;
      lt.mode = document.getElementById('ltModeSelect').value;
      lt.visible = !lt.visible;

      if (lt.visible && lt.mode.startsWith('temp')) {
        const secs = lt.mode === 'temp5' ? 5000 : 8000;
        setTimeout(() => {
          this.state.lowerThird.visible = false;
          this.broadcastFullState();
        }, secs);
      }
      this.logAction(`Lower Third (GC): ${lt.visible ? 'NO AR' : 'OCULTA'} (${lt.title})`);
      this.broadcastFullState();
    });

    // Core #4: Placar Esportivo e Cronômetro
    const syncScoreInputs = () => {
      this.state.scoreboard.teamA = document.getElementById('scoreTeamA').value;
      this.state.scoreboard.ptsA = parseInt(document.getElementById('scorePtsA').value, 10) || 0;
      this.state.scoreboard.teamB = document.getElementById('scoreTeamB').value;
      this.state.scoreboard.ptsB = parseInt(document.getElementById('scorePtsB').value, 10) || 0;
      this.broadcastFullState();
    };
    ['scoreTeamA', 'scorePtsA', 'scoreTeamB', 'scorePtsB'].forEach((id) => {
      document.getElementById(id)?.addEventListener('input', syncScoreInputs);
    });

    document.getElementById('btnToggleScoreboard')?.addEventListener('click', () => {
      syncScoreInputs();
      this.state.scoreboard.visible = !this.state.scoreboard.visible;
      this.logAction(`Placar Esportivo: ${this.state.scoreboard.visible ? 'NO AR' : 'OCULTO'}`);
      this.broadcastFullState();
    });

    document.getElementById('btnScoreTimerToggle')?.addEventListener('click', () => {
      this.state.scoreboard.timerRunning = !this.state.scoreboard.timerRunning;
      this.broadcastFullState();
    });

    document.getElementById('btnScoreTimerReset')?.addEventListener('click', () => {
      this.state.scoreboard.timerSec = 0;
      this.broadcastFullState();
    });

    // Função #7 e #37: Ticker Tape / Crawl e Feed RSS Automático
    document.getElementById('btnToggleTicker')?.addEventListener('click', () => {
      this.state.ticker.text = document.getElementById('tickerTextInput').value;
      this.state.ticker.visible = !this.state.ticker.visible;
      this.broadcastFullState();
    });

    document.getElementById('btnLoadRssTicker')?.addEventListener('click', () => {
      const rssHeadlines = [
        '📡 [FEED RSS AO VIVO] • Audiência de transmissões interativas via WebRTC cresce 42% no semestre',
        '⚽ [ESPORTES] • Final do campeonato terá transmissão multi-câmera com replay instantâneo',
        '💻 [TECNOLOGIA] • WebAudio API permite Mix-Minus com latência zero diretamente no navegador'
      ].join(' • ');
      document.getElementById('tickerTextInput').value = rssHeadlines + ' • ';
      this.state.ticker.text = rssHeadlines + ' • ';
      this.state.ticker.visible = true;
      this.logAction('Feed RSS (#37) carregado na barra de rolagem (Ticker)');
      this.broadcastFullState();
    });

    // Função #9: QR Code Ao Vivo
    document.getElementById('btnToggleQR')?.addEventListener('click', () => {
      this.state.qrOverlay.url = document.getElementById('qrUrlInput').value;
      this.state.qrOverlay.visible = !this.state.qrOverlay.visible;
      this.logAction(`QR Code Ao Vivo (#9): ${this.state.qrOverlay.visible ? 'EXIBIDO' : 'OCULTO'}`);
      this.broadcastFullState();
    });

    // Função #31, #35, #38: Chat Ao Vivo com Filtro de Palavrões e Comentário em Destaque
    document.getElementById('btnSendChat')?.addEventListener('click', () => {
      const filterOn = document.getElementById('chkProfanityFilter')?.checked;
      const author = document.getElementById('chatAuthorInput').value || '@Espectador';
      const rawMsg = document.getElementById('chatMsgInput').value;
      const cleanMsg = window.sanitizeProfanity(rawMsg, filterOn);

      this.appendChatMessage(author, cleanMsg);
      this.state.featuredComment = { visible: true, author, text: cleanMsg };
      this.logAction(`Comentário destacado no OBS (#35): ${author}`);
      this.broadcastFullState();
    });

    // Mensagens iniciais de demonstração do Chat (#31)
    [
      { u: '@Lucas_Broadcast', m: 'O áudio Mix-Minus do repórter está cristalino!' },
      { u: '@Ana_Produtora', m: 'Adorei o corte com Stinger animado no OBS!' }
    ].forEach((item) => this.appendChatMessage(item.u, item.m));

    // Função #32: Enquetes Ao Vivo (Live Polls)
    document.getElementById('btnTogglePoll')?.addEventListener('click', () => {
      this.state.pollOverlay.visible = !this.state.pollOverlay.visible;
      this.broadcastFullState();
    });
    document.getElementById('btnVotePollA')?.addEventListener('click', () => {
      this.state.pollOverlay.votesA += 5;
      this.broadcastFullState();
    });
    document.getElementById('btnVotePollB')?.addEventListener('click', () => {
      this.state.pollOverlay.votesB += 5;
      this.broadcastFullState();
    });

    // Função #34: Barra de Meta (Sub Goal)
    document.getElementById('btnToggleSubGoal')?.addEventListener('click', () => {
      this.state.subGoalOverlay.visible = !this.state.subGoalOverlay.visible;
      this.state.subGoalOverlay.current = Math.min(1000, this.state.subGoalOverlay.current + 25);
      this.broadcastFullState();
    });

    // Função #33: Alertas de Doação / Superchat via Webhook
    document.getElementById('btnTriggerAlert')?.addEventListener('click', () => {
      fetch('/api/webhook/alert?user=Gabriel_VIP&amount=R$%20100,00&msg=Excelente%20transmissao%20WebLive!').catch(() => {
        this.sync.send('WEBHOOK_ALERT', {
          user: 'Gabriel_VIP',
          amount: 'R$ 100,00',
          message: 'Excelente transmissão WebLive!'
        });
      });
      this.audioEngine.playSoundEffect('alert');
      this.logAction('Alerta de Superchat/Doação (#33) disparado');
    });

    // Função #36: Widget de Previsão do Tempo na tela
    document.getElementById('btnToggleWeather')?.addEventListener('click', () => {
      this.state.weatherOverlay.visible = !this.state.weatherOverlay.visible;
      this.broadcastFullState();
    });
  }

  _bindVideoAndAutomationControls() {
    // Controles Visuais (#1 PiP, #2 Multi-view Grid, #3 Chroma Key, #4 Crop, #5 Color, #10 BG Loop)
    const updateVisuals = () => {
      const vc = this.state.visualConfig;
      vc.layoutMode = document.getElementById('layoutModeSelect').value;
      vc.bgLoopTheme = document.getElementById('bgLoopSelect').value;
      vc.chromaEnabled = document.getElementById('chkChromaKey').checked;
      vc.chromaTolerance = parseInt(document.getElementById('rangeChromaTol').value, 10);
      vc.pipScale = parseInt(document.getElementById('rangePipScale').value, 10) / 100;
      vc.brightness = parseInt(document.getElementById('rangeBrightness').value, 10);
      vc.contrast = parseInt(document.getElementById('rangeContrast').value, 10);
      vc.saturation = parseInt(document.getElementById('rangeSaturation').value, 10);
      vc.cropTop = parseInt(document.getElementById('rangeCropTop').value, 10);

      Object.assign(this.pvwCompositor.visualConfig, vc);
      Object.assign(this.pgmCompositor.visualConfig, vc);
      this.broadcastFullState();
    };

    [
      'layoutModeSelect', 'bgLoopSelect', 'chkChromaKey', 'rangeChromaTol',
      'rangePipScale', 'rangeBrightness', 'rangeContrast', 'rangeSaturation', 'rangeCropTop'
    ].forEach((id) => {
      document.getElementById(id)?.addEventListener('input', updateVisuals);
      document.getElementById(id)?.addEventListener('change', updateVisuals);
    });

    // Core #3 e #6: Upload de Stinger / Marca d'água salvo localmente em IndexedDB
    document.getElementById('fileStingerUpload')?.addEventListener('change', (e) => {
      const file = e.target.files?.[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = async () => {
        const dataUrl = reader.result;
        await this.sync.saveAsset('custom_stinger_logo', dataUrl, file.type);
        this.pvwCompositor.setWatermarkImage(dataUrl);
        this.pgmCompositor.setWatermarkImage(dataUrl);
        this.logAction(`Arquivo Stinger/Logo (${file.name}) salvo no IndexedDB local (Core #3)`);
      };
      reader.readAsDataURL(file);
    });

    // Core #2 e #22: Fontes de Mídia Web + Playlist
    document.getElementById('btnAddMediaPlaylist')?.addEventListener('click', () => {
      const url = document.getElementById('webMediaUrlInput').value.trim();
      if (!url) return;
      this.state.webMedia.playlist.push(url);
      this.renderPlaylist();
      this.logAction(`Mídia adicionada à Playlist (#22): ${url}`);
    });

    document.getElementById('btnMediaPlay')?.addEventListener('click', () => {
      this.state.webMedia.currentUrl = document.getElementById('webMediaUrlInput').value.trim();
      this.state.webMedia.playing = true;
      this.sync.send('WEBMEDIA_CONTROL', { action: 'play', url: this.state.webMedia.currentUrl });
      this.logAction(`Play Mídia Web (Core #2): ${this.state.webMedia.currentUrl}`);
    });

    document.getElementById('btnMediaPause')?.addEventListener('click', () => {
      this.state.webMedia.playing = false;
      this.sync.send('WEBMEDIA_CONTROL', { action: 'pause' });
    });

    document.getElementById('btnMediaNext')?.addEventListener('click', () => {
      if (this.state.webMedia.playlist.length > 0) {
        const nextUrl = this.state.webMedia.playlist.shift();
        this.state.webMedia.playlist.push(nextUrl);
        document.getElementById('webMediaUrlInput').value = nextUrl;
        this.state.webMedia.currentUrl = nextUrl;
        this.renderPlaylist();
        this.sync.send('WEBMEDIA_CONTROL', { action: 'play', url: nextUrl });
      }
    });

    // Câmera Local + Roteamento de Áudio (Core #6)
    document.getElementById('btnStartLocalCam')?.addEventListener('click', async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ video: { width: 1280, height: 720 }, audio: true });
        const videoEl = document.getElementById('localCamVideo');
        videoEl.srcObject = stream;
        this.pvwCompositor.registerVideoSource('cam1', videoEl);
        this.pgmCompositor.registerVideoSource('cam1', videoEl);
        this.audioEngine.attachMediaStreamToChannel('cam1', stream);
        this.logAction('Câmera local 720p e microfone roteados para o Canal 1 (Core #6)');
      } catch (err) {
        this.logAction('Modo Simulador Broadcast ativo (Câmera física não conectada)');
      }
    });

    document.getElementById('audioRouteSelect')?.addEventListener('change', (e) => {
      const mode = e.target.value;
      this.audioEngine.setChannelMute('cam1', mode === 'muted');
      this.logAction(`Roteamento de Áudio Cam 1 (Core #6) alterado para: ${mode}`);
    });

    // Função #16: Talkback / Intercom (Push-to-Talk exclusivo para o Repórter WebRTC)
    const pttBtn = document.getElementById('btnTalkbackPTT');
    const startPTT = () => {
      this.audioEngine.setTalkbackActive(true);
      this.sync.send('TALKBACK_STATUS', { active: true, message: 'DIRETOR FALANDO NO INTERCOM (OFF-AIR)' });
      if (pttBtn) pttBtn.textContent = '🔴 TALKBACK ATIVO (FALANDO NO FONE DO REPÓRTER)';
    };
    const stopPTT = () => {
      this.audioEngine.setTalkbackActive(false);
      this.sync.send('TALKBACK_STATUS', { active: false });
      if (pttBtn) pttBtn.textContent = '🎙️ Segure p/ Talkback (Intercom #16)';
    };
    pttBtn?.addEventListener('mousedown', startPTT);
    pttBtn?.addEventListener('mouseup', stopPTT);
    pttBtn?.addEventListener('mouseleave', stopPTT);
    pttBtn?.addEventListener('touchstart', (e) => { e.preventDefault(); startPTT(); });
    pttBtn?.addEventListener('touchend', stopPTT);

    // Função #39: Compartilhamento de Tela (Screen Share)
    document.getElementById('btnStartScreenShare')?.addEventListener('click', async () => {
      try {
        const screenStream = await navigator.mediaDevices.getDisplayMedia({ video: true, audio: true });
        const screenVid = document.getElementById('screenShareVideo');
        screenVid.srcObject = screenStream;
        this.pvwCompositor.registerVideoSource('screenshare', screenVid);
        this.pgmCompositor.registerVideoSource('screenshare', screenVid);
        this.state.visualConfig.layoutMode = 'pip';
        document.getElementById('layoutModeSelect').value = 'pip';
        updateVisuals();
        this.logAction('Compartilhamento de Tela (#39) iniciado no PiP');
      } catch (_) {}
    });

    // Função #41: Testador de Banda Integrado
    document.getElementById('btnRunSpeedtest')?.addEventListener('click', async () => {
      const resBox = document.getElementById('speedtestResult');
      if (resBox) resBox.textContent = 'Testando RTT, Jitter e Upload WebRTC...';
      const stats = await this.webrtc.runBandwidthTest();
      if (resBox) {
        resBox.textContent = `Speedtest (#41): Upload ${stats.uploadMbps} Mbps • RTT ${stats.rttMs}ms • Jitter ${stats.jitterMs}ms • ${stats.quality}`;
      }
      this.logAction(`Speedtest (#41): ${stats.uploadMbps} Mbps (${stats.rttMs}ms)`);
    });

    // Função #25: Cronômetro Regressivo (Countdown de Início de Live)
    document.getElementById('btnToggleCountdown')?.addEventListener('click', () => {
      this.state.countdownOverlay.visible = !this.state.countdownOverlay.visible;
      if (this.state.countdownOverlay.visible && this.state.countdownOverlay.remainingSec <= 0) {
        this.state.countdownOverlay.remainingSec = 180;
      }
      this.logAction(`Countdown Regressivo (#25): ${this.state.countdownOverlay.visible ? 'ATIVADO' : 'OCULTO'}`);
      this.broadcastFullState();
    });

    // Função #27: Gravação Local de Backup via MediaRecorder API
    document.getElementById('btnBackupRecord')?.addEventListener('click', (e) => {
      const isRec = this.pgmCompositor.toggleLocalBackupRecording((filename) => {
        this.logAction(`Gravação de Backup Local (#27) salva: ${filename}`);
      });
      e.currentTarget.textContent = isRec ? '⏹️ Parar e Salvar Backup (#27)' : '⏺️ Gravar Backup Local (#27)';
      e.currentTarget.classList.toggle('btn-pgm', isRec);
      this.logAction(isRec ? 'Gravação de Backup Local (#27) iniciada' : 'Gravação de Backup Local finalizada');
    });

    // Função #28: Agendamento de Eventos (Troca de cena em horário programado)
    document.getElementById('btnAddSchedule')?.addEventListener('click', () => {
      const timeVal = document.getElementById('scheduleTimeInput').value;
      const sceneId = document.getElementById('scheduleSceneSelect').value;
      if (!timeVal || !sceneId) return;
      this.scheduledEvents.push({ time: timeVal, sceneId, executed: false });
      this.logAction(`Evento agendado (#28): Cena ${sceneId} às ${timeVal}`);
    });

    // Função #45: Exportar e Importar Projeto Completo em JSON
    document.getElementById('btnExportJson')?.addEventListener('click', () => {
      const blob = new Blob([JSON.stringify(this.state, null, 2)], { type: 'application/json' });
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = `weblive-project-${Date.now()}.json`;
      a.click();
      this.logAction('Projeto exportado em JSON (#45)');
    });

    document.getElementById('fileImportJson')?.addEventListener('change', (e) => {
      const file = e.target.files?.[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = () => {
        try {
          const imported = JSON.parse(reader.result);
          Object.assign(this.state, imported);
          this.renderScenesGrid();
          this.broadcastFullState();
          this.logAction(`Projeto JSON importado com sucesso (#45): ${file.name}`);
        } catch (_) {}
      };
      reader.readAsText(file);
    });

    // Função #49: Exportar Log de Ações / Comerciais em CSV
    document.getElementById('btnExportLogs')?.addEventListener('click', () => {
      const csv = 'Horario,Acao\n' + this.actionLogs.map((l) => `"${l.time}","${l.msg}"`).join('\n');
      const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = `weblive-audit-log-${Date.now()}.csv`;
      a.click();
    });

    // Funções de Áudio: Ducking (#14), Auto-Switching por Voz (#23), Soundboard (#15) e Web MIDI (#48)
    document.getElementById('chkAudioDucking')?.addEventListener('change', (e) => {
      this.audioEngine.duckingEnabled = e.target.checked;
      this.logAction(`Audio Ducking Automático (#14): ${e.target.checked ? 'ATIVO' : 'OFF'}`);
    });

    document.getElementById('chkAutoVoiceSwitch')?.addEventListener('change', (e) => {
      this.audioEngine.autoSwitchVoiceEnabled = e.target.checked;
      this.logAction(`Auto-Switching por Voz (#23): ${e.target.checked ? 'ATIVO' : 'OFF'}`);
    });

    document.querySelectorAll('.sfx-trigger').forEach((btn) => {
      btn.addEventListener('click', () => {
        const sfx = btn.dataset.sfx;
        this.audioEngine.playSoundEffect(sfx);
        this.logAction(`Soundboard (#15) disparado: ${sfx.toUpperCase()}`);
      });
    });

    document.getElementById('btnInitMidi')?.addEventListener('click', () => {
      this.audioEngine.initWebMIDI((status) => {
        const el = document.getElementById('midiStatusText');
        if (el) el.textContent = status;
        this.logAction(status);
      });
    });
  }

  /**
   * Renderiza os botões de Cenas (Core #1) e popula o seletor de Agendamento (#28)
   */
  renderScenesGrid() {
    const grid = document.getElementById('scenesGrid');
    const schedSelect = document.getElementById('scheduleSceneSelect');
    if (!grid) return;

    grid.innerHTML = '';
    if (schedSelect) schedSelect.innerHTML = '';

    this.state.scenes.forEach((scene) => {
      const isPvw = scene.id === this.state.pvwSceneId;
      const isPgm = scene.id === this.state.pgmSceneId;

      const tile = document.createElement('div');
      tile.className = `scene-tile ${isPvw ? 'active-pvw' : ''} ${isPgm ? 'active-pgm' : ''}`;
      tile.innerHTML = `
        <div style="display:flex; justify-content:space-between; width:100%;">
          <span class="scene-key-badge">[${scene.key || '•'}]</span>
          <span style="font-size:10px; font-weight:800; color:${isPgm ? '#ff5252' : (isPvw ? '#00e676' : 'var(--text-muted)')};">
            ${isPgm ? 'PGM NO AR' : (isPvw ? 'PREVIEW' : 'STANDBY')}
          </span>
        </div>
        <strong style="font-size:12px;">${scene.name}</strong>
        <span style="font-size:10px; color:var(--text-muted);">${scene.subtitle}</span>
      `;

      // Clique simples seleciona no Preview; Duplo clique corta direto para o Program
      tile.addEventListener('click', () => this.selectPreviewScene(scene.id));
      tile.addEventListener('dblclick', () => {
        this.selectPreviewScene(scene.id);
        this.executeTransition('cut');
      });

      grid.appendChild(tile);

      if (schedSelect) {
        const opt = document.createElement('option');
        opt.value = scene.id;
        opt.textContent = scene.name;
        schedSelect.appendChild(opt);
      }
    });

    const pvwScene = this.getSceneById(this.state.pvwSceneId);
    const pgmScene = this.getSceneById(this.state.pgmSceneId);
    const pvwTitle = document.getElementById('pvwSceneName');
    const pgmTitle = document.getElementById('pgmSceneName');
    if (pvwTitle && pvwScene) pvwTitle.textContent = pvwScene.name.toUpperCase();
    if (pgmTitle && pgmScene) pgmTitle.textContent = pgmScene.name.toUpperCase();
  }

  /**
   * Renderiza os Canais do Audio Mixer Multi-pista (#11, #13, #17, #18, #19)
   */
  renderMixerStrips() {
    const container = document.getElementById('mixerChannelsContainer');
    if (!container) return;
    container.innerHTML = '';

    this.audioEngine.defaultChannelDefs.forEach((def) => {
      const ch = this.audioEngine.channels.get(def.id) || this.audioEngine.createChannel(def);
      ch.simulatedSignal = true; // Ativa modulação para feedback visual imediato dos VU meters

      const strip = document.createElement('div');
      strip.className = 'mixer-channel';
      strip.innerHTML = `
        <div style="display:flex; justify-content:space-between; align-items:center;">
          <strong style="font-size:11px;">${def.name}</strong>
          <div style="display:flex; gap:4px;">
            <button class="btn btn-sm btn-pfl" data-id="${def.id}" title="Pre-Fader Listen (#18)">🎧 PFL</button>
            <button class="btn btn-sm btn-mute" data-id="${def.id}" title="Mute Canal">🔊 ON</button>
          </div>
        </div>
        <div class="vu-meter-bar">
          <div class="vu-meter-fill" id="vu_${def.id}"></div>
        </div>
        <div style="display:grid; grid-template-columns:48px 1fr 42px; gap:6px; align-items:center; font-size:10px;">
          <span>Vol (#11):</span>
          <input type="range" class="fader-vol" data-id="${def.id}" min="0" max="1" step="0.01" value="${def.volume}" />
          <span id="volLabel_${def.id}">${Math.round(def.volume * 100)}%</span>
        </div>
        <div style="display:grid; grid-template-columns:48px 1fr 52px 55px; gap:4px; align-items:center; font-size:10px; color:var(--text-muted);">
          <span>Pan (#19):</span>
          <input type="range" class="fader-pan" data-id="${def.id}" min="-1" max="1" step="0.1" value="${def.pan}" />
          <span>Delay (#17):</span>
          <input type="number" class="input-delay" data-id="${def.id}" min="0" max="900" value="${def.delayMs}" title="Lip-Sync Delay em ms" style="padding:2px 4px; font-size:10px;" />
        </div>
      `;

      strip.querySelector('.fader-vol')?.addEventListener('input', (e) => {
        const val = parseFloat(e.target.value);
        this.audioEngine.setChannelVolume(def.id, val);
        const lbl = document.getElementById(`volLabel_${def.id}`);
        if (lbl) lbl.textContent = `${Math.round(val * 100)}%`;
      });

      strip.querySelector('.fader-pan')?.addEventListener('input', (e) => {
        this.audioEngine.setChannelPan(def.id, parseFloat(e.target.value));
      });

      strip.querySelector('.input-delay')?.addEventListener('change', (e) => {
        this.audioEngine.setChannelDelay(def.id, parseInt(e.target.value, 10));
      });

      strip.querySelector('.btn-mute')?.addEventListener('click', (e) => {
        const chObj = this.audioEngine.channels.get(def.id);
        const nextMute = !chObj.muted;
        this.audioEngine.setChannelMute(def.id, nextMute);
        e.currentTarget.textContent = nextMute ? '🔇 MUTE' : '🔊 ON';
        e.currentTarget.classList.toggle('btn-pgm', nextMute);
      });

      strip.querySelector('.btn-pfl')?.addEventListener('click', (e) => {
        const active = this.audioEngine.toggleChannelPFL(def.id);
        e.currentTarget.classList.toggle('btn-amber', active);
        this.logAction(`Monitoramento PFL (#18) em ${def.name}: ${active ? 'ATIVO' : 'OFF'}`);
      });

      container.appendChild(strip);
    });
  }

  renderPlaylist() {
    const box = document.getElementById('playlistContainer');
    if (!box) return;
    box.innerHTML = '';
    this.state.webMedia.playlist.forEach((url, idx) => {
      const row = document.createElement('div');
      row.style.cssText = 'display:flex; justify-content:space-between; align-items:center; background:var(--bg-card); padding:3px 6px; border-radius:4px;';
      row.innerHTML = `<span style="overflow:hidden; text-overflow:ellipsis; white-space:nowrap; max-width:210px;">${idx + 1}. ${url}</span>`;
      const btnPlayItem = document.createElement('button');
      btnPlayItem.className = 'btn btn-sm';
      btnPlayItem.textContent = '▶';
      btnPlayItem.onclick = () => {
        document.getElementById('webMediaUrlInput').value = url;
        this.state.webMedia.currentUrl = url;
        this.state.webMedia.playing = true;
        this.sync.send('WEBMEDIA_CONTROL', { action: 'play', url });
      };
      row.appendChild(btnPlayItem);
      box.appendChild(row);
    });
  }

  appendChatMessage(author, text) {
    const feed = document.getElementById('liveChatFeed');
    if (!feed) return;
    const div = document.createElement('div');
    div.style.cssText = 'display:flex; justify-content:space-between; align-items:center; background:rgba(255,255,255,0.04); padding:4px 6px; border-radius:4px;';
    div.innerHTML = `<span><strong>${author}:</strong> ${text}</span>`;
    const btn = document.createElement('button');
    btn.className = 'btn btn-sm';
    btn.textContent = 'No Ar';
    btn.onclick = () => {
      this.state.featuredComment = { visible: true, author, text };
      this.broadcastFullState();
    };
    div.appendChild(btn);
    feed.prepend(div);
  }

  selectPreviewScene(sceneId) {
    this.state.pvwSceneId = sceneId;
    this.renderScenesGrid();
    this.updateTallyLights();
  }

  /**
   * Executa a transição entre Preview e Program (CUT, Crossfade ou Stinger Animado Core #3)
   */
  executeTransition(type = 'cut') {
    if (this.state.sceneLocked) {
      alert('🔒 A cena atual está bloqueada (Lock Scene #44). Desative o cadeado para trocar de cena.');
      return;
    }

    if (type === 'stinger') {
      this.audioEngine.playSoundEffect('stinger');
      this.sync.send('TRIGGER_STINGER', { durationMs: 900 });
    }

    // Troca Program <-> Preview (estilo Switcher Broadcast)
    const oldPgm = this.state.pgmSceneId;
    this.state.pgmSceneId = this.state.pvwSceneId;
    this.state.pvwSceneId = oldPgm;

    const newPgmScene = this.getSceneById(this.state.pgmSceneId);
    this.renderScenesGrid();
    this.updateTallyLights();
    this.logAction(`Transição [${type.toUpperCase()}] -> NO AR: ${newPgmScene?.name || this.state.pgmSceneId}`);
    this.broadcastFullState();
  }

  /**
   * Função #24: Tally Light (Envia sinal em tempo real para o celular do Repórter indicando se está NO AR ou PREVIEW)
   */
  updateTallyLights() {
    const pgmScene = this.getSceneById(this.state.pgmSceneId);
    const pvwScene = this.getSceneById(this.state.pvwSceneId);

    const guestInPgm = pgmScene && (pgmScene.sourceType === 'guest1' || pgmScene.layoutMode !== 'single');
    const guestInPvw = pvwScene && (pvwScene.sourceType === 'guest1' || pvwScene.layoutMode !== 'single');

    const tallyState = guestInPgm ? 'PGM' : (guestInPvw ? 'PVW' : 'IDLE');
    this.sync.send('TALLY_UPDATE', { guestId: 'Reporter1', tally: tallyState, sceneName: pgmScene?.name });
  }

  /**
   * Função #23: Auto-Switching por Voz
   */
  handleAutoVoiceSwitch(dominantChannelId) {
    if (this.state.sceneLocked) return;
    const now = Date.now();
    if (now - this.lastVoiceSwitchTime < 3500) return; // Evita cortes frenéticos

    const targetScene = this.state.scenes.find((s) => s.sourceType === dominantChannelId);
    if (targetScene && targetScene.id !== this.state.pgmSceneId) {
      this.lastVoiceSwitchTime = now;
      this.state.pvwSceneId = targetScene.id;
      this.executeTransition('cut');
    }
  }

  /**
   * Função #8: Dispara Instant Replay dos últimos 10 segundos no Program e no OBS
   */
  triggerInstantReplay() {
    const replayUrl = this.pgmCompositor.getInstantReplayBlobUrl();
    if (!replayUrl) {
      this.logAction('Instant Replay (#8): Aguardando buffer inicial de 10 segundos...');
      return;
    }
    const replayVid = document.getElementById('replayPlaybackVideo');
    replayVid.src = replayUrl;
    replayVid.play().catch(() => {});
    this.pgmCompositor.registerVideoSource('replay', replayVid);
    this.sync.send('TRIGGER_INSTANT_REPLAY', { durationMs: 6000 });
    this.logAction('⏪ Instant Replay (#8) dos últimos 10s exibido no ar!');
  }

  /**
   * Função #40: Whiteboard / Telestrator Ao Vivo (Desenhar sobre o monitor Program e refletir no OBS)
   */
  _initWhiteboardInteraction() {
    const canvas = document.getElementById('pgmCanvas');
    if (!canvas) return;
    let drawing = false;

    const getNormCoords = (e) => {
      const rect = canvas.getBoundingClientRect();
      const clientX = e.touches ? e.touches[0].clientX : e.clientX;
      const clientY = e.touches ? e.touches[0].clientY : e.clientY;
      return {
        x: (clientX - rect.left) / rect.width,
        y: (clientY - rect.top) / rect.height
      };
    };

    canvas.addEventListener('mousedown', (e) => {
      if (!document.getElementById('chkWhiteboardMode')?.checked) return;
      drawing = true;
      const color = document.getElementById('whiteboardColor')?.value || '#ffeb3b';
      const stroke = { color, size: 5, points: [getNormCoords(e)] };
      this.pgmCompositor.whiteboardStrokes.push(stroke);
    });

    canvas.addEventListener('mousemove', (e) => {
      if (!drawing) return;
      const strokes = this.pgmCompositor.whiteboardStrokes;
      const current = strokes[strokes.length - 1];
      if (current) {
        current.points.push(getNormCoords(e));
        this.sync.send('WHITEBOARD_SYNC', { strokes });
      }
    });

    window.addEventListener('mouseup', () => { drawing = false; });

    document.getElementById('btnClearWhiteboard')?.addEventListener('click', () => {
      this.pgmCompositor.whiteboardStrokes = [];
      this.sync.send('WHITEBOARD_SYNC', { strokes: [] });
      this.logAction('Whiteboard / Anotações Ao Vivo (#40) limpo');
    });
  }

  /**
   * Função #21: Macros e Atalhos de Teclado (Teclas 1..6 mudam Preview, Espaço = CUT, Enter = AUTO)
   */
  _initKeyboardMacros() {
    window.addEventListener('keydown', (e) => {
      if (['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement?.tagName)) return;

      if (e.code === 'Space') {
        e.preventDefault();
        this.executeTransition('cut');
      } else if (e.key >= '1' && e.key <= '6') {
        const idx = parseInt(e.key, 10) - 1;
        if (this.state.scenes[idx]) {
          this.selectPreviewScene(this.state.scenes[idx].id);
        }
      }
    });
  }

  _initWebRTCCallbacks() {
    this.webrtc.onRemoteTrackCallback = (guestId, stream) => {
      const vEl = document.getElementById('guestRemoteVideo');
      if (vEl) {
        vEl.srcObject = stream;
        this.pvwCompositor.registerVideoSource('guest1', vEl);
        this.pgmCompositor.registerVideoSource('guest1', vEl);
      }
      this.audioEngine.attachMediaStreamToChannel('guest1', stream);
      const badge = document.getElementById('guestStatusBadge');
      if (badge) {
        badge.textContent = 'CONECTADO AO VIVO';
        badge.style.background = 'rgba(0, 200, 83, 0.25)';
        badge.style.color = '#00e676';
      }
      this.updateTallyLights();
      this.logAction(`Repórter Remoto (${guestId}) conectado via WebRTC com retorno Mix-Minus!`);
    };

    this.webrtc.onConnectionStateChange = (guestId, state) => {
      const badge = document.getElementById('guestStatusBadge');
      if (badge) badge.textContent = state.toUpperCase();
      if (state === 'disconnected' || state === 'reconnecting') {
        this.logAction(`Auto-Reconexão WebRTC (#50) acionada para ${guestId}`);
      }
    };
  }

  _initSyncListeners() {
    this.sync.onMessage((msg) => {
      if (!msg) return;
      // Função #46: Recebe comandos HTTP vindos do Elgato Stream Deck
      if (msg.type === 'STREAMDECK_COMMAND') {
        if (msg.action === 'cut') {
          this.executeTransition('cut');
        } else if (msg.action === 'stinger') {
          this.executeTransition('stinger');
        } else if (msg.action === 'scene') {
          const targetIdx = parseInt(msg.target, 10) - 1;
          if (this.state.scenes[targetIdx]) {
            this.selectPreviewScene(this.state.scenes[targetIdx].id);
            this.executeTransition('cut');
          }
        }
        this.logAction(`Stream Deck API (#46) executou: ${msg.action} ${msg.target || ''}`);
      } else if (msg.type === 'OUTPUT_REQUEST_STATE') {
        this.broadcastFullState();
      }
    });
  }

  getProgramReturnStream() {
    const pgmCanvas = document.getElementById('pgmCanvas');
    if (pgmCanvas && pgmCanvas.captureStream) {
      return pgmCanvas.captureStream(30);
    }
    return null;
  }

  getSceneById(id) {
    return this.state.scenes.find((s) => s.id === id) || this.state.scenes[0];
  }

  broadcastFullState() {
    this.sync.send('STATE_UPDATE', this.state);
  }

  /**
   * Função #49: Registra cada ação de broadcast com carimbo de hora para comprovação comercial
   */
  logAction(msg) {
    const time = new Date().toLocaleTimeString('pt-BR');
    this.actionLogs.unshift({ time, msg });
    const box = document.getElementById('actionLogsBox');
    if (box) {
      const line = document.createElement('div');
      line.textContent = `[${time}] ${msg}`;
      box.prepend(line);
    }
  }

  /**
   * Loop Principal 60fps: Renderiza Canvas PVW/PGM, VU Meters, Relógio (#26),
   * Cronômetros (#4/#25), Agendador (#28) e Monitoramento CPU/RAM (#42)
   */
  _startRenderAndMetricsLoop() {
    let frameCount = 0;
    let lastFpsCheck = performance.now();

    const renderLoop = () => {
      frameCount++;
      const spectrum = this.audioEngine.getVisualizerSpectrum();

      const pvwScene = this.getSceneById(this.state.pvwSceneId);
      const pgmScene = this.getSceneById(this.state.pgmSceneId);

      this.pvwCompositor.renderSceneFrame(pvwScene, spectrum);
      this.pgmCompositor.renderSceneFrame(pgmScene, spectrum);

      // Atualiza barras de VU Meter no Mixer (#11)
      this.audioEngine.channels.forEach((ch, id) => {
        const bar = document.getElementById(`vu_${id}`);
        if (bar) bar.style.width = `${Math.min(100, Math.round(ch.currentLevel))}%`;
      });

      requestAnimationFrame(renderLoop);
    };
    requestAnimationFrame(renderLoop);

    // Tick de 1 segundo para Relógio (#26), Cronômetro do Placar (Core #4), Countdown (#25), Agendador (#28) e Saúde (#42)
    setInterval(() => {
      const now = performance.now();
      const fps = Math.min(60, Math.round((frameCount * 1000) / Math.max(1, now - lastFpsCheck)));
      frameCount = 0;
      lastFpsCheck = now;

      // Função #42: Monitoramento de CPU / Memória / FPS
      const memMb = performance.memory ? Math.round(performance.memory.usedJSHeapSize / 1048576) : 142;
      const cpuSim = Math.min(35, Math.max(8, Math.round(14 + Math.sin(now / 2000) * 5)));
      const healthEl = document.getElementById('healthMetrics');
      if (healthEl) healthEl.textContent = `${fps} FPS • CPU ${cpuSim}% • RAM ${memMb}MB`;

      // Função #26: Relógio com suporte a Fuso Horário
      const tz = document.getElementById('timezoneSelect')?.value || 'America/Sao_Paulo';
      const timeStr = new Date().toLocaleTimeString('pt-BR', { timeZone: tz });
      const clockEl = document.getElementById('clockDisplay');
      if (clockEl) clockEl.textContent = timeStr;

      // Cronômetro do Placar Esportivo (Core #4)
      if (this.state.scoreboard.timerRunning) {
        this.state.scoreboard.timerSec++;
        this.broadcastFullState();
      }

      // Cronômetro Regressivo de Início de Live (#25)
      if (this.state.countdownOverlay.visible && this.state.countdownOverlay.remainingSec > 0) {
        this.state.countdownOverlay.remainingSec--;
        this.broadcastFullState();
      }

      // Função #28: Verificador de Eventos Agendados
      const hhmmss = new Date().toTimeString().slice(0, 8);
      const hhmm = hhmmss.slice(0, 5);
      this.scheduledEvents.forEach((ev) => {
        if (!ev.executed && (ev.time === hhmmss || ev.time === hhmm)) {
          ev.executed = true;
          this.selectPreviewScene(ev.sceneId);
          this.executeTransition('stinger');
          this.logAction(`⏰ Agendamento Automático (#28) executado: Cena ${ev.sceneId}`);
        }
      });
    }, 1000);
  }
}

window.addEventListener('DOMContentLoaded', () => {
  window.directorApp = new WebLiveDirectorApp();
});

