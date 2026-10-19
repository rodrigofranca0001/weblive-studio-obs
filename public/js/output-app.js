/**
 * ============================================================================
 * WebLive Studio - Controlador da Tela de Exibição OBS (output-app.js)
 * ============================================================================
 * Renderiza a saída final em 1080p60 para ser capturada como "Browser Source" no OBS.
 * Suporta:
 * - Modo Normal (`/output.html`): Vídeo + Overlays Gráficos + Tarjetas + Placar + Ticker
 * - Modo Clean Feed (`/output.html?clean=1` - Função #43): Apenas o vídeo composto sem gráficos
 * - Carregamento de Stingers e Logos direto do IndexedDB local da máquina do OBS (Core #3)
 */

class WebLiveOutputApp {
  constructor() {
    this.sync = new WebLiveSyncEngine('output');
    this.compositor = new WebLiveVideoCompositor(document.getElementById('obsOutputCanvas'), 'output');

    // Função #43: Verifica se esta URL é a saída "Clean Feed" (?clean=1)
    const params = new URLSearchParams(window.location.search);
    this.isCleanFeed = params.get('clean') === '1';

    if (this.isCleanFeed) {
      const gLayer = document.getElementById('graphicsLayer');
      if (gLayer) gLayer.style.display = 'none';
      this.compositor.visualConfig.watermarkEnabled = false;
      this.compositor.visualConfig.visualizerEnabled = false;
    }

    this.currentState = {
      scenes: [
        { id: 'scene_1', name: 'Estúdio Principal', subtitle: 'Apresentador • Cam 1 (1080p60)', sourceType: 'cam1', layoutMode: 'single', bgTheme: 'cyber-grid' }
      ],
      pgmSceneId: 'scene_1'
    };

    this._loadLocalAssetsFromIndexedDB();
    this._setupSyncListeners();
    this._startRenderLoop();

    // Pede o estado atual ao Painel do Diretor assim que o OBS abre a Browser Source
    setTimeout(() => this.sync.send('OUTPUT_REQUEST_STATE', {}), 200);
  }

  async _loadLocalAssetsFromIndexedDB() {
    const customLogo = await this.sync.getAsset('custom_stinger_logo');
    if (customLogo) {
      if (!this.isCleanFeed) {
        this.compositor.setWatermarkImage(customLogo);
      }
      const stingerImg = document.getElementById('obsStingerLogo');
      if (stingerImg) {
        stingerImg.src = customLogo;
        stingerImg.style.display = 'block';
      }
    }
  }

  _setupSyncListeners() {
    this.sync.onMessage((msg) => {
      if (!msg || !msg.type) return;

      if (msg.type === 'STATE_UPDATE' && msg.data) {
        this.currentState = msg.data;
        if (msg.data.visualConfig) {
          Object.assign(this.compositor.visualConfig, msg.data.visualConfig);
          if (this.isCleanFeed) {
            this.compositor.visualConfig.watermarkEnabled = false;
            this.compositor.visualConfig.visualizerEnabled = false;
          }
        }
        this._updateDOMOverlays(msg.data);
      } else if (msg.type === 'TRIGGER_STINGER') {
        this._playStingerTransition(msg.data?.durationMs || 900);
      } else if (msg.type === 'WHITEBOARD_SYNC') {
        if (!this.isCleanFeed) {
          this.compositor.whiteboardStrokes = msg.data?.strokes || [];
        }
      } else if (msg.type === 'ASSET_UPDATED') {
        this._loadLocalAssetsFromIndexedDB();
      } else if (msg.type === 'WEBHOOK_ALERT') {
        this._showWebhookAlert(msg.data || msg);
      } else if (msg.type === 'WEBMEDIA_CONTROL') {
        this._handleWebMedia(msg.data);
      }
    });
  }

  _updateDOMOverlays(state) {
    if (this.isCleanFeed) return;

    // 1. Lower Third / Tarjeta (Core #5)
    const ltEl = document.getElementById('obsLowerThird');
    if (ltEl && state.lowerThird) {
      document.getElementById('obsLtTitle').textContent = state.lowerThird.title;
      document.getElementById('obsLtSubtitle').textContent = state.lowerThird.subtitle;
      ltEl.classList.toggle('visible', !!state.lowerThird.visible);
    }

    // 2. Placar Esportivo (Core #4)
    const sbEl = document.getElementById('obsScoreboard');
    if (sbEl && state.scoreboard) {
      document.getElementById('obsTeamA').textContent = state.scoreboard.teamA;
      document.getElementById('obsPtsA').textContent = state.scoreboard.ptsA;
      document.getElementById('obsTeamB').textContent = state.scoreboard.teamB;
      document.getElementById('obsPtsB').textContent = state.scoreboard.ptsB;
      const mins = String(Math.floor((state.scoreboard.timerSec || 0) / 60)).padStart(2, '0');
      const secs = String((state.scoreboard.timerSec || 0) % 60).padStart(2, '0');
      document.getElementById('obsTimer').textContent = `${mins}:${secs}`;
      sbEl.classList.toggle('visible', !!state.scoreboard.visible);
    }

    // 3. Ticker Tape / Crawl (#7 & #37)
    const tickerEl = document.getElementById('obsTicker');
    if (tickerEl && state.ticker) {
      document.getElementById('obsTickerTrack').textContent = state.ticker.text;
      tickerEl.classList.toggle('visible', !!state.ticker.visible);
    }

    // 4. QR Code Ao Vivo (#9)
    const qrBox = document.getElementById('obsQrBox');
    if (qrBox && state.qrOverlay) {
      qrBox.style.display = state.qrOverlay.visible ? 'block' : 'none';
      if (state.qrOverlay.visible && window.drawLiveQRCode) {
        window.drawLiveQRCode(document.getElementById('obsQrCanvas'), state.qrOverlay.url);
      }
    }

    // 5. Enquete Ao Vivo (#32)
    const pollBox = document.getElementById('obsPollBox');
    if (pollBox && state.pollOverlay) {
      pollBox.style.display = state.pollOverlay.visible ? 'block' : 'none';
      const total = Math.max(1, state.pollOverlay.votesA + state.pollOverlay.votesB);
      const pctA = Math.round((state.pollOverlay.votesA / total) * 100);
      const pctB = 100 - pctA;
      document.getElementById('obsPollPctA').textContent = `${pctA}%`;
      document.getElementById('obsPollPctB').textContent = `${pctB}%`;
      document.getElementById('obsPollBarA').style.width = `${pctA}%`;
      document.getElementById('obsPollBarB').style.width = `${pctB}%`;
    }

    // 6. Barra de Meta (#34)
    const goalBox = document.getElementById('obsSubGoalBox');
    if (goalBox && state.subGoalOverlay) {
      goalBox.style.display = state.subGoalOverlay.visible ? 'block' : 'none';
      const pct = Math.min(100, Math.round((state.subGoalOverlay.current / state.subGoalOverlay.target) * 100));
      document.getElementById('obsGoalCount').textContent = `${state.subGoalOverlay.current} / ${state.subGoalOverlay.target}`;
      document.getElementById('obsGoalFill').style.width = `${pct}%`;
    }

    // 7. Comentário em Destaque (#35)
    const commBox = document.getElementById('obsFeaturedComment');
    if (commBox && state.featuredComment) {
      commBox.style.display = state.featuredComment.visible ? 'block' : 'none';
      document.getElementById('obsCommentAuthor').textContent = state.featuredComment.author;
      document.getElementById('obsCommentText').textContent = state.featuredComment.text;
    }

    // 8. Previsão do Tempo (#36)
    const weatherBox = document.getElementById('obsWeatherBox');
    if (weatherBox && state.weatherOverlay) {
      weatherBox.style.display = state.weatherOverlay.visible ? 'block' : 'none';
    }

    // 9. Countdown Regressivo Gigante (#25)
    const cdBox = document.getElementById('obsCountdownOverlay');
    if (cdBox && state.countdownOverlay) {
      cdBox.style.display = state.countdownOverlay.visible ? 'flex' : 'none';
      const m = String(Math.floor((state.countdownOverlay.remainingSec || 0) / 60)).padStart(2, '0');
      const s = String((state.countdownOverlay.remainingSec || 0) % 60).padStart(2, '0');
      document.getElementById('obsCountdownClock').textContent = `${m}:${s}`;
    }

    // 10. Mídia Web (Core #2) quando a cena de Mídia Web está ativa
    const pgmScene = this._getActivePgmScene();
    const mediaBox = document.getElementById('webMediaContainer');
    if (mediaBox) {
      const showMedia = pgmScene?.sourceType === 'webmedia' || state.webMedia?.playing;
      mediaBox.style.display = showMedia ? 'block' : 'none';
    }
  }

  _handleWebMedia(data) {
    const mediaBox = document.getElementById('webMediaContainer');
    const iframe = document.getElementById('webMediaIframe');
    if (!mediaBox || !iframe) return;

    if (data?.action === 'play' && data.url) {
      mediaBox.style.display = 'block';
      if (iframe.src !== data.url) {
        iframe.src = data.url;
      }
    } else if (data?.action === 'pause') {
      mediaBox.style.display = 'none';
      iframe.src = '';
    }
  }

  _playStingerTransition(durationMs) {
    const stinger = document.getElementById('obsStingerLayer');
    if (!stinger) return;
    stinger.classList.add('active');
    setTimeout(() => stinger.classList.remove('active'), durationMs);
  }

  _showWebhookAlert(alertData) {
    if (this.isCleanFeed) return;
    const box = document.getElementById('obsWebhookAlert');
    if (!box) return;
    document.getElementById('obsAlertUser').textContent = `${alertData.user || 'Apoiador'} • ${alertData.amount || 'R$ 50,00'}`;
    document.getElementById('obsAlertMsg').textContent = alertData.message || 'Parabéns pela transmissão!';
    box.style.display = 'block';
    setTimeout(() => { box.style.display = 'none'; }, 5500);
  }

  _getActivePgmScene() {
    if (!this.currentState.scenes) return null;
    return this.currentState.scenes.find((s) => s.id === this.currentState.pgmSceneId) || this.currentState.scenes[0];
  }

  _startRenderLoop() {
    const loop = () => {
      const scene = this._getActivePgmScene();
      const simSpectrum = Array.from({ length: 16 }, (_, i) => Math.abs(Math.sin(Date.now() / 190 + i * 0.5)) * 60 + 10);
      this.compositor.renderSceneFrame(scene, simSpectrum);
      requestAnimationFrame(loop);
    };
    requestAnimationFrame(loop);
  }
}

window.addEventListener('DOMContentLoaded', () => {
  window.outputApp = new WebLiveOutputApp();
});

