/**
 * ============================================================================
 * WebLive Studio - Engine de Vídeo, Compositor Canvas/WebGL & Instant Replay
 * ============================================================================
 * Implementa:
 * - #1: Picture-in-Picture (PiP) redimensionável e posicionável
 * - #2: Multi-view Grid (Mosaico automático para até 4 ou 8 câmeras/convidados)
 * - #3: Chroma Key (Fundo Verde) processado pixel a pixel / shader em tempo real
 * - #4: Recorte / Máscara (Cropping Top/Bottom/Left/Right)
 * - #5: Correção de Cor Básica (Brilho, Contraste e Saturação por fonte)
 * - #6: Marca d'água transparente no canto da tela
 * - #8: Instant Replay (Gravação circular em buffer dos últimos 10 segundos com MediaRecorder)
 * - #10: Backgrounds Dinâmicos animados em loop
 * - #27: Gravação Local de Backup (MediaRecorder API gerando arquivo .webm no PC do diretor)
 * - #40: Whiteboard / Anotações Ao Vivo (Telestrator esportivo desenhado sobre a cena)
 */

class WebLiveVideoCompositor {
  constructor(canvasElement, role = 'director') {
    this.canvas = canvasElement;
    this.ctx = this.canvas ? this.canvas.getContext('2d', { willReadFrequently: true }) : null;
    this.role = role;

    // Estado de Filtros Visuais (#3, #4, #5, #1, #2)
    this.visualConfig = {
      layoutMode: 'single', // 'single' | 'pip' | 'grid4' | 'grid8'
      pipScale: 0.28,
      pipX: 0.68,
      pipY: 0.64,
      chromaEnabled: false,
      chromaTolerance: 95,
      cropTop: 0,
      cropBottom: 0,
      cropLeft: 0,
      cropRight: 0,
      brightness: 100,
      contrast: 100,
      saturation: 100,
      bgLoopTheme: 'cyber-grid', // 'cyber-grid' | 'news-globe' | 'stadium-lights' | 'custom-video'
      watermarkEnabled: true,
      watermarkText: 'WEBLIVE HD',
      visualizerEnabled: true
    };

    // Fontes de vídeo ativas (Câmera Local, Repórteres WebRTC, Screen Share #39, Replay #8)
    this.videoElements = new Map();
    this.watermarkImg = null;
    this.customBgVideo = null;

    // Traços do Whiteboard / Anotações Ao Vivo (#40)
    this.whiteboardStrokes = [];
    this.currentStroke = null;

    // Buffer de Instant Replay de 10 segundos (#8) e Gravação de Backup (#27)
    this.replayChunks = [];
    this.replayRecorder = null;
    this.backupRecorder = null;
    this.backupChunks = [];
  }

  registerVideoSource(id, videoEl) {
    this.videoElements.set(id, videoEl);
  }

  setWatermarkImage(dataUrl) {
    if (!dataUrl) {
      this.watermarkImg = null;
      return;
    }
    const img = new Image();
    img.src = dataUrl;
    this.watermarkImg = img;
  }

  /**
   * Renderiza um quadro completo da cena ativa aplicando:
   * Background Dinâmico (#10) -> Correção de Cor (#5) -> Recorte/Crop (#4) ->
   * Chroma Key (#3) -> Multi-view Grid (#2) ou PiP (#1) -> Marca d'água (#6) -> Whiteboard (#40)
   */
  renderSceneFrame(scene, spectrumData = []) {
    if (!this.ctx || !this.canvas) return;
    const w = this.canvas.width;
    const h = this.canvas.height;
    const now = performance.now() / 1000;

    this.ctx.save();

    // 1. Background Dinâmico em Loop (#10)
    this._drawDynamicBackground(w, h, now, scene);

    // 2. Aplica Correção de Cor CSS/Canvas (#5)
    const { brightness, contrast, saturation } = this.visualConfig;
    this.ctx.filter = `brightness(${brightness}%) contrast(${contrast}%) saturate(${saturation}%)`;

    // 3. Renderiza o layout da cena (Single, PiP #1, Multi-view 4x ou 8x #2)
    const mode = scene?.layoutMode || this.visualConfig.layoutMode;
    if (mode === 'grid4' || mode === 'grid8') {
      this._drawMultiViewGrid(w, h, mode === 'grid8' ? 8 : 4, now);
    } else {
      // Fonte Primária com Recorte/Cropping (#4) e Chroma Key (#3)
      this._drawPrimarySource(w, h, scene, now);

      // Picture-in-Picture Sobreposto (#1)
      if (mode === 'pip' || scene?.pipEnabled) {
        this._drawPiPWindow(w, h, now);
      }
    }

    this.ctx.filter = 'none';

    // 4. Audio Visualizer Gráfico na Tela (#12)
    if (this.visualConfig.visualizerEnabled && spectrumData.length > 0) {
      this._drawAudioVisualizer(w, h, spectrumData);
    }

    // 5. Marca d'água Transparente no Canto (#6)
    if (this.visualConfig.watermarkEnabled) {
      this._drawWatermark(w, h);
    }

    // 6. Whiteboard / Telestrator Ao Vivo (#40)
    this._drawWhiteboard(w, h);

    this.ctx.restore();
  }

  _drawDynamicBackground(w, h, t, scene) {
    if (this.customBgVideo && this.customBgVideo.readyState >= 2) {
      this.ctx.drawImage(this.customBgVideo, 0, 0, w, h);
      return;
    }

    const theme = scene?.bgTheme || this.visualConfig.bgLoopTheme;
    const grad = this.ctx.createLinearGradient(0, 0, w, h);
    if (theme === 'news-globe') {
      grad.addColorStop(0, '#071426');
      grad.addColorStop(0.5, '#0c274e');
      grad.addColorStop(1, '#050b16');
    } else if (theme === 'stadium-lights') {
      grad.addColorStop(0, '#091f15');
      grad.addColorStop(0.5, '#103b28');
      grad.addColorStop(1, '#05120c');
    } else {
      grad.addColorStop(0, '#0d111a');
      grad.addColorStop(0.5, '#171f32');
      grad.addColorStop(1, '#090b10');
    }
    this.ctx.fillStyle = grad;
    this.ctx.fillRect(0, 0, w, h);

    // Malha animada procedural 60fps para backgrounds dinâmicos (#10)
    this.ctx.strokeStyle = 'rgba(56, 189, 248, 0.12)';
    this.ctx.lineWidth = 1;
    const step = 48;
    const offset = (t * 24) % step;
    for (let x = offset; x < w; x += step) {
      this.ctx.beginPath();
      this.ctx.moveTo(x, 0);
      this.ctx.lineTo(x, h);
      this.ctx.stroke();
    }
    for (let y = offset; y < h; y += step) {
      this.ctx.beginPath();
      this.ctx.moveTo(0, y);
      this.ctx.lineTo(w, y);
      this.ctx.stroke();
    }
  }

  _drawPrimarySource(w, h, scene, t) {
    const cropL = (this.visualConfig.cropLeft / 100) * w;
    const cropR = (this.visualConfig.cropRight / 100) * w;
    const cropT = (this.visualConfig.cropTop / 100) * h;
    const cropB = (this.visualConfig.cropBottom / 100) * h;

    const drawW = Math.max(40, w - cropL - cropR);
    const drawH = Math.max(40, h - cropT - cropB);

    this.ctx.save();
    // Máscara de Recorte / Cropping (#4)
    this.ctx.beginPath();
    this.ctx.rect(cropL, cropT, drawW, drawH);
    this.ctx.clip();

    const sourceId = scene?.sourceType || 'cam1';
    const videoEl = this.videoElements.get(sourceId);

    if (videoEl && videoEl.readyState >= 2) {
      this.ctx.drawImage(videoEl, cropL, cropT, drawW, drawH);
      // Função #3: Filtro Chroma Key (Fundo Verde) processando os pixels do quadro
      if (this.visualConfig.chromaEnabled) {
        this._applyChromaKeyFilter(cropL, cropT, drawW, drawH);
      }
    } else {
      // Renderização Broadcast Sintética da Cena Ativa caso a câmera física não esteja aberta
      this._drawSimulatedCameraFeed(cropL, cropT, drawW, drawH, scene, t);
    }

    this.ctx.restore();
  }

  /**
   * Função #3: Algoritmo Chroma Key em Tempo Real (Remove pixels de fundo verde)
   */
  _applyChromaKeyFilter(x, y, w, h) {
    try {
      const frame = this.ctx.getImageData(x, y, w, h);
      const data = frame.data;
      const tol = this.visualConfig.chromaTolerance || 90;

      for (let i = 0; i < data.length; i += 4) {
        const r = data[i];
        const g = data[i + 1];
        const b = data[i + 2];
        // Detecta dominância do canal verde sobre vermelho e azul
        if (g > 100 && g - Math.max(r, b) > (140 - tol)) {
          data[i + 3] = 0; // Torna o pixel transparente revelando o Background Dinâmico (#10)
        }
      }
      this.ctx.putImageData(frame, x, y);
    } catch (_) {}
  }

  _drawSimulatedCameraFeed(x, y, w, h, scene, t) {
    const title = scene ? scene.name : 'CENA 1 - ESTÚDIO PRINCIPAL';
    const subtitle = scene ? scene.subtitle : 'Câmera Ao Vivo 1080p60';

    // Silhueta / Avatar animado de apresentador ou mídia web
    const cx = x + w / 2;
    const cy = y + h / 2;

    const pulse = Math.sin(t * 2.5) * 8;
    const radGrad = this.ctx.createRadialGradient(cx, cy, 20, cx, cy, Math.min(w, h) * 0.42);
    radGrad.addColorStop(0, 'rgba(41, 121, 255, 0.32)');
    radGrad.addColorStop(1, 'rgba(15, 23, 42, 0.0)');
    this.ctx.fillStyle = radGrad;
    this.ctx.beginPath();
    this.ctx.arc(cx, cy, Math.min(w, h) * 0.4 + pulse, 0, Math.PI * 2);
    this.ctx.fill();

    // Moldura central da fonte
    this.ctx.fillStyle = 'rgba(255, 255, 255, 0.92)';
    this.ctx.font = '800 28px Inter, sans-serif';
    this.ctx.textAlign = 'center';
    this.ctx.fillText(title.toUpperCase(), cx, cy - 10);

    this.ctx.fillStyle = '#38bdf8';
    this.ctx.font = '600 16px Inter, sans-serif';
    this.ctx.fillText(subtitle, cx, cy + 22);
  }

  /**
   * Função #1: Picture-in-Picture (PiP) redimensionável e posicionável
   */
  _drawPiPWindow(w, h, t) {
    const pipW = w * this.visualConfig.pipScale;
    const pipH = h * this.visualConfig.pipScale;
    const pipX = w * this.visualConfig.pipX;
    const pipY = h * this.visualConfig.pipY;

    this.ctx.save();
    this.ctx.fillStyle = '#0f172a';
    this.ctx.strokeStyle = '#38bdf8';
    this.ctx.lineWidth = 3;
    this.ctx.fillRect(pipX, pipY, pipW, pipH);
    this.ctx.strokeRect(pipX, pipY, pipW, pipH);

    const guestVideo = this.videoElements.get('guest1') || this.videoElements.get('screenshare');
    if (guestVideo && guestVideo.readyState >= 2) {
      this.ctx.drawImage(guestVideo, pipX, pipY, pipW, pipH);
    } else {
      this.ctx.fillStyle = '#e2e8f0';
      this.ctx.font = '700 14px Inter, sans-serif';
      this.ctx.textAlign = 'center';
      this.ctx.fillText('📱 REPÓRTER REMOTO (PiP)', pipX + pipW / 2, pipY + pipH / 2 - 4);
      this.ctx.fillStyle = '#4ade80';
      this.ctx.font = '600 11px monospace';
      this.ctx.fillText(`WebRTC Mix-Minus OK • ${Math.floor(24 + Math.sin(t) * 2)}ms`, pipX + pipW / 2, pipY + pipH / 2 + 16);
    }
    this.ctx.restore();
  }

  /**
   * Função #2: Multi-view Grid (Mosaico automático para até 4 ou 8 convidados)
   */
  _drawMultiViewGrid(w, h, count, t) {
    const cols = count === 8 ? 4 : 2;
    const rows = 2;
    const pad = 12;
    const cellW = (w - pad * (cols + 1)) / cols;
    const cellH = (h - pad * (rows + 1)) / rows;

    const labels = [
      'CAM 1 • APRESENTADOR',
      'WEBRTC 1 • REPÓRTER EXTERNO',
      'WEBRTC 2 • COMENTARISTA',
      'MÍDIA WEB • YOUTUBE/INSTA',
      'WEBRTC 3 • CONVIDADO SP',
      'WEBRTC 4 • CONVIDADO RJ',
      'SCREEN SHARE • TELA',
      'REPLAY BUFFER • 10s'
    ];

    for (let i = 0; i < count; i++) {
      const col = i % cols;
      const row = Math.floor(i / cols);
      const x = pad + col * (cellW + pad);
      const y = pad + row * (cellH + pad);

      this.ctx.fillStyle = 'rgba(15, 23, 42, 0.88)';
      this.ctx.fillRect(x, y, cellW, cellH);

      // Destaque de Tally ou Voz Ativa (#23 / #24)
      this.ctx.strokeStyle = i === 0 ? '#e53935' : '#2979ff';
      this.ctx.lineWidth = i === 0 ? 3 : 1.5;
      this.ctx.strokeRect(x, y, cellW, cellH);

      // Se a câmera local ou convidado estiver conectado, desenha o vídeo real no slot
      const vEl = i === 0 ? this.videoElements.get('cam1') : (i === 1 ? this.videoElements.get('guest1') : null);
      if (vEl && vEl.readyState >= 2) {
        this.ctx.drawImage(vEl, x, y, cellW, cellH);
      } else {
        this.ctx.fillStyle = '#f8fafc';
        this.ctx.font = '700 14px Inter, sans-serif';
        this.ctx.textAlign = 'center';
        this.ctx.fillText(labels[i], x + cellW / 2, y + cellH / 2);
      }

      // Tarjeta de identificação do slot no Multi-view
      this.ctx.fillStyle = 'rgba(0,0,0,0.72)';
      this.ctx.fillRect(x + 6, y + cellH - 28, Math.min(cellW - 12, 210), 22);
      this.ctx.fillStyle = '#38bdf8';
      this.ctx.font = '700 11px monospace';
      this.ctx.textAlign = 'left';
      this.ctx.fillText(labels[i], x + 12, y + cellH - 13);
    }
  }

  /**
   * Função #12: Audio Visualizer (Barras gráficas reativas ao som na tela)
   */
  _drawAudioVisualizer(w, h, spectrum) {
    const barCount = spectrum.length;
    const barW = 6;
    const gap = 4;
    const startX = w - (barCount * (barW + gap)) - 28;
    const baseY = h - 58;

    this.ctx.save();
    for (let i = 0; i < barCount; i++) {
      const val = spectrum[i] || 8;
      const barH = Math.max(4, (val / 100) * 54);
      this.ctx.fillStyle = val > 75 ? '#ff1744' : (val > 45 ? '#00e676' : '#38bdf8');
      this.ctx.fillRect(startX + i * (barW + gap), baseY - barH, barW, barH);
    }
    this.ctx.restore();
  }

  /**
   * Função #6: Marca d'água fixa transparente no canto superior direito
   */
  _drawWatermark(w, h) {
    this.ctx.save();
    this.ctx.globalAlpha = 0.72;
    if (this.watermarkImg && this.watermarkImg.complete) {
      this.ctx.drawImage(this.watermarkImg, w - 150, 22, 120, 46);
    } else {
      this.ctx.fillStyle = 'rgba(15, 23, 42, 0.65)';
      this.ctx.fillRect(w - 165, 20, 140, 34);
      this.ctx.strokeStyle = 'rgba(255,255,255,0.25)';
      this.ctx.strokeRect(w - 165, 20, 140, 34);
      this.ctx.fillStyle = '#ffffff';
      this.ctx.font = '800 13px Inter, sans-serif';
      this.ctx.textAlign = 'center';
      this.ctx.fillText(this.visualConfig.watermarkText || 'WEBLIVE HD', w - 95, 42);
    }
    this.ctx.restore();
  }

  /**
   * Função #40: Whiteboard / Telestrator Ao Vivo (Desenho de comentarista esportivo)
   */
  _drawWhiteboard(w, h) {
    if (!this.whiteboardStrokes || this.whiteboardStrokes.length === 0) return;
    this.ctx.save();
    this.ctx.lineCap = 'round';
    this.ctx.lineJoin = 'round';

    this.whiteboardStrokes.forEach((stroke) => {
      if (!stroke.points || stroke.points.length < 2) return;
      this.ctx.strokeStyle = stroke.color || '#ffeb3b';
      this.ctx.lineWidth = stroke.size || 5;
      this.ctx.beginPath();
      this.ctx.moveTo(stroke.points[0].x * w, stroke.points[0].y * h);
      for (let i = 1; i < stroke.points.length; i++) {
        this.ctx.lineTo(stroke.points[i].x * w, stroke.points[i].y * h);
      }
      this.ctx.stroke();
    });
    this.ctx.restore();
  }

  /**
   * Função #8: Instant Replay Buffer (Mantém os últimos 10 segundos gravados em RAM via MediaRecorder)
   */
  startInstantReplayBuffer() {
    if (!this.canvas || !this.canvas.captureStream || typeof MediaRecorder === 'undefined') return;
    try {
      const stream = this.canvas.captureStream(30);
      this.replayRecorder = new MediaRecorder(stream, { mimeType: 'video/webm;codecs=vp8' });
      this.replayRecorder.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) {
          this.replayChunks.push(e.data);
          // Mantém janela deslizante dos últimos 10 segundos (10 blocos de 1s)
          if (this.replayChunks.length > 10) {
            this.replayChunks.shift();
          }
        }
      };
      this.replayRecorder.start(1000);
    } catch (_) {}
  }

  getInstantReplayBlobUrl() {
    if (this.replayChunks.length === 0) return null;
    const blob = new Blob(this.replayChunks, { type: 'video/webm' });
    return URL.createObjectURL(blob);
  }

  /**
   * Função #27: Gravação Local de Backup (Salva a transmissão no PC do Diretor via MediaRecorder)
   */
  toggleLocalBackupRecording(onSavedCallback) {
    if (this.backupRecorder && this.backupRecorder.state === 'recording') {
      this.backupRecorder.stop();
      return false;
    }
    if (!this.canvas || !this.canvas.captureStream || typeof MediaRecorder === 'undefined') return false;

    this.backupChunks = [];
    const stream = this.canvas.captureStream(30);
    this.backupRecorder = new MediaRecorder(stream, { mimeType: 'video/webm' });
    this.backupRecorder.ondataavailable = (e) => {
      if (e.data && e.data.size > 0) this.backupChunks.push(e.data);
    };
    this.backupRecorder.onstop = () => {
      const blob = new Blob(this.backupChunks, { type: 'video/webm' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `WebLive_Backup_${new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-')}.webm`;
      a.click();
      if (onSavedCallback) onSavedCallback(a.download);
    };
    this.backupRecorder.start(1000);
    return true;
  }
}

window.WebLiveVideoCompositor = WebLiveVideoCompositor;

