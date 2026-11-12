# Instalar o Habblaud (completo, com Docker)

Instale o **Habblaud** na minha máquina (**não neste projeto**) e deixe tudo rodando e configurado para os meus agentes: **Claude Code**, **Codex** ou os dois.

- **Repositório:** https://github.com/marmottajr/habblaud
- **Pasta:** `~/habblaud` (no Windows, dentro do WSL)
- **Endereço final:** https://habblaud.localhost
- **Sistemas:** macOS, Linux e Windows
- **Agentes:** Claude Code e Codex (conecte os que eu usar)

## Regras

- Este prompt vale igual no **Claude Code** e no **Codex**: siga do mesmo jeito em qualquer um dos dois.
- Faça tudo sozinho, na ordem abaixo. Só me interrompa para pedir permissão.
- Se o sandbox ou as permissões bloquearem algo (rede, pastas fora deste projeto, Docker, `sudo`), peça a minha aprovação para rodar fora dele. Nunca pule um passo por isso.
- Instale sempre a versão **completa**, sem opções reduzidas (nada de `--sem-permissoes` ou `--sem-mensagens`).
- Se algo der erro, leia o README do repositório, corrija e continue até tudo funcionar.

## 0. Descubra o sistema e os agentes

### Sistema

Detecte o sistema operacional e a arquitetura (`uname -sm`; no Windows, `$env:OS` e `[Environment]::OSVersion`) e **adapte todo o fluxo abaixo a ele**. Os comandos estão em bash: traduza para o shell do sistema quando precisar.

- **macOS** (Intel ou Apple Silicon): roda direto, usando o Homebrew.
- **Linux** (Ubuntu, Debian, Fedora, Arch…): roda direto, usando o gerenciador de pacotes da distro (`apt`, `dnf`, `pacman`…).
- **Windows 10/11**: roda pelo **WSL2**, com o Habblaud **dentro do Ubuntu do WSL**.
  - Sem WSL: `wsl --install -d Ubuntu` no PowerShell como administrador. Se pedir para reiniciar, pare e me explique em "Sua vez" que basta reiniciar e colar este mesmo prompt de novo.
  - Comandos do Windows (instalar programas, firewall, tarefas no login) rodam no PowerShell; os do Habblaud rodam no WSL (`wsl -d Ubuntu -- bash -lc "..."`).
- **Qualquer outra situação**: use o equivalente mais próximo e siga em frente. O resultado final precisa ser sempre o mesmo.

### Agentes

Descubra quais agentes eu uso e conecte **todos** os que existirem:

- **Claude Code:** `claude --version` ou pastas `~/.claude*` (e `CLAUDE_CONFIG_DIR`).
- **Codex** (CLI ou app): `codex --version` ou pastas `~/.codex*` (e `CODEX_HOME`).
- Se só um existir, siga só com ele: não instale o outro. Se nenhum existir, pare e me diga.
- **Windows:** se o Claude Code ou o Codex rodam nativos no Windows (`%USERPROFILE%\.claude`, `%USERPROFILE%\.codex`), aponte o Habblaud para essas pastas (no WSL: `/mnt/c/Users/<usuário>/...`) com `HABBLAUD_CLAUDE_DIRS` e `HABBLAUD_CODEX_DIRS`, como o README descreve, e garanta que o mod e os hooks sejam instalados nessas mesmas pastas.

## Passo a passo

### 1. Ferramentas

- Confira `git` e **Node.js 22.12+** (`node --version`). Instale ou atualize o que faltar (no Windows, dentro do WSL).
- **Claude Code** (se eu uso): **2.1.287+** (`claude --version`); atualize se for mais antigo.
- **Codex** (se eu uso): atualize para a versão mais recente, do mesmo jeito que ele foi instalado (npm `@openai/codex` ou Homebrew).
- Confira o Docker (`docker info`). Se não estiver instalado e rodando:
  - **macOS:** instale o Homebrew (se faltar) e rode `brew install --cask docker`. Abra o Docker Desktop, ative "iniciar com o login" e espere ficar pronto.
  - **Linux:** instale o Docker Engine com Compose v2 pelo script oficial (`get.docker.com`), ative o serviço no boot e coloque meu usuário no grupo `docker`.
  - **Windows:** `winget install -e --id Docker.DockerDesktop`. Abra o Docker Desktop, use o backend WSL2, ligue a integração com o Ubuntu (Settings → Resources → WSL integration), ative "iniciar com o login" e espere ficar pronto. Confira `docker info` de dentro do WSL.

### 2. Baixar

- `git clone https://github.com/marmottajr/habblaud.git ~/habblaud`
- `cd ~/habblaud && npm install`

### 3. Subir

- `npm run docker:up`: acha as contas do Claude Code e as pastas do Codex, monta só o necessário (somente leitura) e sobe o container, que reinicia sozinho junto com o Docker.

### 4. Conectar o Claude Code (se eu uso)

- `npm run mod:install`, **sem flags**: instala o mod `habblaud` e os plugins `habblaud-permissoes` e `habblaud-mensagens` em todas as minhas contas do Claude Code.
- Confira com `npm run mod:status` que os três estão instalados e ligados em todas as contas.

### 5. Conectar o Codex (se eu uso)

- `npm run codex:install`, **sem flags**: acrescenta os hooks do Habblaud no `hooks.json` de cada pasta do Codex (com backup; os outros hooks ficam).
- Confira com `npm run codex:status`. Se ele avisar sobre o Node do shell de login, corrija como a mensagem indica e rode `npm run codex:install` de novo.
- Com o Habblaud no Docker, as mensagens ao Codex passam pelo `npm run codex:bridge`, que precisa ficar sempre rodando. Crie um serviço que rode esse comando em `~/habblaud`, com o Node 22.12+ e o `codex` no `PATH` (ou `HABBLAUD_CODEX_BIN` com o caminho do binário), que reinicie se cair e suba sozinho no login:
  - **macOS:** um LaunchAgent.
  - **Linux:** um serviço systemd de usuário (com `loginctl enable-linger`).
  - **Windows:** um serviço systemd de usuário no WSL (ative `systemd=true` em `/etc/wsl.conf`).
- Não tente aprovar os hooks por mim nem mexer no `config.toml` do Codex: ele só aceita essa aprovação dentro dele, em `/hooks`. Isso fica para mim, em "Sua vez".

### 6. Endereço bonito (portless)

- `npm install -g portless` e `portless alias habblaud 4747` (no Windows, dentro do WSL).
- O Habblaud já aceita endereços `*.localhost`: não mude nada nele.
- Garanta que o proxy do portless suba sozinho no login e confie no certificado local se ele pedir:
  - **macOS:** um LaunchAgent.
  - **Linux:** um serviço systemd de usuário (com `loginctl enable-linger`).
  - **Windows:** um serviço systemd de usuário no WSL e uma tarefa no Agendador de Tarefas que inicia o WSL no login. Confie no certificado também no Windows, para o navegador aceitar.

### 7. Testar

- `http://localhost:4747/api/health` responde, com o terminal, o responder e as mensagens pelo escritório ligados, e mostra as contas do Claude Code e do Codex que eu uso.
- Se conectou o Codex: o log do serviço do `codex:bridge` diz "conectado".
- https://habblaud.localhost abre o escritório (no Windows, teste no navegador do Windows).

## Quando terminar, me responda assim

1. **Pronto:** o endereço para abrir, o sistema detectado e os agentes conectados (Claude Code, Codex ou os dois).
2. **Sua vez** (só se for necessário): se ficou algo que só eu posso fazer, como digitar a senha do computador, reiniciar, autorizar algo nas configurações do sistema, abrir o Docker Desktop pela primeira vez ou rodar um comando no terminal, liste cada ação em passos numerados, com o comando exato para copiar. **Se conectou o Codex, inclua sempre:** feche o Codex que estiver aberto (inclusive esta conversa, se ela for no Codex), abra de novo, digite `/hooks` e aprove os hooks do Habblaud. Se não ficou nada, pule esta parte.
3. **Como usar:** abrir o Claude Code ou o Codex em qualquer projeto e ver o agente chegar (os do Codex com o selo CODEX, a partir da primeira mensagem); clicar num personagem para ver o que ele faz (tecla `T` abre o terminal); aprovar pedidos pelo escritório (tecla `P`); mandar mensagens na caixa **Mandar mensagem**; ver o Meu dia (tecla `M`); modo demonstração com `?mock=1`; e rodar `/reload-plugins` nas sessões do Claude Code que já estavam abertas.
4. **Manutenção:** status com `npm run mod:status` e `npm run codex:status`, e logs com `npm run docker:logs` (no Windows, dentro do WSL).

Seja curto e direto.
