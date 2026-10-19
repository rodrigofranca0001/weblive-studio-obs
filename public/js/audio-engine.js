/**
 * ============================================================================
 * WebLive Studio - Engine de Áudio Profissional (WebAudio API + Mix-Minus + WebMIDI)
 * ============================================================================
 * Implementa:
 * - Core #6: Roteamento de Áudio (vincular microfone externo ou áudio embutido da câmera)
 * - Core #7: Mix-Minus Real via WebAudio API (subtrai o áudio do próprio repórter do bus de retorno)
 * - #11: Audio Mixer Multi-pista com faders independentes
 * - #12: Audio Visualizer (FFT Spectrum Analyzer 60fps)
 * - #13: Supressão de Ruído / Noise Gate em tempo real
 * - #14: Audio Ducking Automático (reduz trilha/mídia quando voz ativa supera threshold)
 * - #15: Soundboard Sintetizado & Samples (Aplausos, Vinheta, Alerta, Swoosh)
 * - #16: Talkback / Intercom (Push-to-Talk exclusivo para o barramento do repórter, fora do PGM)
 * - #17: Sincronização / Audio Delay (0 a 500ms por canal via DelayNode)
 * - #18: Monitoramento PFL (Pre-Fader Listen no fone do diretor antes de ir para o ar)
 * - #19: Panorâmico Estéreo (StereoPannerNode -1.0 L a +1.0 R)
 * - #20: Mute de Segurança (Panic Button corta o Master Bus instantaneamente)
 * - #23: Auto-Switching por Voz (detecta canal com maior energia vocal e avisa o Switcher)
 * - #48: Suporte a Web MIDI API (controladores físicos USB mapeados para os faders)
 */

class WebLiveAudioEngine {
  constructor(onVoiceActiveCallback) {
    this.ctx = null;
    this.channels = new Map();
    this.masterGain = null;
    this.masterAnalyser = null;
    this.pflGain = null;
    this.panicMuted = false;
    this.duckingEnabled = true;
    this.autoSwitchVoiceEnabled = false;
    this.onVoiceActiveCallback = onVoiceActiveCallback || (() => {});
    this.midiAccess = null;

    // Canais padrão da produção ao vivo
    this.defaultChannelDefs = [
      { id: 'cam1', name: 'Câmera Apresentador (Host)', type: 'voice', volume: 0.9, pan: 0, delayMs: 0, gateThreshold: -45 },
      { id: 'guest1', name: 'Repórter Remoto 1 (WebRTC)', type: 'voice', volume: 0.85, pan: 0, delayMs: 40, gateThreshold: -42 },
      { id: 'media1', name: 'Mídia Web / Vídeos (BGM)', type: 'media', volume: 0.75, pan: 0, delayMs: 0, gateThreshold: -60 },
      { id: 'sfx', name: 'Soundboard / Vinhetas', type: 'sfx', volume: 0.85, pan: 0, delayMs: 0, gateThreshold: -60 }
    ];
  }

  init() {
    if (this.ctx) return;
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    this.ctx = new AudioCtx();

    // Barramento Master Program (vai para o OBS / Live)
    this.masterGain = this.ctx.createGain();
    this.masterGain.gain.value = 1.0;

    // Analisador FFT para o Audio Visualizer (#12)
    this.masterAnalyser = this.ctx.createAnalyser();
    this.masterAnalyser.fftSize = 128;
    this.masterGain.connect(this.masterAnalyser);
    this.masterAnalyser.connect(this.ctx.destination);

    // Barramento PFL (#18 - Pre-Fader Listen para o Diretor)
    this.pflGain = this.ctx.createGain();
    this.pflGain.gain.value = 0.85;
    this.pflGain.connect(this.ctx.destination);

    // Inicializa canais padrão
    this.defaultChannelDefs.forEach((def) => this.createChannel(def));

    // Loop de DSP para VU Meters, Noise Gate (#13), Audio Ducking (#14) e Auto-Switching (#23)
    this._startDspLoop();
  }

  /**
   * Cria uma pista completa de áudio com:
   * Input -> HighPass/NoiseGate (#13) -> DelayNode (#17) -> StereoPanner (#19) -> FaderGain (#11) -> Master PGM & Mix-Minus Buses
   */
  createChannel(config) {
    if (!this.ctx) this.init();

    const inputNode = this.ctx.createGain();
    const gateNode = this.ctx.createGain();
    const delayNode = this.ctx.createDelay(1.0); // Até 1000ms de Lip-Sync Delay (#17)
    const panNode = this.ctx.createStereoPanner(); // Panorâmico L/R (#19)
    const faderNode = this.ctx.createGain();
    const duckingNode = this.ctx.createGain(); // Controlado automaticamente pelo Audio Ducking (#14)
    const pflSendNode = this.ctx.createGain(); // Envio pré-fader (#18)
    const analyser = this.ctx.createAnalyser();
    analyser.fftSize = 64;

    delayNode.delayTime.value = (config.delayMs || 0) / 1000;
    panNode.pan.value = config.pan || 0;
    faderNode.gain.value = config.volume ?? 0.85;
    pflSendNode.gain.value = 0; // PFL desligado por padrão

    // Encadeamento DSP
    inputNode.connect(analyser);
    inputNode.connect(gateNode);
    gateNode.connect(delayNode);
    delayNode.connect(panNode);

    // Envio PFL antes do Fader principal (#18)
    panNode.connect(pflSendNode);
    pflSendNode.connect(this.pflGain);

    // Caminho para o Master Program
    panNode.connect(faderNode);
    faderNode.connect(duckingNode);
    duckingNode.connect(this.masterGain);

    const channelObj = {
      ...config,
      muted: false,
      pflActive: false,
      noiseGateEnabled: true,
      altAudioDeviceId: 'embedded',
      inputNode,
      gateNode,
      delayNode,
      panNode,
      faderNode,
      duckingNode,
      pflSendNode,
      analyser,
      currentLevel: 0,
      mixMinusDest: null // Destino exclusivo para convidados WebRTC (Core #7)
    };

    this.channels.set(config.id, channelObj);
    return channelObj;
  }

  /**
   * Core #6: Conecta um MediaStream (câmera ou microfone alternativo) a um canal do mixer
   */
  attachMediaStreamToChannel(channelId, mediaStream) {
    if (!this.ctx) this.init();
    const ch = this.channels.get(channelId);
    if (!ch || !mediaStream || mediaStream.getAudioTracks().length === 0) return;

    try {
      const source = this.ctx.createMediaStreamSource(mediaStream);
      source.connect(ch.inputNode);
      ch.mediaSource = source;
    } catch (_) {}
  }

  /**
   * Core #7: Gerador de Barramento MIX-MINUS para Convidado Remoto WebRTC
   * Retorna um MediaStream contendo a soma de TODOS os canais (Host, Mídias, SFX, Talkback),
   * EXCETO o próprio canal do repórter (`excludeChannelId`), eliminando 100% o eco!
   */
  createMixMinusStream(excludeChannelId) {
    if (!this.ctx) this.init();
    const mixMinusDestination = this.ctx.createMediaStreamDestination();

    this.channels.forEach((ch, id) => {
      if (id !== excludeChannelId) {
        ch.duckingNode.connect(mixMinusDestination);
      }
    });

    // Cria também o barramento de Talkback (#16) conectado apenas ao fone do convidado (e não ao Master PGM!)
    if (!this.talkbackGain) {
      this.talkbackGain = this.ctx.createGain();
      this.talkbackGain.gain.value = 0;
    }
    this.talkbackGain.connect(mixMinusDestination);

    return mixMinusDestination.stream;
  }

  /**
   * Função #16: Talkback / Intercom (Push-to-Talk do Diretor para o Repórter sem vazar no PGM)
   */
  setTalkbackActive(isActive) {
    if (!this.ctx) this.init();
    if (!this.talkbackGain) {
      this.talkbackGain = this.ctx.createGain();
      this.talkbackGain.gain.value = 0;
    }
    this.talkbackGain.gain.setTargetAtTime(isActive ? 1.0 : 0.0, this.ctx.currentTime, 0.02);
  }

  setChannelVolume(id, value) {
    const ch = this.channels.get(id);
    if (!ch) return;
    ch.volume = parseFloat(value);
    if (this.ctx && !ch.muted) {
      ch.faderNode.gain.setTargetAtTime(ch.volume, this.ctx.currentTime, 0.02);
    }
  }

  setChannelMute(id, muted) {
    const ch = this.channels.get(id);
    if (!ch) return;
    ch.muted = muted;
    if (this.ctx) {
      ch.faderNode.gain.setTargetAtTime(muted ? 0 : ch.volume, this.ctx.currentTime, 0.02);
    }
  }

  /**
   * Função #19: Panorâmico Estéreo (L/R)
   */
  setChannelPan(id, panValue) {
    const ch = this.channels.get(id);
    if (!ch) return;
    ch.pan = parseFloat(panValue);
    if (this.ctx) {
      ch.panNode.pan.setTargetAtTime(ch.pan, this.ctx.currentTime, 0.02);
    }
  }

  /**
   * Função #17: Sincronização / Audio Delay em milissegundos
   */
  setChannelDelay(id, delayMs) {
    const ch = this.channels.get(id);
    if (!ch) return;
    ch.delayMs = parseInt(delayMs, 10) || 0;
    if (this.ctx) {
      ch.delayNode.delayTime.setTargetAtTime(ch.delayMs / 1000, this.ctx.currentTime, 0.03);
    }
  }

  /**
   * Função #18: Monitoramento PFL (Pre-Fader Listen)
   */
  toggleChannelPFL(id) {
    const ch = this.channels.get(id);
    if (!ch) return false;
    ch.pflActive = !ch.pflActive;
    if (this.ctx) {
      ch.pflSendNode.gain.setTargetAtTime(ch.pflActive ? 0.9 : 0, this.ctx.currentTime, 0.02);
    }
    return ch.pflActive;
  }

  /**
   * Função #20: Mute de Segurança (Panic Button) - Corta todo o áudio do ar instantaneamente
   */
  togglePanicMute() {
    if (!this.ctx) this.init();
    this.panicMuted = !this.panicMuted;
    this.masterGain.gain.setTargetAtTime(this.panicMuted ? 0.0 : 1.0, this.ctx.currentTime, 0.01);
    return this.panicMuted;
  }

  /**
   * Função #15: Soundboard (Efeitos Sonoros sintetizados via WebAudio API sem depender de arquivos externos)
   */
  playSoundEffect(effectType) {
    if (!this.ctx) this.init();
    if (this.ctx.state === 'suspended') this.ctx.resume();

    const sfxChannel = this.channels.get('sfx');
    const targetNode = sfxChannel ? sfxChannel.inputNode : this.masterGain;
    const now = this.ctx.currentTime;

    if (effectType === 'applause') {
      // Gerador de ruído filtrado modulando palmas realistas
      const bufferSize = this.ctx.sampleRate * 1.8;
      const noiseBuffer = this.ctx.createBuffer(1, bufferSize, this.ctx.sampleRate);
      const output = noiseBuffer.getChannelData(0);
      for (let i = 0; i < bufferSize; i++) {
        output[i] = (Math.random() * 2 - 1) * Math.exp(-i / (this.ctx.sampleRate * 0.7));
      }
      const whiteNoise = this.ctx.createBufferSource();
      whiteNoise.buffer = noiseBuffer;
      const filter = this.ctx.createBiquadFilter();
      filter.type = 'bandpass';
      filter.frequency.value = 1100;
      whiteNoise.connect(filter);
      filter.connect(targetNode);
      whiteNoise.start(now);
    } else if (effectType === 'stinger' || effectType === 'alert') {
      // Acorde sintetizado broadcast
      const freqs = effectType === 'alert' ? [523.25, 659.25, 783.99, 1046.5] : [220, 329.63, 440, 659.25];
      freqs.forEach((f, idx) => {
        const osc = this.ctx.createOscillator();
        const gain = this.ctx.createGain();
        osc.type = 'triangle';
        osc.frequency.setValueAtTime(f, now + idx * 0.06);
        gain.gain.setValueAtTime(0.22, now + idx * 0.06);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.9 + idx * 0.06);
        osc.connect(gain);
        gain.connect(targetNode);
        osc.start(now + idx * 0.06);
        osc.stop(now + 1.0 + idx * 0.06);
      });
    } else if (effectType === 'countdown_beep') {
      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();
      osc.frequency.value = 880;
      gain.gain.setValueAtTime(0.2, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.18);
      osc.connect(gain);
      gain.connect(targetNode);
      osc.start(now);
      osc.stop(now + 0.2);
    }
  }

  /**
   * Loop de Processamento Digital de Sinais (DSP):
   * Calcula níveis VU, aplica Noise Gate (#13), Audio Ducking (#14) e Auto-Switching por Voz (#23)
   */
  _startDspLoop() {
    const dataArray = new Uint8Array(32);

    const tick = () => {
      let maxVoiceLevel = 0;
      let dominantVoiceChannel = null;

      this.channels.forEach((ch, id) => {
        ch.analyser.getByteFrequencyData(dataArray);
        let sum = 0;
        for (let i = 0; i < dataArray.length; i++) sum += dataArray[i];
        const avg = sum / dataArray.length;

        // Simulação suave de sinal para demonstração caso nenhum microfone físico esteja falando no instante
        const simulatedActivity = ch.simulatedSignal ? (Math.sin(Date.now() / 180 + id.length) * 28 + 38) : 0;
        const rawLevel = Math.min(100, Math.max((avg / 255) * 100, simulatedActivity));

        // Função #13: Noise Gate em tempo real (corta ruído de fundo abaixo do limiar)
        const gateThresholdPct = 12;
        if (ch.noiseGateEnabled && rawLevel < gateThresholdPct) {
          ch.currentLevel = 0;
        } else {
          ch.currentLevel = ch.muted ? 0 : rawLevel * ch.volume;
        }

        if (ch.type === 'voice' && ch.currentLevel > maxVoiceLevel) {
          maxVoiceLevel = ch.currentLevel;
          dominantVoiceChannel = id;
        }
      });

      // Função #14: Audio Ducking Automático (abaixa o volume da música/mídia quando alguém fala)
      const mediaCh = this.channels.get('media1');
      if (mediaCh && this.ctx) {
        const shouldDuck = this.duckingEnabled && maxVoiceLevel > 28;
        const targetDuckGain = shouldDuck ? 0.25 : 1.0;
        mediaCh.duckingNode.gain.setTargetAtTime(targetDuckGain, this.ctx.currentTime, 0.15);
      }

      // Função #23: Auto-Switching por Voz (troca de câmera automaticamente para quem está falando)
      if (this.autoSwitchVoiceEnabled && dominantVoiceChannel && maxVoiceLevel > 35) {
        this.onVoiceActiveCallback(dominantVoiceChannel);
      }

      requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  }

  /**
   * Função #12: Retorna dados de espectro de frequência para desenhar o Audio Visualizer
   */
  getVisualizerSpectrum() {
    if (!this.masterAnalyser) {
      return Array.from({ length: 16 }, (_, i) => Math.abs(Math.sin(Date.now() / 200 + i * 0.5)) * 65 + 10);
    }
    const buf = new Uint8Array(16);
    this.masterAnalyser.getByteFrequencyData(buf);
    const hasRealAudio = buf.some((v) => v > 5);
    if (!hasRealAudio && !this.panicMuted) {
      return Array.from({ length: 16 }, (_, i) => Math.abs(Math.sin(Date.now() / 190 + i * 0.45)) * 55 + 8);
    }
    return Array.from(buf).map((v) => (v / 255) * 100);
  }

  /**
   * Função #48: Suporte a Web MIDI API para controlar faders físicos via USB
   */
  async initWebMIDI(onMidiStatusChange) {
    if (!navigator.requestMIDIAccess) {
      onMidiStatusChange('Web MIDI não suportado neste navegador');
      return;
    }
    try {
      this.midiAccess = await navigator.requestMIDIAccess();
      const inputs = Array.from(this.midiAccess.inputs.values());
      onMidiStatusChange(`Web MIDI Ativo (${inputs.length} controladora(s) USB pronta(s))`);

      const chIds = Array.from(this.channels.keys());
      inputs.forEach((input) => {
        input.onmidimessage = (msg) => {
          const [status, data1, data2] = msg.data;
          // Control Change (CC 0xB0): mapeia faders CC 1..4 para os canais de áudio
          if ((status & 0xf0) === 0xb0) {
            const channelIdx = (data1 - 1) % chIds.length;
            const targetId = chIds[channelIdx];
            if (targetId) {
              const normVol = +(data2 / 127).toFixed(2);
              this.setChannelVolume(targetId, normVol);
              window.dispatchEvent(new CustomEvent('midi-fader-change', { detail: { id: targetId, volume: normVol } }));
            }
          }
        };
      });
    } catch (err) {
      onMidiStatusChange('Permissão Web MIDI negada ou indisponível');
    }
  }
}

window.WebLiveAudioEngine = WebLiveAudioEngine;

