# 🎬 WebLive Studio — Prompt de Abertura & Relatório de Desenvolvimento (Continuidade de Projeto)

> **Propósito deste Documento:** Permitir que o desenvolvimento do **WebLive Studio** possa ser interrompido a qualquer momento (mesmo abruptamente) e retomado com 100% de contexto arquitetural, histórico de implementação, status de cada módulo e configuração Git/GitHub.

---

## 📌 1. Prompt de Abertura Original (Especificação Mestre)

```text
Atuar como um Arquiteto de Software e Desenvolvedor Full-Stack sênior especialista em streaming e broadcasting (semelhante ao vMix e OBS Studio). Sua tarefa é desenvolver o código-fonte de uma plataforma web completa de Produção ao Vivo e Overlay ("WebLive Studio").

O sistema será dividido logicamente em duas partes conectadas em tempo real (via Firebase, WebSockets ou WebRTC):

Painel de Controle (Director Interface): Acessível via navegador por PC, Mac, Android ou iOS. Totalmente responsivo, modular e intuitivo.

Tela de Exibição (Output/Overlay): A página que será adicionada como "Fonte de Navegador" (Browser Source) no OBS Studio.

Requisitos Essenciais (Core):
1. Gerenciamento de Cenas: Capacidade de criar, nomear e alternar entre diferentes cenas.
2. Fontes de Mídia Web: Inserção de janelas que rodem vídeos do YouTube, links do Facebook e Instagram diretamente na tela, com controle de play/pause no painel.
3. Transições Personalizadas (Stingers): Efeitos de transição entre cenas usando logos e imagens animadas. O sistema deve permitir o upload e armazenamento local desses arquivos (usando IndexedDB ou File System Access API) na máquina em que o OBS está instalado, reduzindo o uso de banda.
4. Placar Esportivo/Competitivo: Módulo de placar dinâmico com controle de pontuação, cronômetro e nomes dos times/jogadores.
5. Tarjetas (Lower Thirds) e Créditos: Sistema de caracteres dinâmicos. Deve permitir tarjetas permanentes (fixas na tela) ou temporárias (que entram, ficam x segundos e saem automaticamente), com animações de entrada e saída.
6. Roteamento de Áudio (Câmeras e Fontes Alternativas): Ao inserir uma câmera (local ou remota), o painel deve oferecer um mixer básico para ligar/desligar o áudio embutido do vídeo ou vincular uma fonte de áudio alternativa (ex: microfone externo).
7. Link de Entrada Remota (Estilo vMix Call / OBS Ninja): O sistema deve gerar um link para um repórter/convidado externo acessar via celular. A conexão deve ser via WebRTC contendo:
   - Envio do vídeo/áudio do celular para o painel.
   - Retorno de Vídeo (Program) para o repórter ver o que está no ar.
   - Mix-Minus (Filtro de Retorno): O repórter deve ouvir o áudio da transmissão (apresentador, vídeos), mas o sistema deve subtrair o próprio áudio do repórter do retorno para evitar eco.

Lista de 50 Funções Adicionais para Integração no Sistema:

Categoria 1: Vídeo e Visuais (1-10)
1. Picture-in-Picture (PiP): Janelas redimensionáveis sobrepostas.
2. Multi-view Grid: Layout automático para até 4 ou 8 convidados (Mosaico).
3. Chroma Key (Fundo Verde): Filtro WebGL/Canvas nativo para remover fundos de câmeras.
4. Recorte/Máscara (Cropping): Cortar as bordas de uma fonte de vídeo.
5. Correção de Cor Básica: Brilho, contraste e saturação por fonte de vídeo.
6. Marca d'água: Upload de logo fixo no canto da tela (transparente).
7. Ticker Tape / Crawl: Barra de texto contínua passando na base da tela (estilo jornalismo).
8. Instant Replay (Replay Imediato): Gravação em buffer dos últimos 10 segundos para exibição.
9. Gerador de QR Code Ao Vivo: Criar e exibir QR codes na tela para doações ou links.
10. Backgrounds Dinâmicos: Suporte a vídeos em loop (MP4/WebM) como fundo de tela.

Categoria 2: Áudio e Comunicação (11-20)
11. Audio Mixer Multi-pista: Faders de volume independentes para cada fonte (Câmeras, Mídias, Sistema).
12. Audio Visualizer: Barras gráficas na tela que reagem ao som.
13. Supressão de Ruído/Noise Gate: Filtro em tempo real para convidados remotos.
14. Audio Ducking: Abaixar automaticamente o som da música de fundo quando alguém falar.
15. Soundboard (Efeitos Sonoros): Botões rápidos para tocar aplausos, trilhas, vinhetas.
16. Talkback/Intercom: Um botão "Push-to-talk" para o diretor falar apenas no fone do repórter remoto (sem vazar na live).
17. Sincronização (Audio Delay): Ajuste de milissegundos para corrigir falta de sincronia de boca.
18. Monitoramento PFL (Pre-Fader Listen): O diretor poder ouvir um vídeo antes de colocá-lo no ar.
19. Panorâmico (Pan L/R): Direcionar o áudio para o canal esquerdo ou direito.
20. Mute de Segurança (Panic Button): Cortar todo o áudio instantaneamente.

Categoria 3: Automação e Fluxo de Trabalho (21-30)
21. Macros / Atalhos de Teclado: Associar teclas (ex: 1, 2, Space) para mudar de cena.
22. Playlist de Vídeos: Enfileirar vídeos para tocarem um após o outro automaticamente.
23. Auto-Switching por Voz: Trocar a cena para a câmera da pessoa que está falando no momento.
24. Tally Light: Indicador vermelho na tela do repórter/convidado mostrando que ele está "No Ar".
25. Cronômetro Regressivo (Countdown): Timer gigante para o início da live.
26. Relógio Digital/Analógico: Widget de hora local com suporte a fuso horário.
27. Gravação Local de Backup: Usar MediaRecorder API para gravar um backup da live no PC do diretor.
28. Agendamento de Eventos: Programar uma cena para entrar em um horário específico.
29. Perfis de Usuário: Níveis de acesso (Diretor, Operador de GC, Operador de Áudio).
30. Modo Noturno (Dark Mode): Para o painel de controle cansar menos os olhos.

Categoria 4: Engajamento e Social (31-40)
31. Integração de Chat Ao Vivo: Capturar e exibir comentários do YouTube/Twitch na tela.
32. Enquetes Ao Vivo (Live Polls): Gerar votações e mostrar os gráficos em tempo real no ar.
33. Alertas de Doação/Inscritos: Animações automáticas (ex: Superchat) acionadas via Webhook.
34. Barra de Meta (Sub Goal): Gráfico de progresso financeiro ou de seguidores.
35. Exibição de Comentário em Destaque: Um clique no painel joga o comentário do espectador na tela do OBS com animação.
36. Integração com API de Previsão do Tempo: Exibir clima local no canto da tela.
37. Feed RSS: Puxar notícias automáticas de portais e jogar na barra de rolagem (Ticker).
38. Filtro de Palavrões (Profanity Filter): Para mensagens de chat exibidas na tela.
39. Compartilhamento de Tela (Screen Share): Capturar a tela do convidado via WebRTC.
40. Whiteboard/Anotações Ao Vivo: O diretor pode desenhar na tela (estilo comentarista esportivo).

Categoria 5: Técnicos e Avançados (41-50)
41. Testador de Banda (Speedtest) Integrado: Para verificar a rede do repórter antes de entrar ao vivo.
42. Monitoramento de CPU/Memória: Mostrar a saúde do navegador do painel.
43. Saída "Clean Feed": Uma segunda URL de overlay que mostra o vídeo sem os gráficos/tarjetas.
44. Bloqueio de Cena (Lock Scene): Impedir mudança acidental durante um momento crucial.
45. Importar/Exportar Projeto: Salvar tudo (cenas, nomes, configurações) num arquivo JSON para carregar depois.
46. API Endpoints Customizados: Permitir que o Stream Deck envie comandos HTTP para trocar as cenas.
47. Grid de Alinhamento e "Snap": Guias magnéticas para alinhar vídeos e gráficos com perfeição no painel.
48. Suporte a Web MIDI: Controlar faders de áudio usando uma mesa controladora física conectada via USB.
49. Log de Ações (History): Histórico do que foi para o ar (útil para comprovar exibição de comerciais).
50. Auto-Reconexão: Se o repórter remoto cair no 4G, o sistema deve reconectá-lo e voltar para a cena suavemente sem travar o OBS.

DIRETRIZ OBRIGATÓRIA DE DOCUMENTAÇÃO E MANUTENÇÃO CONTÍNUA:
- Manter um Manual de Instruções de Uso completo (MANUAL_DE_USO.md) e este Relatório de Desenvolvimento (RELATORIO_E_PROMPT.md) dentro do projeto.
- A CADA MODIFICAÇÃO, novo recurso, alteração de rota, ajuste de layout ou correção feita no código, você DEVE obrigatoriamente atualizar o MANUAL_DE_USO.md e o RELATORIO_E_PROMPT.md (incluindo o Changelog) antes de encerrar a tarefa, além de sincronizar com o repositório GitHub (rodrigofranca0001/weblive-studio-obs).
```

---

## 🚨 1.1. Regra de Ouro para IA / Desenvolvedores (Atualização Obrigatória a Cada Modificação)

> **ATENÇÃO (INSTRUÇÃO PERMANENTE DO PROJETO):**
> Sempre que qualquer arquivo de código deste projeto for modificado, criado ou removido:
> 1. **Recompile imediatamente o executável portátil (`node build-exe.js`)** para que o arquivo `WebLiveStudio.exe` esteja sempre sincronizado com as últimas alterações de HTML/CSS/JS.
> 2. **Atualize imediatamente o arquivo [`MANUAL_DE_USO.md`](./MANUAL_DE_USO.md)** refletindo como operar a nova funcionalidade ou alteração.
> 3. **Atualize este arquivo [`RELATORIO_E_PROMPT.md`](./RELATORIO_E_PROMPT.md)** registrando a mudança na tabela de arquitetura e na seção de Histórico de Modificações (Changelog).
> 4. **Faça commit e push** (incluindo o `WebLiveStudio.exe` atualizado) para o repositório oficial no GitHub (`https://github.com/rodrigofranca0001/weblive-studio-obs`).

---

## 🛠️ 2. Relatório de Desenvolvimento & Arquitetura Implementada

### 2.1. Status Geral do Projeto
* **Status Atual:** Versão `3.1.0`. O caminho de **vídeo** é real e foi testado de ponta a ponta: câmera → compositor → monitores/projetor → gravação `.mkv` → RTMP recebido por um servidor de teste. O **áudio** ainda não existe (a transmissão sai com trilha silenciosa), e o vídeo WebRTC do repórter ainda não entra na estação desktop.
* **Ambiente validado:** Windows 11, Python 3.14, OpenCV 5.0, NumPy 2.5, Pillow 12.3, yt-dlp 2026.08, FFmpeg 9.0 (winget `Gyan.FFmpeg`).
* **Conta GitHub Vinculada:**
  * **Usuário:** `rodrigofranca0001`
  * **E-mail:** `rodrigofranca126@gmail.com`

### 2.2. Mapeamento de Arquivos e Responsabilidades

| Arquivo | Papel na Arquitetura | Requisitos Atendidos |
| :--- | :--- | :--- |
| `package.json` | Manifesto Node.js e script `npm start`. | Setup e execução rápida |
| `weblive_server.py` | **Servidor Python (só biblioteca padrão)**: HTTP multithread, SSE Hub (`/api/events`), SQLite3 (`weblive_studio.db`), `yt-dlp` (`/api/ytdlp`, com `cookies.txt` opcional), `FFmpegStreamerEngine` (`/api/rtmp/*`, transmite o Program real recebido via `frame_provider`, recusa iniciar sem a estação aberta e nunca expõe a chave), RSS/Atom real (`fetch_rss_headlines`), Clima real Open-Meteo (`fetch_weather`), Speedtest real Cloudflare (`run_speedtest`), API Stream Deck (`#46`) e Webhook (`#33`). | Backend, integrações e dados reais |
| `weblive_video.py` | **Motor de Vídeo Real (OpenCV + Pillow + NumPy + FFmpeg)**: `CameraSource` (DirectShow, MJPG, reconexão `#50`), `MediaSource` (arquivo/URL, pausa, loop), `ProgramCompositor` (thread própria a 30 qps: layouts single/PiP/mosaico 4-8, chroma key, cor, crop, fade, stinger, replay em câmera lenta com buffer JPEG em thread separada, todos os gráficos, Clean Feed e Preview 640x360), `FFmpegOutput` (pipe rawvideo → `.mkv` ou RTMP/RTMPS/SRT com relógio de parede, detecção de queda e máscara da chave) e `list_video_devices`/`find_ffmpeg`. | Vídeo real do Program, gravação e transmissão |
| `weblive_studio_gui.pyw` | **Estação Desktop Nativa (Tkinter, 100% Português-BR, barra de menus nativa)**: exibe os quadros reais do compositor nos monitores PRÉVIA/NO AR (16:9) e nos projetores (`NativeProjectorWindow`, Clean Feed `#43`), seleção de câmeras, mídia/fila, edição da cena em PRÉVIA, gráficos, gravação, RTMP, barra de status real (QPS/CPU/REC/AO VIVO), fila de UI thread-safe (`_ui`) e consumo dos eventos do servidor (Stream Deck/Webhook). Mixer de áudio presente só como interface. | Plataforma Desktop Nativa fora do navegador HTML |
| `WebLiveStudio.exe` | **Executável Portátil Desktop v3.0**: Inicia automaticamente a Estação Nativa Python (`weblive_studio_gui.pyw` via `pythonw.exe` sem terminal e sem navegador) ou executa sua própria **Estação Switcher Nativa WinForms C# (`NativeStudioForm`)** caso copiado sozinho para um PC sem Python! | Portabilidade 100% Desktop Nativo |
| `launcher/Launcher.cs` | Código-fonte C# WinForms contendo o Switcher Desktop Nativo (`NativeStudioForm` + `ProjectorForm`) e inicializador silencioso de `pythonw.exe`. | GUI Desktop Nativa Windows |
| `build-exe.js` | Empacotador e compilador automatizado que embute `public/` e gera `WebLiveStudio.exe`. | Build portátil automatizado (`npm run build:exe`) |
| `MANUAL_DE_USO.md` | Manual operacional passo a passo de todas as interfaces, OBS Browser Source, WebRTC, Áudio e APIs. | Documentação de uso (atualizada a cada modificação) |
| `RELATORIO_E_PROMPT.md` | Prompt Mestre + Relatório Arquitetural + Regra de Atualização Contínua + Changelog. | Continuidade de projeto à prova de interrupções |

---

## 📝 2.3. Histórico de Modificações (Changelog)

* **v1.0.0:** Implementação inicial completa da plataforma **WebLive Studio** (Servidor Node.js SSE/API, Painel do Diretor, Tela Output OBS com Clean Feed, Entrada Remota WebRTC com Mix-Minus, Compositor de Vídeo Canvas 60fps, Engine WebAudio DSP e 50 funções adicionais).
* **v1.0.1:** Criação do Manual de Instruções de Uso ([`MANUAL_DE_USO.md`](./MANUAL_DE_USO.md)) e inclusão da diretriz obrigatória no Prompt Mestre ([`RELATORIO_E_PROMPT.md`](./RELATORIO_E_PROMPT.md)) exigindo atualização automática do manual e do relatório a cada nova modificação no projeto.
* **v1.1.0:** Criação do executável portátil nativo **`WebLiveStudio.exe`** ([`launcher/Launcher.cs`](./launcher/Launcher.cs) + [`build-exe.js`](./build-exe.js)). Permite copiar um único arquivo `.exe` para qualquer computador Windows e abrir todo o sistema com duplo clique através de uma janela gráfica própria (sem usar terminal e sem exigir Node.js instalado).
* **v2.0.0:** Conversão e evolução para **Plataforma de Transmissão Profissional em Python 3** ([`weblive_server.py`](./weblive_server.py) e Estação Desktop Gráfica [`weblive_studio_gui.pyw`](./weblive_studio_gui.pyw)):
  * **Servidor Broadcast Multithreaded em Python (`ThreadingHTTPServer` + `BroadcastEventHub`)** com sincronização SSE em tempo real.
  * **Banco de Dados Nativo `SQLite3` (`weblive_studio.db`)** para persistir automaticamente o estado das cenas/projetos e gravar logs de auditoria comercial (`#49`).
  * **Integração Nativa com `yt-dlp` (`/api/ytdlp`)**: extrai streams diretos e títulos de vídeos/lives do YouTube, Twitch, Instagram e Facebook direto no Painel do Diretor e na GUI Python.
  * **Motor de Transmissão Direta `RTMP / FFmpeg` (`/api/rtmp/start` e `/api/rtmp/stop`)**: permite iniciar pipelines de streaming para YouTube Live / Twitch / Facebook tanto pela GUI Desktop Python quanto pela aba de Automação do Diretor.
  * **Extrator Real de Feed RSS em Python (`/api/rss`)** via `urllib` + `xml.etree.ElementTree`, contornando restrições de CORS para alimentar o Ticker Tape (`#7` e `#37`) com notícias reais ao vivo.
  * **Recompilação do `WebLiveStudio.exe`** com todos os novos controles de interface embutidos.
* **v3.0.0:** Transformação completa em **Software Desktop Nativo (`WebLiveNativeStudioApp` em `weblive_studio_gui.pyw` e `NativeStudioForm` em `WebLiveStudio.exe`) — SEM abrir páginas HTML no navegador**:
  * Toda a operação (Monitores duplos `PREVIEW` e `PROGRAM` renderizados a 30/60fps, Seletor de Cenas, Transições `CUT`/`AUTO`/`STINGER`/`REPLAY`, Desenho `Whiteboard #40` com o mouse direto no PGM, `Lower Thirds`, `Placar Esportivo`, `Ticker RSS`, `QR Code`, `Enquetes`, `Audio Mixer Multi-pista` com `VU Meters` nativos e `Soundboard`) roda **100% dentro da janela nativa do programa Desktop**.
  * Adicionada **Janela de Projetor Nativo (`NativeProjectorWindow` / `ProjectorForm`)** para Saída Program e Saída Clean Feed (`#43`), permitindo capturar o vídeo diretamente no OBS Studio via **"Captura de Janela" (Window Capture)** ou exibir em Tela Cheia (`F11` / Duplo Clique) em um segundo monitor.
  * ⚠️ *Nota da revisão v3.1:* na v3.0 os monitores, VU meters, speedtest, gravação, RSS, clima, QR Code e replay eram **simulados** (formas desenhadas, valores fixos, botões que só mudavam de texto), e o RTMP enviava barras de teste ou relatava "sucesso" sem FFmpeg.
* **v3.1.0:** **Vídeo real de ponta a ponta + interface 100% Português-BR**:
  * **Interface traduzida para Português-BR** com barra de menus nativa do Windows (Arquivo, Cenas e Cortes, Gráficos na Tela, Áudio e Efeitos, Saídas para OBS e Transmissão, Ajuda), transições `CORTE SECO` / `SUAVE` / `VINHETA` e nomes de layouts/fundos em português.
  * **Novo motor [`weblive_video.py`](./weblive_video.py):** câmeras reais (até 2, com nomes vindos do DirectShow), vídeo do computador ou de link via yt-dlp (imagem, ainda sem som), compositor real 1280x720 @ 30 qps em thread própria, fade real, vinheta que troca a cena no meio do efeito, replay real (últimos 5 s a 50%), chroma key/cor/crop reais, QR Code real (`qrcode`), etiquetas e telas "SEM SINAL" honestas.
  * **Saídas reais via FFmpeg:** gravação `.mkv` em `gravacoes/` e transmissão RTMP/RTMPS/SRT do Program real com trilha AAC silenciosa (exigida pelas plataformas); campo de **chave de transmissão** oculto (antes era fixo `live_key`); queda do FFmpeg detectada e informada; chave mascarada em logs e fora do SSE.
  * **Dados reais:** manchetes RSS/Atom (sem manchetes inventadas no fallback), clima Open-Meteo por cidade (atualiza a cada 15 min), speedtest Cloudflare (download/envio/latência).
  * **Integrações na estação desktop:** a API do Stream Deck (`scene`, `preview`, `cut`, `auto`, `stinger`, `replay`, `gc`, `placar`, `ticker`, `gravar`) e o webhook de doações agora agem na GUI nativa.
  * **Honestidade de interface:** VU meters e visualizador de áudio falsos removidos; avisos claros de que áudio, efeitos e vídeo do repórter ainda não funcionam na estação desktop; enquete começa zerada e com opções editáveis; meta com valores editáveis.
  * **Correções:** layout de PGM agora segue a cena (antes usava um combobox global); atalhos de teclado não disparam ao digitar em Spinbox/Combobox; barra superior não corta mais botões (indicadores foram para a barra de status no rodapé); monitores em 16:9; desenho na tela mapeado à imagem exibida; importação de projetos v3.0 convertida.
  * **Dependências:** `opencv-python`, `numpy` e `qrcode` adicionados ao `requirements.txt`; `gravacoes/` e `cookies.txt` no `.gitignore`.
  * **Desempenho medido:** compositor 30 qps parado, 29,8 gravando e 30,2 transmitindo (CPU do app ~13-23%); render de cena PiP caiu de 17,5 ms para 3,2 ms com fundo em cache, caminho rápido para fonte em tela cheia e etiquetas/telas "SEM SINAL" pré-renderizadas.

---

## 🔄 3. Guia Rápido de Retomada (Caso o Trabalho Seja Interrompido)

Se você abrir este projeto em uma nova sessão ou outro computador, basta seguir estes passos:

1. **Ler este arquivo (`RELATORIO_E_PROMPT.md`)** para recuperar todo o contexto funcional e arquitetural.
2. **Instalar dependências (uma vez):**
   ```powershell
   python -m pip install -r requirements.txt
   winget install Gyan.FFmpeg
   ```
3. **Abrir a Estação Desktop (modo principal):** duplo clique em `weblive_studio_gui.pyw` ou `WebLiveStudio.exe` (para ver erros no console: `python weblive_studio_gui.pyw`).
4. **Modo navegador (legado, opcional):** `python weblive_server.py` (ou `node server.js`) e acessar:
   * **Painel do Diretor:** `http://localhost:3000/index.html`
   * **OBS Browser Source (Com Gráficos):** `http://localhost:3000/output.html`
   * **OBS Clean Feed (Sem Gráficos - `#43`):** `http://localhost:3000/output.html?clean=1`
   * **Link do Repórter WebRTC (`Core #7`):** `http://localhost:3000/guest.html?guest=Reporter1`
5. **Próximos Passos (Backlog, em ordem de prioridade):**
   * **Áudio real:** captura de microfones (ex.: `sounddevice`), mixer com volume/mudo/pan/delay/ducking/pânico, VU meters reais, áudio da mídia (decodificar via FFmpeg) e envio da mixagem ao FFmpeg (gravação e RTMP) sincronizada com o vídeo.
   * **Repórter WebRTC na estação desktop:** receber o vídeo/áudio do `guest.html` no Python (ex.: `aiortc`) como fonte `guest1`, com tally e mix-minus.
   * **Estação de reserva C# (`launcher/Launcher.cs`):** hoje é demonstrativa; tornar real ou avisar que exige Python.
   * Opções de qualidade: 1080p, bitrate e encoder por hardware (`h264_nvenc`/`h264_qsv`/`h264_amf` estão disponíveis no FFmpeg instalado).
   * Integração opcional com TURN (Coturn), chat real do YouTube/Twitch (#31) e perfis de usuário (#29) com permissões de fato.

