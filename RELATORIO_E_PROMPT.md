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
* **Status Atual:** Funcional (Versão `1.0.0` completa e validada sintaticamente).
* **Conta GitHub Vinculada:**
  * **Usuário:** `rodrigofranca0001`
  * **E-mail:** `rodrigofranca126@gmail.com`

### 2.2. Mapeamento de Arquivos e Responsabilidades

| Arquivo | Papel na Arquitetura | Requisitos Atendidos |
| :--- | :--- | :--- |
| `package.json` | Manifesto Node.js e script `npm start`. | Setup e execução rápida |
| `server.js` | Servidor HTTP estático + Barramento SSE (`/api/events`, `/api/sync`) + API Stream Deck + Webhooks. | Sincronia multi-dispositivo, `#33` (Webhooks), `#46` (Stream Deck HTTP API) |
| `public/index.html` | Interface Responsiva do Painel do Diretor (3 colunas, Monitores PVW/PGM, Abas e Mixer). | Core `#1`-`#7`, Topbar com `#20`, `#26`, `#29`, `#30`, `#36`, `#42` |
| `public/output.html` | Página "Browser Source" 1080p60 para o OBS Studio (suporta parâmetro `?clean=1`). | Core `#2`, `#3`, `#4`, `#5`, `#7`, `#9`, `#25`, `#32`-`#37`, `#43` (Clean Feed) |
| `public/guest.html` | Interface móvel/web para o Repórter Remoto via WebRTC. | Core `#7` (WebRTC + Retorno PGM + Mix-Minus), `#16`, `#24` (Tally), `#39`, `#41`, `#50` |
| `public/css/style.css` | Estilização Broadcast Dark/Light Mode, transições CSS e animações de GC/Stinger. | `#7`, `#30`, `#47` (Snap Grid), animações de entrada/saída |
| `public/js/state-sync.js` | Engine híbrida (`BroadcastChannel` + `EventSource` SSE) + `IndexedDB` local + Utilitários. | Core `#3` (`IndexedDB`), `#6`, `#9` (QR Code Canvas), `#38` (Profanity Filter) |
| `public/js/audio-engine.js` | Engine DSP via `WebAudio API` + Barramento Mix-Minus + Synth Soundboard + `Web MIDI`. | Core `#6`, Core `#7` (Mix-Minus), `#11`-`#20`, `#23`, `#48` |
| `public/js/video-compositor.js` | Compositor 60fps em `Canvas 2D`, Chroma Key, Multi-view 4/8, PiP, `MediaRecorder` Replay/Backup e Whiteboard. | `#1`-`#6`, `#8` (Instant Replay 10s), `#10`, `#12`, `#27` (Backup Local), `#40` |
| `public/js/webrtc-call.js` | Gerenciador `RTCPeerConnection`, Signaling, Speedtest e Watchdog de Auto-Reconexão 4G. | Core `#7`, `#39`, `#41`, `#50` |
| `public/js/director-app.js` | Orquestrador do Diretor: Cenas, Cortes, Stingers, GC, Placar, Macros, Agendamento, JSON e Logs CSV. | Core `#1`-`#7` e integração das 50 funções |
| `public/js/output-app.js` | Receptor em tempo real para o OBS Studio, renderizando Canvas + DOM Overlays e Stingers. | Sincronia sub-milissegundo com o Diretor e suporte a `?clean=1` |
| `WebLiveStudio.exe` | **Executável Portátil Único p/ Windows (435 KB)** com Interface Gráfica (GUI) e Servidor HTTP/SSE/Stream Deck nativo embutido. | Execução em qualquer PC com duplo clique (sem terminal e sem Node.js) |
| `launcher/Launcher.cs` | Código-fonte C# WinForms + `HttpListener` do executável portátil. | GUI nativa Windows, System Tray, SSE e fallback single-file |
| `build-exe.js` | Empacotador e compilador automatizado que embute `public/` e gera `WebLiveStudio.exe`. | Build portátil automatizado (`npm run build:exe`) |
| `MANUAL_DE_USO.md` | Manual operacional passo a passo de todas as interfaces, OBS Browser Source, WebRTC, Áudio e APIs. | Documentação de uso (atualizada a cada modificação) |
| `RELATORIO_E_PROMPT.md` | Prompt Mestre + Relatório Arquitetural + Regra de Atualização Contínua + Changelog. | Continuidade de projeto à prova de interrupções |

---

## 📝 2.3. Histórico de Modificações (Changelog)

* **v1.0.0:** Implementação inicial completa da plataforma **WebLive Studio** (Servidor Node.js SSE/API, Painel do Diretor, Tela Output OBS com Clean Feed, Entrada Remota WebRTC com Mix-Minus, Compositor de Vídeo Canvas 60fps, Engine WebAudio DSP e 50 funções adicionais).
* **v1.0.1:** Criação do Manual de Instruções de Uso ([`MANUAL_DE_USO.md`](./MANUAL_DE_USO.md)) e inclusão da diretriz obrigatória no Prompt Mestre ([`RELATORIO_E_PROMPT.md`](./RELATORIO_E_PROMPT.md)) exigindo atualização automática do manual e do relatório a cada nova modificação no projeto.
* **v1.1.0:** Criação do executável portátil nativo **`WebLiveStudio.exe`** ([`launcher/Launcher.cs`](./launcher/Launcher.cs) + [`build-exe.js`](./build-exe.js)). Permite copiar um único arquivo `.exe` para qualquer computador Windows e abrir todo o sistema com duplo clique através de uma janela gráfica própria (sem usar terminal e sem exigir Node.js instalado).

---

## 🔄 3. Guia Rápido de Retomada (Caso o Trabalho Seja Interrompido)

Se você abrir este projeto em uma nova sessão ou outro computador, basta seguir estes passos:

1. **Ler este arquivo (`RELATORIO_E_PROMPT.md`)** para recuperar todo o contexto funcional e arquitetural.
2. **Iniciar o Servidor Local:**
   ```powershell
   node server.js
   ```
3. **Acessar os Módulos no Navegador / OBS:**
   * **Painel do Diretor:** `http://localhost:3000/index.html`
   * **OBS Browser Source (Com Gráficos):** `http://localhost:3000/output.html`
   * **OBS Clean Feed (Sem Gráficos - `#43`):** `http://localhost:3000/output.html?clean=1`
   * **Link do Repórter WebRTC (`Core #7`):** `http://localhost:3000/guest.html?guest=Reporter1`
4. **Próximos Passos Evolutivos Sugeridos (Backlog Futuro):**
   * Integração opcional com servidor TURN dedicado (Coturn) para redes corporativas restritas no WebRTC.
   * Integração opcional via OAuth com API oficial do YouTube Live Chat / Twitch IRC em `server.js`.
   * Shaders WebGL 2.0 customizados (GLSL) adicionais para transições 3D e Lutting de cor avançado.

