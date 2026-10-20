# 📘 Manual de Instruções de Uso — WebLive Studio (Pro Switcher & OBS Overlay)

> **Regra de Governança:** Este manual faz parte da documentação viva do projeto e **deve ser atualizado obrigatoriamente a cada nova modificação, recurso ou ajuste de interface** realizado no sistema.

---

## 1. Visão Geral do Sistema

O **WebLive Studio** é uma plataforma web completa de produção ao vivo, corte de câmeras (Switcher), geração de caracteres (GC), mixagem de áudio com **Mix-Minus** e chamada remota via **WebRTC** projetada para operar integrada ao **OBS Studio** (ou vMix).

O ecossistema possui **4 endereços principais**:

| Interface | URL Local | Finalidade Principal |
| :--- | :--- | :--- |
| **🎛️ Painel do Diretor** | `http://localhost:3000/index.html` | Mesa de corte (PVW/PGM), controle de cenas, áudio, GC, placar e automação. |
| **📺 Tela OBS (Output)** | `http://localhost:3000/output.html` | Página 1920x1080 transparente/composta para adicionar como *Browser Source* no OBS. |
| **🧼 Saída Clean Feed** | `http://localhost:3000/output.html?clean=1` | Saída de vídeo limpa (sem GC, sem placar, sem marca d'água e sem alertas) para gravação master (`#43`). |
| **📱 Convidado Remoto** | `http://localhost:3000/guest.html?guest=Reporter1` | Link para celular/PC externo enviar câmera/tela via WebRTC e receber retorno com Mix-Minus (`Core #7`). |

---

## 2. Como Iniciar o Sistema (Plataforma Profissional Python + Executável Portátil `.EXE`)

O **WebLive Studio Pro v2.0** agora conta com um **Motor Broadcast Nativo em Python 3** (`weblive_server.py` + `weblive_studio_gui.pyw`) integrado a `SQLite3`, extrator `yt-dlp` para streams diretos do YouTube/Twitch/Instagram, parser nativo de Feed RSS sem bloqueio CORS e pipeline de transmissão direta `RTMP / FFmpeg`, além do executável portátil `WebLiveStudio.exe`.

### Opção A (Estação Profissional Desktop Python — Sem Terminal): `weblive_studio_gui.pyw`
1. Dê um **duplo clique no arquivo `weblive_studio_gui.pyw`** (a extensão `.pyw` abre diretamente a janela gráfica nativa `Tkinter` no Windows **sem abrir janela de terminal CMD**).
2. A janela **🐍 WebLive Studio Pro v2.0 — Plataforma Python de Transmissão Ao Vivo & OBS** será exibida contendo:
   * **Central de Operação Rápida (1 Clique):** Botões para abrir *Painel do Diretor*, *Tela OBS 1080p*, *Saída Clean Feed (`#43`)* e *Link do Repórter WebRTC* (com botão para copiar o IP da rede local para celulares).
   * **📡 Transmissão Direta RTMP / FFmpeg:** Insira a URL RTMP (`rtmp://a.rtmp.youtube.com/live2`) e a sua *Stream Key* e clique em **`🚀 Iniciar Pipeline RTMP Python`** para acionar o motor de streaming.
   * **🎞️ Extrator Python `yt-dlp` Integrado:** Cole qualquer link de vídeo ou live (YouTube, Twitch, Instagram, TikTok) e clique em **`⚡ Extrair c/ yt-dlp e Jogar no Ar (OBS)`** para extrair o stream limpo via Python e exibi-lo imediatamente.
   * **📋 Banco SQLite Nativo (`weblive_studio.db`) & Telemetria em Tempo Real:** Monitora a quantidade de clientes conectados (Abas/OBS/Mobile) e grava automaticamente todo o histórico de auditoria comercial (`#49`) em banco de dados SQLite.

### Opção B (Portátil Único `.EXE` para máquinas sem Python): `WebLiveStudio.exe`
1. Copie o arquivo único **`WebLiveStudio.exe`** para qualquer computador Windows (via Pen Drive, Rede ou GitHub).
2. Dê um **duplo clique em `WebLiveStudio.exe`**.
3. Uma janela gráfica de controle se abrirá iniciando automaticamente o servidor local na porta `3000` e abrindo o **Painel do Diretor** no seu navegador padrão.

### Opção C (Servidor Python via Linha de Comando)
```powershell
python weblive_server.py
```

---

## 3. Como Configurar no OBS Studio (Browser Source)

1. No **OBS Studio**, vá no painel **Fontes (Sources)** $\rightarrow$ clique em **`+`** $\rightarrow$ escolha **Navegador (Browser)**.
2. Nomeie como `WebLive Output Master`.
3. Configure as propriedades da fonte:
   * **URL:** `http://localhost:3000/output.html`
   * **Largura (Width):** `1920`
   * **Altura (Height):** `1080`
   * **FPS Personalizado:** `60`
   * **Controlar áudio via OBS:** Marque caso queira rotear o som da aba diretamente no mixer do OBS.
4. *(Opcional — Clean Feed `#43`)*: Para gravar uma pista limpa sem tarjetas ou placar, crie uma segunda fonte de navegador apontando para `http://localhost:3000/output.html?clean=1`.

---

## 4. Guia Passo a Passo do Painel do Diretor (`index.html`)

### 4.1. Barra Superior (Topbar)
* **🕒 Relógio Broadcast (`#26`):** Exibe a hora exata com seletor de fuso horário (`BRT`, `UTC`, `EST`, `WET`).
* **⚡ Monitoramento de Saúde (`#42`):** Mostra taxa de quadros (`FPS`), uso estimado de `CPU` e consumo de `RAM` do navegador em tempo real.
* **🎬 Seletor de Perfil de Usuário (`#29`):** Permite alternar a visão e permissões entre:
  * **Diretor Geral:** Acesso total a cenas, vídeo, áudio, GC e automação.
  * **Operador de GC:** Foco nas abas de Tarjetas, Placar, Ticker, Enquetes e Chat.
  * **Operador de Áudio:** Foco no Mixer Multi-pista, Soundboard, Roteamento e Call WebRTC.
* **🔇 Botão PANIC MUTE (`#20`):** Corta instantaneamente todo o áudio do barramento Master em caso de emergência.
* **🌙 Tema (`#30`):** Alterna entre o **Dark Mode** (padrão para estúdios escuros) e **Light Mode**.

---

### 4.2. Coluna Esquerda: Cenas, WebRTC, Mídia Web e Câmera Local

#### A. Gerenciamento de Cenas (`Core #1`, `#21`, `#44`)
* **1 Clique na Cena:** Envia a cena para o monitor ** verde PREVIEW (PVW)**.
* **Duplo Clique na Cena:** Envia e corta imediatamente para o **vermelho PROGRAM (NO AR)**.
* **Atalhos de Teclado (`#21`):**
  * Teclas `1` a `6`: Selecionam as cenas 1 a 6 no Preview.
  * Tecla `Espaço (Space)`: Executa o corte imediato (**CUT**) entre Preview e Program.
* **🔒 Lock (`#44`):** Quando marcado, bloqueia qualquer troca acidental de cena durante momentos críticos.
* **Botão `+ Cena`:** Cria novas cenas personalizadas em tempo real.

#### B. Entrada Remota WebRTC com Mix-Minus (`Core #7`, `#16`, `#24`, `#39`, `#41`, `#50`)
* **Copiar / Abrir Link:** Envie o link `guest.html?guest=Reporter1` para o celular ou notebook do repórter/convidado.
* **Retorno com Mix-Minus Automático:** Assim que o convidado clica em *"Entrar Ao Vivo"*, ele vê o retorno do Program e ouve todas as fontes da live **exceto a própria voz**, eliminando eco.
* **🎙️ Segure p/ Talkback (`#16`):** Enquanto o diretor mantém este botão pressionado, sua voz vai exclusivamente para o fone do repórter (com indicação visual na tela dele) **sem sair no ar (OBS)**.
* **🖥️ Screen Share (`#39`):** Captura uma janela ou tela inteira do computador e joga automaticamente no layout Picture-in-Picture (`PiP`).
* **📶 Speedtest (`#41`):** Mede taxa de Upload (Mbps), Latência (`RTT`) e `Jitter` da conexão.

#### C. Fontes de Mídia Web, Extrator Python `yt-dlp` & Playlist (`Core #2`, `#22`)
* Cole links de **YouTube, Twitch, Facebook, Instagram ou arquivos MP4/WebM**.
* Clique em **`🐍 Play via yt-dlp`** para que o backend Python (`weblive_server.py`) extraia o stream direto do vídeo sem bloqueios de embed, ou clique em **`▶ Play Embed`** para reprodução padrão.
* Clique em **`+ Fila`** para enfileirar vários vídeos na **Playlist (`#22`)**.
* Use os botões **`⏸`** e **`⏭`** para controlar a reprodução diretamente no OBS.

#### D. Câmera Local & Roteamento de Áudio (`Core #6`)
* Clique em **`Ligar Câmera`** para capturar sua webcam local em 720p/1080p.
* No seletor **Fonte de Áudio**, escolha entre o áudio embutido da câmera, um microfone externo USB/XLR ou desativar o áudio da câmera.

---

### 4.3. Coluna Central: Monitores PVW/PGM, Transições e Abas de Produção

#### A. Barra de Transições & Ferramentas de Tela
* **✂️ CUT:** Troca imediata entre Preview e Program.
* **✨ AUTO:** Transição suave entre Preview e Program.
* **⚡ STINGER (`Core #3`):** Dispara a animação de transição com logo personalizado (armazenado no `IndexedDB` local) + efeito sonoro de vinheta.
* **⏪ REPLAY (`#8`):** Reproduz instantaneamente os últimos **10 segundos** gravados continuamente no buffer circular de memória.
* **📏 Grid `#47`:** Ativa as linhas-guia magnéticas (Snap Grid) sobre os monitores Preview e Program para alinhamento visual perfeito.
* **✏️ Desenhar na Tela — Whiteboard (`#40`):** Marque a caixa, escolha a cor e desenhe livremente com o mouse ou touch sobre o monitor **PROGRAM** (o traço aparece em tempo real na tela do OBS, estilo comentarista esportivo). Clique em **`Limpar Desenho`** para apagar.
* **⏳ Countdown Live (`#25`):** Exibe ou oculta a tela regressiva gigante de início de transmissão no OBS.
* **⏺️ Gravar Backup Local (`#27`):** Inicia a gravação local da saída Program via `MediaRecorder API` e baixa automaticamente o arquivo `.webm` no PC do diretor ao parar.

#### B. Aba 1 — 🏷️ GC, Placar & Ticker (`Core #4`, `Core #5`, `#7`, `#37`)
* **Tarjeta / Lower Third (`Core #5`):**
  * Preencha Nome/Manchete e Cargo/Subtítulo.
  * Escolha entre **Fixa (Permanente)** ou **Temporária (5s ou 8s)** — no modo temporário ela entra animada, permanece pelo tempo escolhido e sai sozinha.
* **Placar Esportivo & Cronômetro (`Core #4`):**
  * Altere os nomes das equipes e a pontuação (atualização instantânea no ar).
  * Controle o cronômetro da partida com **`Iniciar/Pausar`** e **`Zerar`**.
* **Ticker / Crawl (`#7`) & Feed RSS (`#37`):**
  * Digite avisos contínuos para a barra inferior estilo telejornal ou clique em **`📡 Puxar Feed RSS (#37)`** para carregar manchetes automáticas.

#### C. Aba 2 — 🎨 Vídeo, PiP, Grid & Chroma (`#1` a `#6`, `#10`)
* **Seletor de Layout:** Alterne entre *Câmera Única*, *Picture-in-Picture (PiP `#1`)*, *Multi-view Grid 4 Convidados (`#2`)* ou *Multi-view Grid 8 Convidados (`#2`)*.
* **Backgrounds Dinâmicos (`#10`):** Escolha entre *Cyber Grid*, *Telejornal* ou *Arena Esportiva*.
* **Chroma Key (`#3`):** Ative a remoção de fundo verde em tempo real e ajuste o controle deslizante de **Tolerância**.
* **Correção de Cor (`#5`) & Recorte Crop (`#4`):** Ajuste Brilho, Contraste, Saturação e recorte de bordas em tempo real.
* **Upload de Stinger / Logo (`Core #3` e `#6`):** Selecione uma imagem/logo do seu computador para salvá-la no `IndexedDB` local; ela passa a ser exibida na **Marca d'água (`#6`)** e na transição **Stinger (`Core #3`)** sem gastar banda de internet.

#### D. Aba 3 — 💬 Chat, Enquetes, Meta & QR (`#9`, `#31` a `#38`)
* **Chat Ao Vivo (`#31`) + Filtro de Palavrões (`#38`) + Destaque (`#35`):**
  * Com o **Filtro de Palavrões (`#38`)** ativo, termos inadequados são substituídos por `****`.
  * Clique em **`Destacar (#35)`** ou no botão **`No Ar`** de qualquer mensagem para jogá-la animada na tela do OBS.
* **QR Code Ao Vivo (`#9`):** Digite qualquer URL ou chave Pix e clique em **`QR No Ar (#9)`** para gerar e exibir o QR Code na tela.
* **Enquete Ao Vivo (`#32`):** Exibe o gráfico dinâmico de votação em barras com atualização em tempo real (`+Voto A` / `+Voto B`).
* **Barra de Meta (`#34`):** Exibe a barra de progresso de inscritos/doações.
* **Simular Superchat (`#33`):** Dispara um alerta animado de doação no centro da tela com efeito sonoro (também acionável via Webhook externo).
* **Clima (`#36`):** Exibe ou oculta o widget de previsão do tempo no canto superior.

#### E. Aba 4 — ⚙️ Automação, Agendamento, JSON & Logs (`#28`, `#45`, `#46`, `#49`)
* **Agendamento de Eventos (`#28`):** Defina um horário (`HH:MM:SS`) e escolha qual cena deve entrar automaticamente no ar com transição Stinger.
* **Exportar / Importar Projeto JSON (`#45`):** Salve todas as cenas, textos de GC, placar e configurações visuais em um arquivo `.json` ou carregue um projeto salvo anteriormente.
* **Histórico / Log de Ações (`#49`):** Consulta em tempo real tudo o que foi ao ar com carimbo de horário e permite exportar um relatório auditável em **CSV** (`Baixar CSV`).

---

### 4.4. Coluna Direita: Audio Mixer Multi-Pista & Soundboard (`#11` a `#19`, `#23`, `#48`)
* **Canais Independentes (`#11`):** Controle de volume individual com barra **VU Meter** colorida em tempo real para *Apresentador*, *Repórter WebRTC*, *Mídia Web* e *Soundboard*.
* **🎧 PFL — Pre-Fader Listen (`#18`):** Permite ao diretor escutar a fonte em seu fone antes de abrir o fader para o público.
* **Pan (`#19`) & Delay (`#17`):** Ajuste o balanço estéreo Esquerda/Direita (`-1.0` a `+1.0`) e o atraso em milissegundos (`0` a `900ms`) para corrigir sincronia labial (*Lip-Sync*).
* **🦆 Audio Ducking (`#14`):** Quando marcado, reduz automaticamente o volume da música/mídia sempre que o apresentador ou repórter fala.
* **🗣️ Auto-Switch p/ Voz (`#23`):** Quando marcado, o sistema detecta automaticamente quem está falando no momento e corta a câmera para essa pessoa.
* **🎹 MIDI (`#48`):** Conecta controladoras USB MIDI físicas via *Web MIDI API* para controlar os faders de volume usando potenciômetros reais.
* **🔊 Soundboard (`#15`):** Botões de disparo rápido para *Aplausos*, *Vinheta TV*, *Alerta Urgente* e *Beep Timer*.

---

## 5. Integrações Externas (Stream Deck HTTP API `#46` & Webhooks `#33`)

### 5.1. Comandos HTTP para Elgato Stream Deck / Bitfocus Companion (`#46`)
Configure botões do tipo *Website / GET Request* no seu Stream Deck apontando para:
* **Trocar direto para uma Cena (ex: Cena 1 a 6):**
  `http://localhost:3000/api/streamdeck?action=scene&target=1`
* **Executar Corte Seco (CUT):**
  `http://localhost:3000/api/streamdeck?action=cut`
* **Disparar Transição Stinger:**
  `http://localhost:3000/api/streamdeck?action=stinger`

### 5.2. Webhook para Alertas de Doação / Superchat (`#33`)
Qualquer serviço externo pode disparar alertas na tela enviando um `GET` ou `POST` para:
```text
http://localhost:3000/api/webhook/alert?user=NomeDoApoiador&amount=R$%2050,00&msg=Mensagem%20na%20tela
```

---

## 6. Guia do Repórter / Convidado Remoto (`guest.html`)
1. O repórter abre o link `http://SEU_IP_OU_DOMINIO:3000/guest.html?guest=Reporter1` no celular (4G/5G ou Wi-Fi).
2. Antes de entrar, pode clicar em **`Executar Teste de Banda`** (`#41`) para validar Upload, RTT e Jitter.
3. Clica em **`📡 Entrar Ao Vivo (WebRTC)`** (ou **`🖥️ Compartilhar Tela`** `#39`).
4. O banner superior funciona como **Tally Light (`#24`)**:
   * **⚪ STANDBY:** Aguardando.
   * **🟢 EM PREVIEW:** Diretor selecionou sua câmera no Preview (prepare-se).
   * **🔴 VOCÊ ESTÁ NO AR! (PROGRAM):** Sua imagem está sendo transmitida ao vivo no OBS.
5. Caso o 4G oscile, o watchdog de **Auto-Reconexão (`#50`)** renegocia a conexão automaticamente sem travar a tela do OBS.

