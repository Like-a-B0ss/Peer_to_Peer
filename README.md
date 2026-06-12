# Chat Peer-to-Peer com Docker

Projeto de demonstracao para sala de aula: cada aluno roda um peer local em Docker e entra na mesma rede P2P para conversar com a turma.

O peer inicial ja deve estar rodando com o professor ou com quem for abrir a rede. Este README cobre apenas o que os peers secundarios precisam fazer.

## O que este projeto faz

- sobe um peer local em Docker;
- conecta esse peer a uma rede P2P usando Tailscale;
- abre uma interface web de chat em `http://localhost:8000`;
- salva localmente as ultimas 100 mensagens e os peers conhecidos em SQLite.

## Antes de começar

Cada aluno precisa instalar:

- Docker Desktop ou Docker Engine: https://docs.docker.com/get-started/get-docker/
- Tailscale: https://tailscale.com/download

Links oficiais usados:

- Docker Docs: https://docs.docker.com/get-started/get-docker/
- Tailscale Download: https://tailscale.com/download

## Requisitos para entrar na rede

Antes de rodar o projeto, o aluno precisa ter:

1. Docker instalado e funcionando.
2. Tailscale instalado e logado.
3. O IP Tailscale do peer inicial fornecido pelo professor.
4. Este projeto baixado na maquina.

## Como descobrir seu IP Tailscale

Depois de instalar e entrar no Tailscale, descubra o IP da sua maquina:

No Windows:

```powershell
& "C:\Program Files\Tailscale\tailscale.exe" ip -4
```

No Linux ou macOS:

```bash
tailscale ip -4
```

Guarde esse IP. Ele sera usado em `P2P_ADVERTISE_HOST`.

## Arquivos importantes

- [docker-compose.student.yml](/abs/path/c:/projetos/Peer_to_Peer/docker-compose.student.yml): compose usado pelo aluno
- [.env.student.example](/abs/path/c:/projetos/Peer_to_Peer/.env.student.example): modelo de configuracao
- [start-student.ps1](/abs/path/c:/projetos/Peer_to_Peer/start-student.ps1): inicializacao no Windows
- [start-student.sh](/abs/path/c:/projetos/Peer_to_Peer/start-student.sh): inicializacao no Linux/macOS

## Configuracao do aluno

1. Copie `.env.student.example` para `.env.student`.
2. Edite o arquivo `.env.student`.

Exemplo:

```env
CONTAINER_NAME=p2p-aluno1
PEER_NAME=aluno1
HTTP_PORT=8000
P2P_PORT=7000
P2P_ADVERTISE_HOST=100.70.29.126
BOOTSTRAP_PEERS=100.88.10.20:7000
MAX_CONNECTIONS=20
MESSAGE_RATE_LIMIT=8
RATE_LIMIT_WINDOW_SECONDS=10
```

O que cada campo significa:

- `CONTAINER_NAME`: nome local do container Docker.
- `PEER_NAME`: nome que identifica o aluno no peer.
- `HTTP_PORT`: porta local da interface web.
- `P2P_PORT`: porta local usada pelo peer.
- `P2P_ADVERTISE_HOST`: IP Tailscale da maquina do aluno.
- `BOOTSTRAP_PEERS`: IP e porta do peer inicial.
- `MAX_CONNECTIONS`: limite de conexoes P2P simultaneas.
- `MESSAGE_RATE_LIMIT`: limite de mensagens por peer.
- `RATE_LIMIT_WINDOW_SECONDS`: janela de tempo do rate limit.

## Como executar

### Windows

Abra PowerShell na pasta do projeto e rode:

```powershell
.\start-student.ps1
```

### Linux ou macOS

No terminal, dentro da pasta do projeto:

```bash
chmod +x start-student.sh
./start-student.sh
```

### Alternativa manual

Se preferir, rode direto com Docker Compose:

```bash
docker compose --env-file .env.student -f docker-compose.student.yml up --build
```

## Como abrir o chat

Depois que o container subir, abra:

```text
http://localhost:8000
```

Se o aluno estiver rodando mais de um peer na mesma maquina, mude `HTTP_PORT` no `.env.student`.

## O que esperar quando funcionar

- a pagina do chat abre no navegador;
- o peer aparece com seu nome e endereco P2P;
- a lista de peers conhecidos comeca a ser preenchida;
- mensagens enviadas em outro peer aparecem no seu chat.

## Persistencia

Cada aluno tem persistencia local em volume Docker:

- banco SQLite em `/data/chat.db`;
- mensagens permanecem apos reinicio do container;
- peers conhecidos permanecem apos reinicio do container.

Se o volume Docker for removido, esses dados locais sao apagados.

## Moderacao basica da rede

O projeto usa protecoes simples contra abuso:

- `MAX_CONNECTIONS`: limita quantas conexoes simultaneas um peer aceita;
- `MESSAGE_RATE_LIMIT`: limita quantas mensagens um peer pode repassar;
- `RATE_LIMIT_WINDOW_SECONDS`: define a janela usada nesse limite.

Padrao atual:

- `20` conexoes
- `8` mensagens por `10` segundos por peer

## Problemas comuns

`Tailscale nao responde`

- confirme que o aplicativo esta instalado e logado;
- teste `tailscale ip -4` ou o comando equivalente no Windows.

`Docker nao sobe o projeto`

- confirme que o Docker Desktop esta aberto;
- teste `docker --version`;
- teste `docker compose version`.

`Nao conecta ao chat da turma`

- confira se `BOOTSTRAP_PEERS` aponta para o IP correto do peer inicial;
- confira se `P2P_ADVERTISE_HOST` e o IP Tailscale da sua maquina;
- confira se o peer inicial ainda esta online.

`A porta 8000 esta ocupada`

- troque `HTTP_PORT` no `.env.student`, por exemplo para `8010`;
- depois abra `http://localhost:8010`.

## Estrutura do projeto

- [app.py](/abs/path/c:/projetos/Peer_to_Peer/app.py): no P2P + API HTTP + WebSocket
- [static/index.html](/abs/path/c:/projetos/Peer_to_Peer/static/index.html): interface web
- [Dockerfile](/abs/path/c:/projetos/Peer_to_Peer/Dockerfile): imagem da aplicacao
- [docker-compose.student.yml](/abs/path/c:/projetos/Peer_to_Peer/docker-compose.student.yml): compose para alunos

Fontes:

- Docker Docs: https://docs.docker.com/get-started/get-docker/
- Tailscale Download: https://tailscale.com/download
