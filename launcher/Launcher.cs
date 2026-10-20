/**
 * ============================================================================
 * WebLiveStudio.exe - Servidor e Launcher Nativo Windows (Zero-Dependency)
 * ============================================================================
 * Compilado nativamente para Windows (.NET 4.x / WinForms + HttpListener).
 * Roda em QUALQUER PC Windows 10/11 sem precisar instalar Node.js e sem abrir terminal!
 * - Servidor HTTP embutido (http://localhost:3000/)
 * - Barramento em tempo real SSE (/api/events e /api/sync)
 * - API Stream Deck (/api/streamdeck) e Webhook de Alertas (/api/webhook/alert)
 * - Interface gráfica (GUI) com botões de 1 clique para Diretor, OBS Output, Clean Feed e Repórter
 */

using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Reflection;
using System.Text;
using System.Threading;
using System.Windows.Forms;

[assembly: AssemblyTitle("WebLive Studio Launcher & Broadcast Server")]
[assembly: AssemblyProduct("WebLive Studio")]
[assembly: AssemblyVersion("1.1.0.0")]

namespace WebLiveStudio
{
    public class EmbeddedAsset
    {
        public byte[] Content;
        public string MimeType;
    }

    public class MainForm : Form
    {
        private HttpListener _listener;
        private Thread _serverThread;
        private volatile bool _running = false;
        private int _port = 3000;
        private string _publicDir;
        private readonly List<HttpListenerResponse> _sseClients = new List<HttpListenerResponse>();
        private readonly object _sseLock = new object();

        private Label _lblStatus;
        private TextBox _txtObsUrl;
        private NotifyIcon _trayIcon;

        public MainForm()
        {
            Text = "🎬 WebLive Studio — Central Executável Portátil (v1.1)";
            Size = new Size(560, 410);
            StartPosition = FormStartPosition.CenterScreen;
            FormBorderStyle = FormBorderStyle.FixedSingle;
            MaximizeBox = false;
            BackColor = Color.FromArgb(14, 18, 26);
            ForeColor = Color.FromArgb(240, 244, 248);
            Font = new Font("Segoe UI", 9.5f, FontStyle.Regular);

            _publicDir = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "public");

            BuildGui();
            // Se o Python estiver instalado na máquina e os scripts Python existirem,
            // podemos iniciar o motor Python Pro ou usar o servidor HTTP/SSE embutido 100% compatível!
            StartBroadcastServer();
        }

        private void BuildGui()
        {
            var headerPanel = new Panel
            {
                Dock = DockStyle.Top,
                Height = 64,
                BackColor = Color.FromArgb(22, 29, 42),
                Padding = new Padding(16)
            };

            var lblTitle = new Label
            {
                Text = "🔴 WEBLIVE STUDIO • SERVIDOR ATIVO",
                Font = new Font("Segoe UI", 13f, FontStyle.Bold),
                ForeColor = Color.FromArgb(255, 82, 82),
                AutoSize = true,
                Location = new Point(16, 12)
            };

            _lblStatus = new Label
            {
                Text = "Iniciando servidor local na porta 3000...",
                Font = new Font("Segoe UI", 9f, FontStyle.Regular),
                ForeColor = Color.FromArgb(148, 163, 184),
                AutoSize = true,
                Location = new Point(18, 38)
            };

            headerPanel.Controls.Add(lblTitle);
            headerPanel.Controls.Add(_lblStatus);
            Controls.Add(headerPanel);

            // Botões de Ação Rápida (1 Clique)
            var btnDirector = CreateStyledButton("🎛️ Abrir Painel do Diretor (Director Interface)", Color.FromArgb(41, 121, 255), new Point(20, 82), new Size(505, 44));
            btnDirector.Click += (s, e) => OpenUrl(string.Format("http://localhost:{0}/index.html", _port));
            Controls.Add(btnDirector);

            var btnOutput = CreateStyledButton("📺 Abrir Tela OBS (Output)", Color.FromArgb(229, 57, 53), new Point(20, 136), new Size(246, 40));
            btnOutput.Click += (s, e) => OpenUrl(string.Format("http://localhost:{0}/output.html", _port));
            Controls.Add(btnOutput);

            var btnClean = CreateStyledButton("🧼 Abrir Saída Clean Feed", Color.FromArgb(30, 41, 59), new Point(279, 136), new Size(246, 40));
            btnClean.Click += (s, e) => OpenUrl(string.Format("http://localhost:{0}/output.html?clean=1", _port));
            Controls.Add(btnClean);

            var btnGuest = CreateStyledButton("📱 Abrir Link do Repórter Remoto (WebRTC Call + Mix-Minus)", Color.FromArgb(0, 200, 83), new Point(20, 186), new Size(505, 38));
            btnGuest.ForeColor = Color.Black;
            btnGuest.Click += (s, e) => OpenUrl(string.Format("http://localhost:{0}/guest.html?guest=Reporter1", _port));
            Controls.Add(btnGuest);

            // Caixa com URL pronta para colar no OBS Browser Source
            var lblObsInfo = new Label
            {
                Text = "Link para copiar e colar na 'Fonte de Navegador' (Browser Source 1920x1080) do OBS:",
                ForeColor = Color.FromArgb(148, 163, 184),
                AutoSize = true,
                Location = new Point(20, 238)
            };
            Controls.Add(lblObsInfo);

            _txtObsUrl = new TextBox
            {
                ReadOnly = true,
                BackColor = Color.FromArgb(28, 35, 49),
                ForeColor = Color.FromArgb(56, 189, 248),
                BorderStyle = BorderStyle.FixedSingle,
                Font = new Font("Consolas", 10.5f, FontStyle.Bold),
                Location = new Point(20, 260),
                Size = new Size(390, 28),
                Text = "http://localhost:3000/output.html"
            };
            Controls.Add(_txtObsUrl);

            var btnCopyObs = CreateStyledButton("Copiar URL", Color.FromArgb(45, 55, 72), new Point(418, 258), new Size(107, 29));
            btnCopyObs.Click += (s, e) =>
            {
                Clipboard.SetText(_txtObsUrl.Text);
                MessageBox.Show("URL do OBS copiada para a área de transferência:\n" + _txtObsUrl.Text, "WebLive Studio", MessageBoxButtons.OK, MessageBoxIcon.Information);
            };
            Controls.Add(btnCopyObs);

            var lblFooter = new Label
            {
                Text = "💡 Portátil 100% Autônomo: Você pode copiar o arquivo WebLiveStudio.exe para qualquer PC Windows e executar com duplo clique (não requer terminal nem Node.js instalado).",
                ForeColor = Color.FromArgb(140, 155, 180),
                Location = new Point(20, 304),
                Size = new Size(505, 50)
            };
            Controls.Add(lblFooter);

            // Bandeja do sistema (System Tray)
            _trayIcon = new NotifyIcon
            {
                Text = "WebLive Studio (Rodando)",
                Icon = SystemIcons.Application,
                Visible = true
            };
            _trayIcon.DoubleClick += (s, e) => { Show(); WindowState = FormWindowState.Normal; };
        }

        private Button CreateStyledButton(string text, Color bg, Point loc, Size sz)
        {
            var btn = new Button
            {
                Text = text,
                BackColor = bg,
                ForeColor = Color.White,
                FlatStyle = FlatStyle.Flat,
                Font = new Font("Segoe UI", 9.5f, FontStyle.Bold),
                Location = loc,
                Size = sz,
                Cursor = Cursors.Hand
            };
            btn.FlatAppearance.BorderColor = Color.FromArgb(60, 255, 255, 255);
            return btn;
        }

        private void OpenUrl(string url)
        {
            try
            {
                Process.Start(new ProcessStartInfo(url) { UseShellExecute = true });
            }
            catch (Exception ex)
            {
                MessageBox.Show("Erro ao abrir navegador: " + ex.Message);
            }
        }

        private string GetLocalIpAddress()
        {
            try
            {
                var host = Dns.GetHostEntry(Dns.GetHostName());
                foreach (var ip in host.AddressList)
                {
                    if (ip.AddressFamily == AddressFamily.InterNetwork && !IPAddress.IsLoopback(ip))
                    {
                        return ip.ToString();
                    }
                }
            }
            catch { }
            return "localhost";
        }

        private void StartBroadcastServer()
        {
            // Tenta porta 3000; se já estiver ocupada por outra instância, abre o navegador nela ou usa porta alternativa
            for (int tryPort = 3000; tryPort <= 3010; tryPort++)
            {
                try
                {
                    var listener = new HttpListener();
                    listener.Prefixes.Add(string.Format("http://localhost:{0}/", tryPort));
                    listener.Prefixes.Add(string.Format("http://127.0.0.1:{0}/", tryPort));
                    listener.Start();
                    _listener = listener;
                    _port = tryPort;
                    break;
                }
                catch
                {
                    // Porta em uso, tenta próxima
                }
            }

            if (_listener == null)
            {
                _lblStatus.Text = "Servidor já estava ativo na porta 3000! Pronto para uso.";
                OpenUrl("http://localhost:3000/index.html");
                return;
            }

            _running = true;
            string lanIp = GetLocalIpAddress();
            _lblStatus.Text = string.Format("Online em http://localhost:{0}  |  Rede Local: http://{1}:{0}", _port, lanIp);
            _txtObsUrl.Text = string.Format("http://localhost:{0}/output.html", _port);

            _serverThread = new Thread(ListenLoop) { IsBackground = true };
            _serverThread.Start();

            // Abre automaticamente o Painel do Diretor ao iniciar o executável
            OpenUrl(string.Format("http://localhost:{0}/index.html", _port));
        }

        private void ListenLoop()
        {
            while (_running && _listener != null && _listener.IsListening)
            {
                try
                {
                    var context = _listener.GetContext();
                    ThreadPool.QueueUserWorkItem(_ => HandleRequest(context));
                }
                catch
                {
                    if (!_running) break;
                }
            }
        }

        private void BroadcastSse(string jsonPayload)
        {
            byte[] bytes = Encoding.UTF8.GetBytes("data: " + jsonPayload + "\n\n");
            lock (_sseLock)
            {
                for (int i = _sseClients.Count - 1; i >= 0; i--)
                {
                    try
                    {
                        _sseClients[i].OutputStream.Write(bytes, 0, bytes.Length);
                        _sseClients[i].OutputStream.Flush();
                    }
                    catch
                    {
                        _sseClients.RemoveAt(i);
                    }
                }
            }
        }

        private void HandleRequest(HttpListenerContext ctx)
        {
            var req = ctx.Request;
            var res = ctx.Response;

            res.AddHeader("Access-Control-Allow-Origin", "*");
            res.AddHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS, HEAD");
            res.AddHeader("Access-Control-Allow-Headers", "Content-Type");

            if (req.HttpMethod == "OPTIONS" || req.HttpMethod == "HEAD")
            {
                res.StatusCode = 200;
                res.Close();
                return;
            }

            string path = req.Url.AbsolutePath;

            // 1. SSE Event Stream (/api/events)
            if (path == "/api/events" && req.HttpMethod == "GET")
            {
                res.ContentType = "text/event-stream; charset=utf-8";
                res.AddHeader("Cache-Control", "no-cache");
                res.SendChunked = true;

                byte[] hello = Encoding.UTF8.GetBytes("data: {\"type\":\"CONNECTED\"}\n\n");
                try
                {
                    res.OutputStream.Write(hello, 0, hello.Length);
                    res.OutputStream.Flush();
                    lock (_sseLock) { _sseClients.Add(res); }
                }
                catch { res.Close(); }
                return;
            }

            // 2. Sync & WebRTC Signaling (/api/sync)
            if (path == "/api/sync" && req.HttpMethod == "POST")
            {
                using (var reader = new StreamReader(req.InputStream, Encoding.UTF8))
                {
                    string body = reader.ReadToEnd();
                    BroadcastSse(body);
                }
                WriteJson(res, "{\"ok\":true}");
                return;
            }

            // 3. Stream Deck API (#46: /api/streamdeck)
            if (path == "/api/streamdeck")
            {
                string action = req.QueryString["action"] ?? "cut";
                string target = req.QueryString["target"] ?? "";
                string payload = string.Format("{{\"type\":\"STREAMDECK_COMMAND\",\"action\":\"{0}\",\"target\":\"{1}\"}}", action, target);
                BroadcastSse(payload);
                WriteJson(res, "{\"status\":\"dispatched\"}");
                return;
            }

            // 4. Webhook Alert (#33: /api/webhook/alert)
            if (path == "/api/webhook/alert")
            {
                string user = req.QueryString["user"] ?? "Apoiador Ao Vivo";
                string amount = req.QueryString["amount"] ?? "R$ 50,00";
                string msg = req.QueryString["msg"] ?? "Parabens pela transmissao!";
                string payload = string.Format("{{\"type\":\"WEBHOOK_ALERT\",\"user\":\"{0}\",\"amount\":\"{1}\",\"message\":\"{2}\"}}", user, amount, msg);
                BroadcastSse(payload);
                WriteJson(res, "{\"triggered\":true}");
                return;
            }

            // 5. Servir arquivos da pasta public/ (se existir ao lado do .exe) ou do bundle embutido no .exe!
            string cleanRel = path == "/" ? "/index.html" : path;
            string diskPath = Path.Combine(_publicDir, cleanRel.TrimStart('/').Replace('/', Path.DirectorySeparatorChar));

            if (File.Exists(diskPath))
            {
                byte[] fileBytes = File.ReadAllBytes(diskPath);
                res.ContentType = GetMimeType(Path.GetExtension(diskPath));
                res.ContentLength64 = fileBytes.Length;
                res.OutputStream.Write(fileBytes, 0, fileBytes.Length);
                res.Close();
                return;
            }

            // Fallback: serve diretamente da memória embutida no próprio .exe (100% single-file portátil!)
            EmbeddedAsset embedded;
            if (EmbeddedBundle.Files.TryGetValue(cleanRel, out embedded))
            {
                res.ContentType = embedded.MimeType;
                res.ContentLength64 = embedded.Content.Length;
                res.OutputStream.Write(embedded.Content, 0, embedded.Content.Length);
                res.Close();
                return;
            }

            res.StatusCode = 404;
            byte[] err = Encoding.UTF8.GetBytes("404 - Nao encontrado no WebLive Studio");
            res.OutputStream.Write(err, 0, err.Length);
            res.Close();
        }

        private void WriteJson(HttpListenerResponse res, string json)
        {
            byte[] data = Encoding.UTF8.GetBytes(json);
            res.ContentType = "application/json; charset=utf-8";
            res.ContentLength64 = data.Length;
            res.OutputStream.Write(data, 0, data.Length);
            res.Close();
        }

        private string GetMimeType(string ext)
        {
            switch (ext.ToLowerInvariant())
            {
                case ".html": return "text/html; charset=utf-8";
                case ".css": return "text/css; charset=utf-8";
                case ".js": return "application/javascript; charset=utf-8";
                case ".json": return "application/json; charset=utf-8";
                case ".png": return "image/png";
                case ".jpg":
                case ".jpeg": return "image/jpeg";
                case ".svg": return "image/svg+xml";
                default: return "application/octet-stream";
            }
        }

        protected override void OnFormClosing(FormClosingEventArgs e)
        {
            _running = false;
            if (_trayIcon != null) _trayIcon.Visible = false;
            try { if (_listener != null) _listener.Stop(); } catch { }
            base.OnFormClosing(e);
        }

        [STAThread]
        public static void Main()
        {
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            Application.Run(new MainForm());
        }
    }
}

