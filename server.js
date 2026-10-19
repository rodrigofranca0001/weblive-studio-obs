/**
 * WebLive Studio - Servidor HTTP, API REST (Stream Deck #46) e Signaling WebSocket / WebRTC
 * Funciona de forma zero-dependency (nativo Node.js + suporte a WS/SSE + BroadcastChannel no cliente).
 */
const http = require('http');
const fs = require('fs');
const path = require('path');

const PORT = process.env.PORT || 3000;
const PUBLIC_DIR = path.join(__dirname, 'public');

// Clientes conectados via Server-Sent Events (SSE) para sincronização cross-device e Stream Deck API
const sseClients = new Set();

function broadcastEvent(payload) {
  const data = `data: ${JSON.stringify(payload)}\n\n`;
  for (const client of sseClients) {
    client.write(data);
  }
}

const MIME_TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.svg': 'image/svg+xml',
  '.webm': 'video/webm',
  '.mp4': 'video/mp4'
};

const server = http.createServer((req, res) => {
  // CORS Headers para permitir controle externo (Stream Deck, Companion, Mobile)
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') {
    res.writeHead(204);
    res.end();
    return;
  }

  const parsedUrl = new URL(req.url, `http://${req.headers.host}`);
  const pathname = parsedUrl.pathname;

  // 1. Stream de Eventos em Tempo Real (SSE Sync & WebRTC Signaling entre dispositivos)
  if (pathname === '/api/events' && req.method === 'GET') {
    res.writeHead(200, {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      'Connection': 'keep-alive'
    });
    res.write(`data: ${JSON.stringify({ type: 'CONNECTED', timestamp: Date.now() })}\n\n`);
    sseClients.add(res);
    req.on('close', () => sseClients.delete(res));
    return;
  }

  // 2. Endpoint de Sincronização e Signaling WebRTC (POST /api/sync)
  if (pathname === '/api/sync' && req.method === 'POST') {
    let body = '';
    req.on('data', chunk => { body += chunk; });
    req.on('end', () => {
      try {
        const payload = JSON.parse(body);
        broadcastEvent(payload);
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ ok: true }));
      } catch (err) {
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: 'Invalid JSON' }));
      }
    });
    return;
  }

  // 3. Função #46: API Endpoints Customizados para Elgato Stream Deck / Bitfocus Companion
  // Exemplo: GET ou POST /api/streamdeck?action=scene&target=1 ou /api/streamdeck?action=cut
  if (pathname === '/api/streamdeck') {
    const action = parsedUrl.searchParams.get('action') || 'cut';
    const target = parsedUrl.searchParams.get('target') || '';
    const value = parsedUrl.searchParams.get('value') || '';
    const cmdPayload = {
      type: 'STREAMDECK_COMMAND',
      action,
      target,
      value,
      timestamp: Date.now()
    };
    broadcastEvent(cmdPayload);
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ status: 'dispatched', command: cmdPayload }));
    return;
  }

  // 4. Função #33: Webhook para Alertas de Doação / Superchat / Inscritos
  if (pathname === '/api/webhook/alert' && (req.method === 'POST' || req.method === 'GET')) {
    const user = parsedUrl.searchParams.get('user') || 'Apoiador Ao Vivo';
    const amount = parsedUrl.searchParams.get('amount') || 'R$ 50,00';
    const message = parsedUrl.searchParams.get('msg') || 'Parabéns pela transmissão!';
    broadcastEvent({
      type: 'WEBHOOK_ALERT',
      alertType: 'superchat',
      user,
      amount,
      message,
      timestamp: Date.now()
    });
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ triggered: true, user, amount }));
    return;
  }

  // 5. Servir arquivos estáticos da pasta /public
  let safePath = pathname === '/' ? '/index.html' : pathname;
  const filePath = path.join(PUBLIC_DIR, path.normalize(safePath).replace(/^(\.\.[\/\\])+/, ''));

  fs.stat(filePath, (err, stats) => {
    if (err || !stats.isFile()) {
      res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
      res.end('404 - Arquivo não encontrado no WebLive Studio');
      return;
    }
    const ext = path.extname(filePath).toLowerCase();
    res.writeHead(200, { 'Content-Type': MIME_TYPES[ext] || 'application/octet-stream' });
    fs.createReadStream(filePath).pipe(res);
  });
});

server.listen(PORT, () => {
  console.log(`\n=============================================================`);
  console.log(`🎬 WEBLIVE STUDIO RODANDO EM: http://localhost:${PORT}`);
  console.log(`-------------------------------------------------------------`);
  console.log(`🎛️  Painel do Diretor : http://localhost:${PORT}/index.html`);
  console.log(`📺 Tela OBS (Output) : http://localhost:${PORT}/output.html`);
  console.log(`🧼 Saída Clean Feed  : http://localhost:${PORT}/output.html?clean=1`);
  console.log(`📱 Entrada Repórter  : http://localhost:${PORT}/guest.html?guest=Reporter1`);
  console.log(`⚡ Stream Deck API   : http://localhost:${PORT}/api/streamdeck?action=scene&target=1`);
  console.log(`=============================================================\n`);
});

