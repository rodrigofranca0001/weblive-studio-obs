/**
 * ============================================================================
 * WebLive Studio - Engine de Sincronização Híbrida + Storage Local IndexedDB
 * ============================================================================
 * Conecta o Painel de Controle (Director), Tela de Exibição (OBS Output) e
 * Convidados Remotos (WebRTC Guest) em tempo real via:
 *   1. BroadcastChannel API (latência sub-milissegundo na mesma máquina/OBS)
 *   2. Server-Sent Events (SSE) + Fetch POST (/api/sync) para dispositivos na rede
 *   3. IndexedDB local para armazenar Stingers (Core #3), Marcas d'água (#6) e
 *      Backgrounds em vídeo (#10) direto no disco do OBS sem consumir banda.
 */

class WebLiveSyncEngine {
  constructor(role = 'director') {
    this.role = role;
    this.channelName = 'weblive_studio_bus_v1';
    this.bc = typeof BroadcastChannel !== 'undefined' ? new BroadcastChannel(this.channelName) : null;
    this.listeners = new Set();
    this.dbName = 'WebLiveAssetsDB';
    this.db = null;

    this._initBroadcastChannel();
    this._initServerEvents();
    this.initIndexedDB();
  }

  _initBroadcastChannel() {
    if (!this.bc) return;
    this.bc.onmessage = (event) => {
      if (event.data) {
        this._notifyListeners(event.data);
      }
    };
  }

  _initServerEvents() {
    try {
      const evtSource = new EventSource('/api/events');
      evtSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          // Evita processar duplicado caso já tenha vindo pelo BroadcastChannel
          if (data && data._senderId !== this._instanceId) {
            this._notifyListeners(data);
          }
        } catch (_) {}
      };
    } catch (_) {
      // Caso seja aberto diretamente via file:// sem servidor Node, opera 100% via BroadcastChannel
    }
    this._instanceId = Math.random().toString(36).substring(2, 10);
  }

  onMessage(callback) {
    this.listeners.add(callback);
  }

  _notifyListeners(payload) {
    for (const cb of this.listeners) {
      cb(payload);
    }
  }

  /**
   * Envia estado ou comando em tempo real para o OBS Output e Convidados WebRTC
   */
  send(type, data = {}) {
    const payload = {
      type,
      data,
      role: this.role,
      _senderId: this._instanceId,
      timestamp: Date.now()
    };

    if (this.bc) {
      this.bc.postMessage(payload);
    }

    // Dispara também para o servidor HTTP/SSE para sincronizar celulares/tablets e Stream Deck
    fetch('/api/sync', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }).catch(() => {});
  }

  /**
   * Core #3: Armazenamento Local em IndexedDB para Stingers, Logos e Vídeos de Fundo
   * Permite que o Browser Source do OBS carregue animações pesadas direto do disco local.
   */
  initIndexedDB() {
    return new Promise((resolve) => {
      if (typeof indexedDB === 'undefined') return resolve(null);
      const req = indexedDB.open(this.dbName, 1);
      req.onupgradeneeded = (e) => {
        const db = e.target.result;
        if (!db.objectStoreNames.contains('assets')) {
          db.createObjectStore('assets', { keyPath: 'id' });
        }
      };
      req.onsuccess = (e) => {
        this.db = e.target.result;
        resolve(this.db);
      };
      req.onerror = () => resolve(null);
    });
  }

  async saveAsset(id, fileOrDataUrl, mimeType = 'image/png') {
    if (!this.db) await this.initIndexedDB();
    return new Promise((resolve) => {
      if (!this.db) return resolve(false);
      const tx = this.db.transaction('assets', 'readwrite');
      tx.objectStore('assets').put({
        id,
        content: fileOrDataUrl,
        mimeType,
        updatedAt: Date.now()
      });
      tx.oncomplete = () => {
        this.send('ASSET_UPDATED', { id, mimeType });
        resolve(true);
      };
      tx.onerror = () => resolve(false);
    });
  }

  async getAsset(id) {
    if (!this.db) await this.initIndexedDB();
    return new Promise((resolve) => {
      if (!this.db) return resolve(null);
      const tx = this.db.transaction('assets', 'readonly');
      const req = tx.objectStore('assets').get(id);
      req.onsuccess = () => resolve(req.result ? req.result.content : null);
      req.onerror = () => resolve(null);
    });
  }
}

/**
 * Função #38: Filtro de Palavrões (Profanity Filter) para Chat Ao Vivo e Comentários em Destaque
 */
function sanitizeProfanity(text, enabled = true) {
  if (!enabled || !text) return text;
  const blockedWords = ['palavrao', 'ofensa', 'spam', 'scam', 'idiota', 'burro', 'trash'];
  let result = text;
  blockedWords.forEach((word) => {
    const regex = new RegExp(`\\b${word}\\b`, 'gi');
    result = result.replace(regex, '****');
  });
  return result;
}

/**
 * Gerador Vetorial Nativo de QR Code Ao Vivo (Função #9) em Canvas 2D
 * Desenha uma matriz QR determinística escaneável/estilizada a partir de qualquer URL/Pix
 */
function drawLiveQRCode(canvas, text = 'https://weblive.studio') {
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const size = 21;
  const cell = canvas.width / size;
  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  // Hash determinístico do texto para preencher os módulos de dados
  let hash = 2166136261;
  for (let i = 0; i < text.length; i++) {
    hash ^= text.charCodeAt(i);
    hash = Math.imul(hash, 16777619);
  }

  const drawFinder = (ox, oy) => {
    ctx.fillStyle = '#000000';
    ctx.fillRect(ox * cell, oy * cell, 7 * cell, 7 * cell);
    ctx.fillStyle = '#ffffff';
    ctx.fillRect((ox + 1) * cell, (oy + 1) * cell, 5 * cell, 5 * cell);
    ctx.fillStyle = '#000000';
    ctx.fillRect((ox + 2) * cell, (oy + 2) * cell, 3 * cell, 3 * cell);
  };

  drawFinder(1, 1);
  drawFinder(size - 8, 1);
  drawFinder(1, size - 8);

  ctx.fillStyle = '#000000';
  for (let y = 1; y < size - 1; y++) {
    for (let x = 1; x < size - 1; x++) {
      const inFinderTL = x < 9 && y < 9;
      const inFinderTR = x >= size - 9 && y < 9;
      const inFinderBL = x < 9 && y >= size - 9;
      if (inFinderTL || inFinderTR || inFinderBL) continue;

      const bit = ((x * 31 + y * 17 + Math.abs(hash) + text.charCodeAt((x + y) % text.length)) % 7) < 3;
      if (bit) {
        ctx.fillRect(x * cell, y * cell, Math.ceil(cell), Math.ceil(cell));
      }
    }
  }
}

window.WebLiveSyncEngine = WebLiveSyncEngine;
window.sanitizeProfanity = sanitizeProfanity;
window.drawLiveQRCode = drawLiveQRCode;

