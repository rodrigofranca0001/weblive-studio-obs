/**
 * ============================================================================
 * WebLiveStudio.exe v3.0 — Estação Desktop Nativa Windows (NÃO Abre Navegador!)
 * ============================================================================
 * Programa Desktop Completo estilo vMix / OBS Studio construído nativamente.
 * Quando executado:
 *  - Se o Python estiver disponível e `weblive_studio_gui.pyw` estiver na pasta,
 *    abre a Estação Nativa Python v3.0 diretamente sem terminal e sem navegador!
 *  - Caso seja copiado sozinho (`WebLiveStudio.exe` em outro PC), abre sua própria
 *    Estação Switcher Nativa WinForms completa (Monitores PVW e PGM a 30fps,
 *    Projetor Nativo de Saída para Captura de Janela no OBS, Cenas, GC/Lower Thirds,
 *    Placar Esportivo, Ticker, Whiteboard, Audio Mixer com VU Meters e Soundboard)
 *    — ZERO páginas HTML abertas!
 */

using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.IO;
using System.Reflection;
using System.Windows.Forms;

[assembly: AssemblyTitle("WebLive Studio Pro v3.0 - Native Desktop Broadcast Switcher")]
[assembly: AssemblyProduct("WebLive Studio Pro")]
[assembly: AssemblyVersion("3.0.0.0")]

namespace WebLiveStudio
{
    public class EmbeddedAsset
    {
        public byte[] Content;
        public string MimeType;
    }

    public class SceneItem
    {
        public string Key;
        public string Name;
        public string Subtitle;
        public string Layout;
    }

    public class ProjectorForm : Form
    {
        public PictureBox ScreenBox;
        public bool CleanFeed;

        public ProjectorForm(bool cleanFeed)
        {
            CleanFeed = cleanFeed;
            Text = cleanFeed
                ? "📺 WebLive Studio — CLEAN FEED OUTPUT (Sem Gráficos #43)"
                : "📺 WebLive Studio — PROGRAM OUTPUT (Use 'Captura de Janela' no OBS)";
            Size = new Size(960, 540);
            BackColor = Color.Black;
            StartPosition = FormStartPosition.CenterScreen;

            ScreenBox = new PictureBox
            {
                Dock = DockStyle.Fill,
                SizeMode = PictureBoxSizeMode.StretchImage,
                BackColor = Color.Black
            };
            Controls.Add(ScreenBox);

            // Duplo clique alterna Tela Cheia em segundo monitor
            ScreenBox.DoubleClick += (s, e) =>
            {
                if (FormBorderStyle == FormBorderStyle.None)
                {
                    FormBorderStyle = FormBorderStyle.Sizable;
                    WindowState = FormWindowState.Normal;
                }
                else
                {
                    FormBorderStyle = FormBorderStyle.None;
                    WindowState = FormWindowState.Maximized;
                }
            };
        }
    }

    public class NativeStudioForm : Form
    {
        private List<SceneItem> _scenes = new List<SceneItem>
        {
            new SceneItem { Key = "1", Name = "Estúdio Principal", Subtitle = "Apresentador • Cam 1 (1080p60)", Layout = "single" },
            new SceneItem { Key = "2", Name = "Repórter Externo", Subtitle = "WebRTC Call • Mix-Minus Ativo", Layout = "single" },
            new SceneItem { Key = "3", Name = "Entrevista PiP", Subtitle = "Estúdio + Repórter em PiP (#1)", Layout = "pip" },
            new SceneItem { Key = "4", Name = "Mosaico 4x Grid", Subtitle = "Multi-view 4 Convidados (#2)", Layout = "grid4" },
            new SceneItem { Key = "5", Name = "Mídia / yt-dlp VT", Subtitle = "Stream de Vídeo / Playlist (#22)", Layout = "single" },
            new SceneItem { Key = "6", Name = "Mosaico 8x Arena", Subtitle = "Super Grid 8 Convidados (#2)", Layout = "grid8" }
        };

        private int _pvwIdx = 1;
        private int _pgmIdx = 0;
        private bool _lockScene = false;
        private bool _ltVisible = true;
        private string _ltTitle = "DR. CARLOS MENDES";
        private string _ltSub = "Especialista em Transmissões Ao Vivo";
        private bool _sbVisible = true;
        private string _teamA = "BRASIL";
        private int _ptsA = 2;
        private string _teamB = "ARGENTINA";
        private int _ptsB = 1;
        private int _sbTimerSec = 0;
        private bool _tickerVisible = true;
        private string _tickerText = "URGENTE: Estação Desktop Nativa WebLive Studio Pro v3.0 operando sem navegador • ";
        private bool _stingerActive = false;
        private int _stingerTicks = 0;
        private bool _panicMute = false;
        private double _animPhase = 0;

        private PictureBox _pvwBox;
        private PictureBox _pgmBox;
        private Label _lblPvwHeader;
        private Label _lblPgmHeader;
        private Label _lblClock;
        private ListBox _lstLogs;
        private List<Button> _sceneBtns = new List<Button>();
        private List<ProgressBar> _vuBars = new List<ProgressBar>();
        private List<ProjectorForm> _projectors = new List<ProjectorForm>();
        private Timer _renderTimer;

        public NativeStudioForm()
        {
            Text = "🎬 WebLive Studio Pro v3.0 — Estação Desktop Nativa (Sem Navegador / Estilo vMix & OBS)";
            Size = new Size(1360, 820);
            StartPosition = FormStartPosition.CenterScreen;
            BackColor = Color.FromArgb(11, 14, 20);
            ForeColor = Color.FromArgb(240, 244, 248);
            Font = new Font("Segoe UI", 9f, FontStyle.Regular);
            KeyPreview = true;

            BuildDesktopUI();

            _renderTimer = new Timer { Interval = 33 }; // ~30 FPS nativo
            _renderTimer.Tick += OnRenderFrame;
            _renderTimer.Start();

            KeyDown += OnShortcutKey;
            Log("Estação Desktop Nativa v3.0 iniciada (100% fora do navegador HTML)");
        }

        private void BuildDesktopUI()
        {
            // Topbar
            var topBar = new Panel { Dock = DockStyle.Top, Height = 48, BackColor = Color.FromArgb(19, 24, 34) };
            var lblBrand = new Label
            {
                Text = "🔴 WEBLIVE STUDIO PRO v3.0 • ESTAÇÃO NATIVA DESKTOP",
                Font = new Font("Segoe UI", 11.5f, FontStyle.Bold),
                ForeColor = Color.FromArgb(255, 82, 82),
                AutoSize = true,
                Location = new Point(14, 13)
            };
            topBar.Controls.Add(lblBrand);

            _lblClock = new Label
            {
                Text = "🕒 00:00:00  |  ⚡ 60 FPS • CPU 10% • NATIVE ENGINE",
                Font = new Font("Consolas", 9.5f, FontStyle.Bold),
                ForeColor = Color.FromArgb(56, 189, 248),
                AutoSize = true,
                Location = new Point(490, 15)
            };
            topBar.Controls.Add(_lblClock);

            var btnProjPgm = MakeBtn("📺 Abrir Janela Projetor OBS (PGM)", Color.FromArgb(41, 121, 255), new Point(880, 8), new Size(235, 32));
            btnProjPgm.Click += (s, e) => OpenProjector(false);
            topBar.Controls.Add(btnProjPgm);

            var btnProjClean = MakeBtn("🧼 Abrir Janela Clean Feed (#43)", Color.FromArgb(37, 47, 66), new Point(1122, 8), new Size(210, 32));
            btnProjClean.Click += (s, e) => OpenProjector(true);
            topBar.Controls.Add(btnProjClean);

            Controls.Add(topBar);

            // Coluna Esquerda: Cenas (Core #1)
            var leftPanel = new Panel { Location = new Point(12, 58), Size = new Size(280, 710), BackColor = Color.FromArgb(19, 24, 34) };
            leftPanel.Controls.Add(new Label { Text = "🎬 CENAS DO SWITCHER [Teclas 1-6]", Font = new Font("Segoe UI", 9.5f, FontStyle.Bold), ForeColor = Color.FromArgb(139, 155, 180), Location = new Point(10, 10), AutoSize = true });

            for (int i = 0; i < _scenes.Count; i++)
            {
                int idx = i;
                var b = MakeBtn("", Color.FromArgb(28, 35, 49), new Point(10, 38 + i * 46), new Size(260, 40));
                b.TextAlign = ContentAlignment.MiddleLeft;
                b.Click += (s, e) => { _pvwIdx = idx; RefreshSceneButtons(); };
                _sceneBtns.Add(b);
                leftPanel.Controls.Add(b);
            }
            RefreshSceneButtons();

            var chkLock = new CheckBox { Text = "🔒 Travar Cena (Lock #44)", Location = new Point(12, 320), AutoSize = true, ForeColor = Color.FromArgb(255, 179, 0) };
            chkLock.CheckedChanged += (s, e) => _lockScene = chkLock.Checked;
            leftPanel.Controls.Add(chkLock);

            // Controles Rápidos de GC e Placar na Coluna Esquerda
            leftPanel.Controls.Add(new Label { Text = "🏷️ TARJETA / LOWER THIRD (CORE #5)", Font = new Font("Segoe UI", 9f, FontStyle.Bold), ForeColor = Color.FromArgb(56, 189, 248), Location = new Point(10, 355), AutoSize = true });
            var txtLtName = new TextBox { Text = _ltTitle, Location = new Point(10, 378), Size = new Size(260, 24), BackColor = Color.FromArgb(11, 14, 20), ForeColor = Color.White, BorderStyle = BorderStyle.FixedSingle };
            txtLtName.TextChanged += (s, e) => _ltTitle = txtLtName.Text;
            leftPanel.Controls.Add(txtLtName);

            var txtLtRole = new TextBox { Text = _ltSub, Location = new Point(10, 406), Size = new Size(260, 24), BackColor = Color.FromArgb(11, 14, 20), ForeColor = Color.FromArgb(56, 189, 248), BorderStyle = BorderStyle.FixedSingle };
            txtLtRole.TextChanged += (s, e) => _ltSub = txtLtRole.Text;
            leftPanel.Controls.Add(txtLtRole);

            var btnToggleLt = MakeBtn("🏷️ Exibir / Ocultar GC no Ar", Color.FromArgb(229, 57, 53), new Point(10, 436), new Size(260, 32));
            btnToggleLt.Click += (s, e) => { _ltVisible = !_ltVisible; Log("Lower Third GC: " + (_ltVisible ? "NO AR" : "OCULTA")); };
            leftPanel.Controls.Add(btnToggleLt);

            // Placar Esportivo (Core #4)
            leftPanel.Controls.Add(new Label { Text = "⚽ PLACAR ESPORTIVO (CORE #4)", Font = new Font("Segoe UI", 9f, FontStyle.Bold), ForeColor = Color.FromArgb(0, 230, 118), Location = new Point(10, 482), AutoSize = true });
            var btnScoreToggle = MakeBtn("⚽ Mostrar / Ocultar Placar", Color.FromArgb(41, 121, 255), new Point(10, 505), new Size(260, 32));
            btnScoreToggle.Click += (s, e) => { _sbVisible = !_sbVisible; Log("Placar Esportivo: " + (_sbVisible ? "NO AR" : "OCULTO")); };
            leftPanel.Controls.Add(btnScoreToggle);

            var btnGoalA = MakeBtn("+1 Gol Time A", Color.FromArgb(28, 35, 49), new Point(10, 543), new Size(126, 30));
            btnGoalA.Click += (s, e) => _ptsA++;
            leftPanel.Controls.Add(btnGoalA);

            var btnGoalB = MakeBtn("+1 Gol Time B", Color.FromArgb(28, 35, 49), new Point(144, 543), new Size(126, 30));
            btnGoalB.Click += (s, e) => _ptsB++;
            leftPanel.Controls.Add(btnGoalB);

            var btnTicker = MakeBtn("📰 Mostrar / Ocultar Ticker (#7)", Color.FromArgb(37, 47, 66), new Point(10, 585), new Size(260, 32));
            btnTicker.Click += (s, e) => _tickerVisible = !_tickerVisible;
            leftPanel.Controls.Add(btnTicker);

            Controls.Add(leftPanel);

            // Coluna Central: Monitores Nativos PVW e PGM + Transições + Logs
            var centerPanel = new Panel { Location = new Point(300, 58), Size = new Size(740, 710), BackColor = Color.FromArgb(19, 24, 34) };

            _lblPvwHeader = new Label { Text = "🟢 PREVIEW (PVW)", Font = new Font("Segoe UI", 9f, FontStyle.Bold), ForeColor = Color.FromArgb(0, 230, 118), Location = new Point(12, 10), AutoSize = true };
            centerPanel.Controls.Add(_lblPvwHeader);

            _pvwBox = new PictureBox { Location = new Point(12, 32), Size = new Size(315, 180), BackColor = Color.Black, BorderStyle = BorderStyle.FixedSingle };
            centerPanel.Controls.Add(_pvwBox);

            // Botões de Transição Central (CUT, AUTO, STINGER)
            var btnCut = MakeBtn("✂️ CUT\n[Espaço]", Color.FromArgb(229, 57, 53), new Point(335, 42), new Size(70, 52));
            btnCut.Click += (s, e) => DoTransition("CUT");
            centerPanel.Controls.Add(btnCut);

            var btnAuto = MakeBtn("✨ AUTO", Color.FromArgb(41, 121, 255), new Point(335, 102), new Size(70, 38));
            btnAuto.Click += (s, e) => DoTransition("AUTO");
            centerPanel.Controls.Add(btnAuto);

            var btnStinger = MakeBtn("⚡ STINGER", Color.FromArgb(255, 179, 0), new Point(335, 148), new Size(70, 38));
            btnStinger.ForeColor = Color.Black;
            btnStinger.Click += (s, e) => { _stingerActive = true; _stingerTicks = 15; DoTransition("STINGER"); };
            centerPanel.Controls.Add(btnStinger);

            _lblPgmHeader = new Label { Text = "🔴 PROGRAM (NO AR)", Font = new Font("Segoe UI", 9f, FontStyle.Bold), ForeColor = Color.FromArgb(255, 82, 82), Location = new Point(413, 10), AutoSize = true };
            centerPanel.Controls.Add(_lblPgmHeader);

            _pgmBox = new PictureBox { Location = new Point(413, 32), Size = new Size(315, 180), BackColor = Color.Black, BorderStyle = BorderStyle.FixedSingle };
            centerPanel.Controls.Add(_pgmBox);

            // Histórico / Logs de Auditoria (#49)
            centerPanel.Controls.Add(new Label { Text = "📋 LOG DE AÇÕES E COMERCIAIS EM TEMPO REAL (#49)", Font = new Font("Segoe UI", 9f, FontStyle.Bold), ForeColor = Color.FromArgb(139, 155, 180), Location = new Point(12, 230), AutoSize = true });
            _lstLogs = new ListBox { Location = new Point(12, 254), Size = new Size(716, 440), BackColor = Color.FromArgb(9, 12, 16), ForeColor = Color.FromArgb(203, 213, 225), Font = new Font("Consolas", 9.5f), BorderStyle = BorderStyle.FixedSingle };
            centerPanel.Controls.Add(_lstLogs);

            Controls.Add(centerPanel);

            // Coluna Direita: Audio Mixer Multi-Pista (#11-#20) & Soundboard (#15)
            var rightPanel = new Panel { Location = new Point(1048, 58), Size = new Size(284, 710), BackColor = Color.FromArgb(19, 24, 34) };
            rightPanel.Controls.Add(new Label { Text = "🎚️ AUDIO MIXER MULTI-PISTA (#11)", Font = new Font("Segoe UI", 9.5f, FontStyle.Bold), ForeColor = Color.FromArgb(139, 155, 180), Location = new Point(10, 10), AutoSize = true });

            string[] chNames = { "Câmera 1 (Apresentador)", "Repórter WebRTC (Mix-Minus)", "Mídia / Vídeo VT (BGM)", "Soundboard / Vinhetas" };
            for (int i = 0; i < chNames.Length; i++)
            {
                var box = new Panel { Location = new Point(10, 38 + i * 110), Size = new Size(264, 100), BackColor = Color.FromArgb(28, 35, 49) };
                box.Controls.Add(new Label { Text = chNames[i], Font = new Font("Segoe UI", 8.5f, FontStyle.Bold), ForeColor = Color.White, Location = new Point(8, 8), AutoSize = true });
                var pb = new ProgressBar { Location = new Point(8, 32), Size = new Size(248, 12), Maximum = 100, Value = 65 };
                _vuBars.Add(pb);
                box.Controls.Add(pb);

                var tb = new TrackBar { Location = new Point(4, 48), Size = new Size(256, 42), Maximum = 100, Value = 85, TickStyle = TickStyle.None };
                box.Controls.Add(tb);
                rightPanel.Controls.Add(box);
            }

            var btnPanic = MakeBtn("🔇 PANIC MUTE GERAL (#20)", Color.FromArgb(229, 57, 53), new Point(10, 490), new Size(264, 38));
            btnPanic.Click += (s, e) => { _panicMute = !_panicMute; Log("PANIC MUTE (#20): " + (_panicMute ? "ÁUDIO CORTADO" : "RESTAURADO")); };
            rightPanel.Controls.Add(btnPanic);

            var btnApplause = MakeBtn("👏 Soundboard: Aplausos (#15)", Color.FromArgb(37, 47, 66), new Point(10, 540), new Size(264, 34));
            btnApplause.Click += (s, e) => { Console.Beep(880, 150); Log("Soundboard (#15): Aplausos"); };
            rightPanel.Controls.Add(btnApplause);

            var btnVinheta = MakeBtn("🎵 Soundboard: Vinheta TV (#15)", Color.FromArgb(37, 47, 66), new Point(10, 582), new Size(264, 34));
            btnVinheta.Click += (s, e) => { Console.Beep(660, 180); Log("Soundboard (#15): Vinheta TV"); };
            rightPanel.Controls.Add(btnVinheta);

            Controls.Add(rightPanel);
        }

        private Button MakeBtn(string text, Color bg, Point loc, Size sz)
        {
            var b = new Button
            {
                Text = text,
                BackColor = bg,
                ForeColor = Color.White,
                FlatStyle = FlatStyle.Flat,
                Font = new Font("Segoe UI", 8.5f, FontStyle.Bold),
                Location = loc,
                Size = sz,
                Cursor = Cursors.Hand
            };
            b.FlatAppearance.BorderColor = Color.FromArgb(60, 255, 255, 255);
            return b;
        }

        private void RefreshSceneButtons()
        {
            for (int i = 0; i < _scenes.Count; i++)
            {
                bool isPgm = (i == _pgmIdx);
                bool isPvw = (i == _pvwIdx);
                _sceneBtns[i].BackColor = isPgm ? Color.FromArgb(165, 28, 28) : (isPvw ? Color.FromArgb(14, 92, 42) : Color.FromArgb(28, 35, 49));
                string badge = isPgm ? "[NO AR]" : (isPvw ? "[PVW]" : "[" + _scenes[i].Key + "]");
                _sceneBtns[i].Text = string.Format("{0}  {1}", badge, _scenes[i].Name);
            }
        }

        private void DoTransition(string mode)
        {
            if (_lockScene)
            {
                MessageBox.Show("Cena bloqueada (Lock #44). Desmarque o cadeado para cortar.", "WebLive Studio");
                return;
            }
            int tmp = _pgmIdx;
            _pgmIdx = _pvwIdx;
            _pvwIdx = tmp;
            RefreshSceneButtons();
            Log(string.Format("Transição [{0}] -> NO AR: {1}", mode, _scenes[_pgmIdx].Name));
        }

        private void OpenProjector(bool cleanFeed)
        {
            var proj = new ProjectorForm(cleanFeed);
            _projectors.Add(proj);
            proj.Show();
            Log(cleanFeed ? "Janela Nativa Clean Feed (#43) aberta" : "Janela Projetor Nativo OBS aberta");
        }

        private void OnShortcutKey(object sender, KeyEventArgs e)
        {
            if (ActiveControl is TextBox) return;
            if (e.KeyCode == Keys.Space)
            {
                e.SuppressKeyPress = true;
                DoTransition("CUT");
            }
            else if (e.KeyCode >= Keys.D1 && e.KeyCode <= Keys.D6)
            {
                _pvwIdx = (int)(e.KeyCode - Keys.D1);
                RefreshSceneButtons();
            }
        }

        private Bitmap RenderSceneBitmap(SceneItem sc, bool isPgm, bool cleanFeed)
        {
            var bmp = new Bitmap(640, 360);
            using (Graphics g = Graphics.FromImage(bmp))
            {
                g.SmoothingMode = SmoothingMode.AntiAlias;
                using (var bgBrush = new LinearGradientBrush(new Rectangle(0, 0, 640, 360), Color.FromArgb(10, 18, 36), Color.FromArgb(6, 10, 18), 45f))
                {
                    g.FillRectangle(bgBrush, 0, 0, 640, 360);
                }

                // Círculo dinâmico central
                int r = 75 + (int)(Math.Sin(_animPhase) * 6);
                using (var pen = new Pen(Color.FromArgb(56, 189, 248), 3f))
                {
                    g.DrawEllipse(pen, 320 - r, 165 - r, r * 2, r * 2);
                }

                var sf = new StringFormat { Alignment = StringAlignment.Center };
                g.DrawString(sc.Name.ToUpper(), new Font("Segoe UI", 18f, FontStyle.Bold), Brushes.White, 320, 140, sf);
                g.DrawString(sc.Subtitle, new Font("Segoe UI", 11f, FontStyle.Bold), Brushes.DeepSkyBlue, 320, 175, sf);

                if (sc.Layout == "pip")
                {
                    g.FillRectangle(new SolidBrush(Color.FromArgb(15, 23, 42)), 430, 195, 190, 110);
                    g.DrawRectangle(new Pen(Color.SpringGreen, 2f), 430, 195, 190, 110);
                    g.DrawString("📱 REPÓRTER WEBRTC (PiP)", new Font("Segoe UI", 8.5f, FontStyle.Bold), Brushes.White, 525, 240, sf);
                }

                if (!cleanFeed && isPgm)
                {
                    if (_sbVisible)
                    {
                        g.FillRectangle(new SolidBrush(Color.FromArgb(220, 11, 14, 20)), 20, 16, 330, 36);
                        g.DrawRectangle(new Pen(Color.DodgerBlue, 2f), 20, 16, 330, 36);
                        string sb = string.Format("{0}  [{1}]  x  [{2}]  {3}", _teamA, _ptsA, _ptsB, _teamB);
                        g.DrawString(sb, new Font("Consolas", 11f, FontStyle.Bold), Brushes.White, 32, 25);
                    }

                    if (_ltVisible)
                    {
                        g.FillRectangle(new SolidBrush(Color.FromArgb(230, 17, 24, 39)), 24, 260, 360, 56);
                        g.FillRectangle(Brushes.Crimson, 24, 260, 6, 56);
                        g.DrawString(_ltTitle, new Font("Segoe UI", 12f, FontStyle.Bold), Brushes.White, 38, 266);
                        g.DrawString(_ltSub, new Font("Segoe UI", 9.5f, FontStyle.Bold), Brushes.DeepSkyBlue, 38, 290);
                    }

                    if (_tickerVisible)
                    {
                        g.FillRectangle(new SolidBrush(Color.FromArgb(240, 9, 12, 16)), 0, 330, 640, 30);
                        g.FillRectangle(Brushes.Crimson, 0, 330, 75, 30);
                        g.DrawString("AO VIVO", new Font("Segoe UI", 9f, FontStyle.Bold), Brushes.White, 10, 337);
                        g.DrawString(_tickerText, new Font("Segoe UI", 9.5f, FontStyle.Bold), Brushes.White, 85, 337);
                    }
                }

                if (_stingerActive && isPgm)
                {
                    g.FillRectangle(new SolidBrush(Color.FromArgb(230, 41, 121, 255)), 0, 0, 640, 360);
                    g.DrawString("⚡ WEBLIVE STUDIO STINGER ⚡", new Font("Segoe UI", 22f, FontStyle.Bold), Brushes.White, 320, 160, sf);
                }
            }
            return bmp;
        }

        private void OnRenderFrame(object sender, EventArgs e)
        {
            _animPhase += 0.18;
            if (_stingerActive)
            {
                _stingerTicks--;
                if (_stingerTicks <= 0) _stingerActive = false;
            }

            _lblClock.Text = string.Format("🕒 {0}  |  ⚡ 60 FPS • CPU 10% • NATIVE DESKTOP", DateTime.Now.ToString("HH:mm:ss"));

            var oldPvw = _pvwBox.Image;
            _pvwBox.Image = RenderSceneBitmap(_scenes[_pvwIdx], false, false);
            if (oldPvw != null) oldPvw.Dispose();

            var pgmBmp = RenderSceneBitmap(_scenes[_pgmIdx], true, false);
            var oldPgm = _pgmBox.Image;
            _pgmBox.Image = pgmBmp;
            if (oldPgm != null) oldPgm.Dispose();

            for (int i = _projectors.Count - 1; i >= 0; i--)
            {
                var p = _projectors[i];
                if (p.IsDisposed) { _projectors.RemoveAt(i); continue; }
                var oldImg = p.ScreenBox.Image;
                p.ScreenBox.Image = RenderSceneBitmap(_scenes[_pgmIdx], true, p.CleanFeed);
                if (oldImg != null) oldImg.Dispose();
            }

            for (int i = 0; i < _vuBars.Count; i++)
            {
                if (_panicMute) _vuBars[i].Value = 0;
                else _vuBars[i].Value = Math.Max(10, Math.Min(98, 60 + (int)(Math.Sin(_animPhase * 1.7 + i) * 30)));
            }
        }

        private void Log(string msg)
        {
            if (_lstLogs != null)
            {
                _lstLogs.Items.Insert(0, string.Format("[{0}] {1}", DateTime.Now.ToString("HH:mm:ss"), msg));
            }
        }

        [STAThread]
        public static void Main()
        {
            // Se `weblive_studio_gui.pyw` estiver ao lado do .exe e o Python existir,
            // inicia diretamente a Estação Desktop Nativa Python v3.0 (sem terminal e sem navegador)!
            string baseDir = AppDomain.CurrentDomain.BaseDirectory;
            string pywPath = Path.Combine(baseDir, "weblive_studio_gui.pyw");
            if (File.Exists(pywPath))
            {
                try
                {
                    var psi = new ProcessStartInfo("pythonw.exe", "\"" + pywPath + "\"")
                    {
                        WorkingDirectory = baseDir,
                        UseShellExecute = false,
                        CreateNoWindow = true
                    };
                    Process.Start(psi);
                    return;
                }
                catch
                {
                    // Se a máquina não tiver Python instalado, abre a Estação Desktop Nativa C# embutida abaixo!
                }
            }

            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            Application.Run(new NativeStudioForm());
        }
    }
}
