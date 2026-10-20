# 📘 Manual de Instruções de Uso — WebLive Studio Pro v3.1 (Estação Desktop Nativa)

> **Regra de Governança:** Este manual faz parte da documentação viva do projeto e **deve ser atualizado obrigatoriamente a cada nova modificação, recurso ou ajuste de interface** realizado no sistema.

---

## 1. Visão Geral

O **WebLive Studio Pro v3.1** é um programa de produção ao vivo para Windows (estilo vMix / OBS Studio) que roda em **janela própria**, sem abrir páginas no navegador, com **todos os menus e botões em Português-BR**.

Ele pega **câmeras e vídeos reais**, monta o **PROGRAMA** (a imagem que vai ao ar) em **1280x720 a 30 quadros por segundo** com tarjetas, placar, notícias e demais gráficos, e entrega esse resultado de três formas:

* **Projetor / Saída Limpa** — janelas que o OBS Studio captura com "Captura de Janela";
* **Gravação de segurança** — arquivo `.mkv` no computador;
* **Transmissão direta** — RTMP para YouTube, Twitch ou Facebook, sem precisar do OBS.

### 1.1. O que já é real e o que ainda não é

| Área | Situação na v3.1 |
| :--- | :--- |
| Câmeras (webcam, celular como "Câmera Virtual do Windows", OBS Virtual Camera) | ✅ Real, até 2 câmeras, com reconexão automática |
| Vídeo do computador ou de link (yt-dlp) | ✅ Real (imagem; **sem som** por enquanto) |
| Monitores PRÉVIA / NO AR, transições Corte Seco / Suave / Vinheta | ✅ Real |
| Gráficos (tarjeta, placar, notícias, código QR, enquete, meta, doação, clima, contagem, desenho na tela) | ✅ Real, desenhados no próprio vídeo |
| Replay em câmera lenta | ✅ Real (últimos 5 segundos do programa, a 50% da velocidade) |
| Notícias (RSS), Clima e Teste de Internet | ✅ Dados reais da internet |
| Gravação local e Transmissão RTMP | ✅ Real (exigem FFmpeg) |
| API do Stream Deck e alertas de doação por webhook | ✅ Chegam à estação desktop |
| **Áudio** (mesa de som, medidores, efeitos, talkback, abaixar trilha, corte por voz) | ⚠️ **Ainda não processa som.** A transmissão sai com **áudio em silêncio** |
| **Repórter pelo celular (WebRTC)** | ⚠️ O vídeo do celular **ainda não entra** no PROGRAMA da estação desktop (aparece "SEM SINAL") |
| Estação de reserva embutida no `.exe` (PC sem Python) | ⚠️ Apenas demonstrativa: não usa câmeras nem grava |

---

## 2. Instalação (primeira vez)

1. Instale o **Python 3.12 ou mais novo** (python.org), marcando *"Add Python to PATH"*.
2. Na pasta do programa, abra o terminal e instale as bibliotecas:
   ```powershell
   python -m pip install -r requirements.txt
   ```
   (Pillow, OpenCV, NumPy, yt-dlp e qrcode.)
3. Instale o **FFmpeg** (necessário para gravar e transmitir):
   ```powershell
   winget install Gyan.FFmpeg
   ```
   Alternativa: copie o `ffmpeg.exe` para a pasta do programa.

> Se faltar alguma biblioteca, o programa mostra uma janela avisando qual instalar. Se faltar o FFmpeg, o rodapé da janela avisa e os botões de gravar/transmitir explicam o que fazer.

---

## 3. Como Abrir o Programa

* **Opção A — `WebLiveStudio.exe`:** duplo clique. Com o Python instalado, ele abre a estação completa (`weblive_studio_gui.pyw`) sem janela de terminal.
* **Opção B — `weblive_studio_gui.pyw`:** duplo clique direto no arquivo.

Ao abrir, a **Câmera 1** liga sozinha no primeiro dispositivo (a luz da webcam acende). O driver leva de 3 a 6 segundos para entregar a imagem; até lá o vídeo mostra **"SEM SINAL • conectando..."**.

---

## 4. Primeiros Passos (roteiro rápido)

1. **Escolha as câmeras** em *📷 Câmeras e Fontes de Vídeo* (coluna esquerda).
2. **Monte a cena em PRÉVIA:** clique numa cena (ou teclas `1` a `6`) e ajuste na aba *🎨 Vídeo, Mosaico e Fundo Verde* a disposição, a fonte principal e a fonte da janela sobreposta.
3. **Coloque no ar:** `✂️ CORTAR` (ou `Espaço`), `✨ SUAVE` ou `⚡ VINHETA`.
4. **Gráficos:** aba *🏷️ Tarjetas, Placar e Notícias* e aba *💬 Bate-Papo, Enquete, Meta e Código QR*.
5. **Saída:** abra o projetor para o OBS, grave uma cópia local e/ou transmita direto.

---

## 5. A Tela Principal

### 5.1. Barra de Menus
* **Arquivo:** nova cena, salvar/abrir projeto (.JSON), abrir vídeo do computador, iniciar/parar gravação, abrir a pasta das gravações, sair.
* **Cenas e Cortes:** corte seco, transição suave, vinheta, replay e seleção direta das cenas.
* **Gráficos na Tela:** liga/desliga cada gráfico e busca notícias reais.
* **Áudio e Efeitos:** botão de pânico e efeitos sonoros (bipes locais por enquanto).
* **Saídas para OBS e Transmissão:** projetores e transmissão direta.
* **Ajuda:** como capturar no OBS, como transmitir direto e informações do programa.

### 5.2. Barra Superior
* **🕒 Relógio (#26)** — hora local.
* **Perfil (#29)** — Diretor Geral, Operador de Caracteres (GC) ou Operador de Som (por enquanto só registra no histórico).
* **🔇 Silenciar Tudo (#20)** — botão de pânico (passa a cortar o som de verdade quando o áudio real estiver implementado).
* **📺 Abrir Projetor para OBS** e **🧼 Abrir Janela Saída Limpa (#43)** — veja a seção 6.

### 5.3. Coluna Esquerda

#### A. Cenas e Atalhos (#21, #44)
* **Clique numa cena** → ela vai para a **PRÉVIA** (monitor verde).
* **Teclas `1` a `6`** selecionam as cenas; **`Espaço`** corta para o ar. Os atalhos não disparam enquanto você digita num campo.
* **🔒 Travar Cena (#44)** impede qualquer troca acidental.
* **+ Nova Cena** cria uma cena personalizada (começa com a Câmera 1 em tela cheia).

#### B. Câmeras e Fontes de Vídeo
* **Câmera 1** e **Câmera 2**: escolha o dispositivo na lista (webcam, celular conectado pelo *Link para o Celular* do Windows, OBS Virtual Camera...). Use **(desligada)** para soltar o dispositivo.
* Abaixo de cada uma aparece o estado real: `ao vivo 1280x720 • 20 fps`, `conectando...` ou `sinal perdido (reconectando...)`.
* **🔄 Procurar Câmeras** atualiza a lista (útil ao plugar uma câmera nova).
* Um mesmo dispositivo não pode ser usado nas duas entradas ao mesmo tempo.

#### C. Convidado Remoto (#7, #16, #41)
* **📋 Copiar Link do Celular** — link da página do repórter (`guest.html`). ⚠️ Por enquanto o vídeo do celular só funciona com o Painel Web (seção 11); na estação desktop a fonte *Repórter (celular)* aparece como "SEM SINAL".
* **📶 Testar Internet (#41)** — teste real (~15 s) de download, envio e latência. Para transmitir em 720p30 é recomendado **envio de 6 Mbps ou mais**.
* **🎙️ Segure para Falar com o Repórter (#16)** — sinaliza o talkback para a página do repórter (a voz ainda não é enviada).

#### D. Vídeos (Internet ou Computador) e Fila (#22)
* **🐍 Carregar Link** — cole um link (YouTube, Twitch, Vimeo, arquivo .mp4 na internet...) e o yt-dlp abre o vídeo no canal **MÍDIA**.
* **📂 Do Computador** — abre um vídeo do PC (.mp4, .mov, .mkv, .webm, .avi...).
* **⏸ Pausar / ▶ Continuar** — controla a reprodução.
* **+ Adicionar à Fila** e **⏭ Próximo** — monta e percorre a fila de vídeos. Com **Avançar sozinho** marcado, ao terminar um vídeo o próximo da fila entra automaticamente; desmarcado, o vídeo repete.
* O canal MÍDIA ainda **não toca o som** do vídeo.
* **YouTube pedindo login:** veja a seção 9.

### 5.4. Coluna Central

#### A. Monitores e Transições
* **🟢 PRÉVIA (PREPARAÇÃO)** — a próxima cena, sem gráficos. **🔴 NO AR (PROGRAMA)** — exatamente o que está saindo.
* **✂️ CORTAR [Espaço]** — troca imediata.
* **✨ SUAVE** — mistura gradual (0,6 s) entre a cena atual e a nova.
* **⚡ VINHETA** — painel animado atravessa a tela e a cena troca no meio do efeito.
* **⏪ REPLAY (#8)** — repete em câmera lenta os **últimos 5 segundos** do programa, com o selo "REPLAY • CÂMERA LENTA", e volta ao vivo sozinho.
* **📏 Grade #47** — linhas-guia e área segura **só nos monitores** (não vão para o ar).
* **✏️ Desenhar na Tela Ao Vivo (#40)** — marque a caixa e desenhe com o mouse sobre o monitor NO AR; o traço sai no vídeo. **🎨 Escolher Cor** e **🗑️ Limpar Desenho**.
* **⏳ Contagem Regressiva (#25)** — tela cheia "A TRANSMISSÃO COMEÇA EM 03:00" (reinicia em 3 minutos ao reabrir depois de zerar).
* **⏺️ Gravar Cópia Local (#27)** — veja a seção 8.

#### B. Aba 🏷️ Tarjetas, Placar e Notícias
* **Tarjeta (#5):** nome e cargo; **Fixa** ou **Temporária (5 ou 8 segundos)**. Entra e sai deslizando.
* **Placar (#4):** times, pontos (atualizam na hora), cronômetro com *Iniciar / Pausar* e *Zerar Tempo*.
* **Barra de Notícias (#7/#37):** texto rolante digitado à mão, ou **📡 Buscar Notícias (#37)** para puxar manchetes reais do **Endereço do feed RSS** (padrão: g1). Aceita RSS e Atom.

#### C. Aba 🎨 Vídeo, Mosaico e Fundo Verde (#1-#10)
Os ajustes da esquerda valem para a **cena que está na PRÉVIA**:
* **Disposição das Câmeras:** *Câmera Única (Tela Cheia)*, *Janela Sobreposta (PiP)*, *Mosaico 4 Câmeras* ou *Mosaico 8 Câmeras*.
  * Os mosaicos usam a ordem fixa: Câmera 1, Câmera 2, Mídia, Repórter (o mosaico 8 tem 4 espaços livres).
* **Fundo Animado (#10):** aparece onde a imagem não cobre a tela (bordas, mosaico, fundo verde).
* **Fonte Principal** e **Fonte da Janela Sobreposta:** Câmera 1, Câmera 2, Mídia / Vídeo ou Repórter (celular).
* **Remover Fundo Verde (#3)** + **Sensibilidade:** chroma key real nas câmeras (o fundo verde vira o fundo animado).
* **Tamanho da Janela Sobreposta (#1):** de 15% a 45% da tela.

Os ajustes da direita valem para **todas as câmeras**: **Brilho**, **Contraste**, **Saturação** (#5), **Recorte da Borda Superior** (#4) e o **Texto da Marca d'água** (#6, canto superior direito; deixe vazio para ocultar).

#### D. Aba 💬 Bate-Papo, Enquete, Meta e Código QR
* **Comentário em Destaque (#35):** preencha autor e mensagem e clique em *Exibir Comentário em Destaque*. Com o filtro (#38) ligado, palavrões conhecidos viram `****`.
* **Alerta de Doação (#33):** o botão manual usa o autor e a mensagem acima. Alertas automáticos chegam pela API (seção 10).
* **Código QR (#9):** QR real e escaneável do endereço digitado.
* **Enquete (#32):** defina as duas opções, some votos com *+Voto Opção A / B* e use *Zerar Votos*.
* **Meta (#34):** informe o valor atual e o alvo.
* **Clima (#36):** digite a cidade e clique em *🌤️ Clima*; a temperatura real (Open-Meteo) entra no ar e se atualiza a cada 15 minutos.

#### E. Aba ⚙️ Transmissão, Agendador e Histórico
* **Transmissão direta:** veja a seção 7.
* **Trocar Cena às (HH:MM:SS) (#28):** agenda a cena da PRÉVIA para entrar com vinheta no horário.
* **Salvar / Abrir Projeto (.JSON) (#45):** cenas, tarjeta e barra de notícias. Projetos da v3.0 são convertidos automaticamente.
* **Histórico (#49):** tudo o que foi feito, com horário (também gravado no banco `weblive_studio.db`).

### 5.5. Coluna Direita: Mesa de Som e Efeitos
⚠️ **Ainda sem áudio real.** Os controles (volume, escuta, balanço, atraso, mudo, abaixar trilha, corte por voz) já estão na tela, mas ainda não processam som. Os medidores ficam vazios de propósito, para não indicar um sinal que não existe. Os **efeitos sonoros** tocam bipes só no alto-falante deste PC.

### 5.6. Barra de Status (rodapé)
Mostra os **quadros por segundo reais da saída** (o normal é 30), o **uso de processador** do programa, **⏺ GRAVANDO mm:ss** e **📡 AO VIVO mm:ss**, além de avisar se o FFmpeg não foi encontrado.

---

## 6. Como Capturar no OBS Studio (Captura de Janela)

1. Clique em **📺 Abrir Projetor para OBS (Saída no Ar)** (ou **🧼 Abrir Janela Saída Limpa (#43)** para o vídeo sem gráficos).
2. No OBS: **Fontes → + → Captura de Janela**.
3. Escolha a janela **`📺 WebLive Studio — SAÍDA PRINCIPAL`** (ou `SAÍDA LIMPA`).
4. Dica: **duplo clique** ou **F11** no projetor deixa em tela cheia (útil num segundo monitor). **Esc** sai da tela cheia.

---

## 7. Transmissão Direta (YouTube / Twitch / Facebook)

1. Aba **⚙️ Transmissão, Agendador e Histórico**.
2. **Servidor:** endereço RTMP da plataforma, por exemplo:
   * YouTube: `rtmp://a.rtmp.youtube.com/live2`
   * Twitch: `rtmp://live.twitch.tv/app`
   * Facebook: `rtmps://live-api-s.facebook.com:443/rtmp/`
3. **Chave:** a chave de transmissão do painel da plataforma. Ela fica oculta na tela e **nunca é gravada no histórico**.
4. **🚀 Iniciar Transmissão.** Vai ao ar o PROGRAMA real (1280x720, 30 qps, H.264 4,5 Mbps) com uma **trilha de áudio em silêncio**, exigida pelas plataformas, até o áudio real existir.
5. Se a plataforma recusar (chave errada, internet caiu...), o programa avisa com a mensagem do FFmpeg e o botão volta a *Iniciar*.
6. **⏹️ Parar Transmissão** encerra.

---

## 8. Gravação de Segurança (#27)

* **⏺️ Gravar Cópia Local** grava o PROGRAMA (com gráficos) em `gravacoes/WebLive_AAAA-MM-DD_HH-MM-SS.mkv` (H.264, 1280x720, 30 qps, **sem áudio** por enquanto).
* **⏹️ Parar Gravação** finaliza o arquivo. O histórico mostra o nome e o tamanho.
* **Arquivo → Abrir Pasta das Gravações** abre a pasta.
* O formato `.mkv` não se perde se o PC desligar no meio. Para converter em `.mp4`: `ffmpeg -i arquivo.mkv -c copy arquivo.mp4`.
* Gravação e transmissão podem rodar ao mesmo tempo. Ao fechar o programa com alguma delas ativa, ele pergunta antes e finaliza o arquivo corretamente.

---

## 9. Vídeos do YouTube que Pedem Login

O YouTube frequentemente bloqueia programas com a mensagem *"confirme que você não é um robô"*. Para liberar:
1. No navegador em que você está logado no YouTube, instale a extensão **"Get cookies.txt LOCALLY"**.
2. Abra o youtube.com, exporte os cookies e salve o arquivo como **`cookies.txt`** na pasta do WebLive Studio.
3. Carregue o link de novo.

> ⚠️ O `cookies.txt` dá acesso à sua conta: não compartilhe. Ele já está no `.gitignore` e nunca vai para o GitHub.

---

## 10. Integrações (Stream Deck #46 e Alertas #33)

O programa abre um servidor local na porta **3000** (ou na próxima livre). Os comandos agem **direto na estação desktop**.

### 10.1. Stream Deck / Bitfocus Companion (#46)
Configure botões do tipo *Website / GET Request*:

| Ação | Endereço |
| :--- | :--- |
| Cortar direto para a cena N | `http://localhost:3000/api/streamdeck?action=scene&target=1` |
| Só colocar a cena N na PRÉVIA | `http://localhost:3000/api/streamdeck?action=preview&target=2` |
| Corte seco | `http://localhost:3000/api/streamdeck?action=cut` |
| Transição suave | `http://localhost:3000/api/streamdeck?action=auto` |
| Vinheta | `http://localhost:3000/api/streamdeck?action=stinger` |
| Replay | `http://localhost:3000/api/streamdeck?action=replay` |
| Mostrar / ocultar tarjeta | `http://localhost:3000/api/streamdeck?action=gc` |
| Mostrar / ocultar placar | `http://localhost:3000/api/streamdeck?action=placar` |
| Mostrar / ocultar notícias | `http://localhost:3000/api/streamdeck?action=ticker` |
| Iniciar / parar gravação | `http://localhost:3000/api/streamdeck?action=gravar` |

### 10.2. Alertas de Doação por Webhook (#33)
Qualquer serviço pode disparar o alerta enviando `GET` ou `POST` para:
```text
http://localhost:3000/api/webhook/alert?user=NomeDoApoiador&amount=R$%2050,00&msg=Mensagem%20na%20tela
```

---

## 11. Painel Web e Página do Repórter (modo navegador, legado)

O projeto ainda contém o painel web da v1/v2 (pasta `public/`), servido pelo mesmo servidor local:
* **Painel do Diretor:** `http://localhost:3000/index.html`
* **Tela para o OBS (Fonte de Navegador):** `http://localhost:3000/output.html` (Saída Limpa: `?clean=1`)
* **Repórter pelo celular:** `http://SEU_IP:3000/guest.html?guest=Reporter1`

Nesse modo, o vídeo do repórter (WebRTC, com retorno sem eco) funciona **dentro do Painel Web**. Ele é independente da estação desktop: o que acontece no navegador não aparece nos monitores da estação, e vice-versa. Para usar só o servidor, sem a estação: `python weblive_server.py`.

---

## 12. Solução de Problemas

| Problema | O que fazer |
| :--- | :--- |
| "SEM SINAL • conectando..." por mais de 10 s | Feche outros programas que usam a câmera (Teams, Zoom, OBS) e escolha o dispositivo de novo na lista. |
| Webcam a ~20 qps | Limite do sensor com pouca luz; mais iluminação costuma subir para 30. |
| Rodapé mostrando bem menos de 30 QPS | Desligue o fundo verde (é o recurso mais pesado) ou feche projetores extras. |
| "FFmpeg não encontrado" | `winget install Gyan.FFmpeg` e reabra o programa. |
| Transmissão cai logo após iniciar | Confira servidor e chave; veja o motivo na mensagem de erro e em `gravacoes/ffmpeg_rtmp.log`. |
| Vídeo do YouTube não carrega | Veja a seção 9 (cookies.txt). |
| Notícias ou clima indisponíveis | Verifique a internet ou o endereço do feed RSS. |
