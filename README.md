# Chat Peer-to-Peer com Docker

Projeto de demonstracao para rodar um peer local em Docker e conectar varios peers na mesma rede interna, como o Wi-Fi da casa, laboratorio ou sala.

Um peer inicial precisa estar acessivel para os demais entrarem na rede. Este README cobre tanto o peer inicial quanto os peers que vao se conectar.

## O que este projeto faz

- sobe um peer local em Docker;
- conecta esse peer a uma rede P2P pela rede local;
- abre uma interface web de chat em `http://localhost:8000`;
- salva localmente as ultimas 100 mensagens e os peers conhecidos em SQLite.

## Antes de comecar

Cada maquina precisa instalar:

- Docker Desktop ou Docker Engine: https://docs.docker.com/get-started/get-docker/

## Requisitos para entrar na rede

Antes de rodar o projeto, voce precisa ter:

1. Docker instalado e funcionando.
2. Este projeto baixado na maquina.
3. O IP local do peer inicial na mesma rede Wi-Fi ou LAN.

## Endereco anunciado do peer

Cada peer anuncia para os outros um endereco no formato `host:porta`.

- `P2P_ADVERTISE_HOST`: IP local da maquina dentro da rede.
- `P2P_ADVERTISE_PORT`: porta anunciada para conexoes P2P.

Todos os peers precisam estar na mesma rede e conseguir se alcancar pelo IP local.

## Arquivos importantes

- [docker-compose.student.yml](c:/projetos/Peer_to_Peer/docker-compose.student.yml): compose usado pelo aluno
- [.env.student.example](c:/projetos/Peer_to_Peer/.env.student.example): modelo de configuracao
- [start-student.ps1](c:/projetos/Peer_to_Peer/start-student.ps1): inicializacao no Windows
- [start-student.sh](c:/projetos/Peer_to_Peer/start-student.sh): inicializacao no Linux/macOS
- [docker-compose.yml](c:/projetos/Peer_to_Peer/docker-compose.yml): compose principal para subir um peer real

## Configuracao do aluno

1. Copie `.env.student.example` para `.env.student`.
2. Edite o arquivo `.env.student`.
3. Troque `P2P_ADVERTISE_HOST` pelo IP local da maquina do aluno.

Exemplo:

```env
CONTAINER_NAME=p2p-aluno1
PEER_NAME=aluno1
HTTP_PORT=8000
P2P_PORT=7000
P2P_ADVERTISE_HOST=SEU_IP_LOCAL
P2P_ADVERTISE_PORT=7000
BOOTSTRAP_PEERS=10.47.6.142:7000
MAX_CONNECTIONS=50
MESSAGE_RATE_LIMIT=8
RATE_LIMIT_WINDOW_SECONDS=10
```

O que cada campo significa:

- `CONTAINER_NAME`: nome local do container Docker.
- `PEER_NAME`: nome que identifica o aluno no peer.
- `HTTP_PORT`: porta local da interface web.
- `P2P_PORT`: porta TCP em que o peer escuta conexoes P2P.
- `P2P_ADVERTISE_HOST`: IP local anunciado aos outros peers.
- `P2P_ADVERTISE_PORT`: porta anunciada aos outros peers.
- `BOOTSTRAP_PEERS`: IP local e porta do peer inicial.
- `MAX_CONNECTIONS`: limite de conexoes P2P simultaneas.
- `MESSAGE_RATE_LIMIT`: limite de mensagens por peer.
- `RATE_LIMIT_WINDOW_SECONDS`: janela de tempo do rate limit.

## Configuracao do peer inicial

Se voce for o peer inicial da rede:

- use o seu proprio IP local em `P2P_ADVERTISE_HOST`;
- use a porta local em `P2P_ADVERTISE_PORT`;
- deixe `BOOTSTRAP_PEERS` vazio;
- entregue para os demais o endereco `10.47.6.142:7000` ou o IP local atual da sua maquina, se ele mudar.

Exemplo:

```env
CONTAINER_NAME=p2p-inicial
PEER_NAME=peer-inicial
HTTP_PORT=8000
P2P_PORT=7000
P2P_ADVERTISE_HOST=10.47.6.142
P2P_ADVERTISE_PORT=7000
BOOTSTRAP_PEERS=
MAX_CONNECTIONS=50
MESSAGE_RATE_LIMIT=8
RATE_LIMIT_WINDOW_SECONDS=10
```

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

### Alternativa manual para aluno

```bash
docker compose --env-file .env.student -f docker-compose.student.yml up --build
```

### Alternativa manual para peer principal

```bash
docker compose --env-file .env.student -f docker-compose.yml up --build
```

## Como abrir o chat

Depois que o container subir, abra no navegador da propria maquina:

```text
http://localhost:8000
```

Se estiver rodando mais de um peer na mesma maquina, mude `HTTP_PORT` no `.env.student`.

## O que esperar quando funcionar

- a pagina do chat abre no navegador;
- o peer aparece com seu nome e endereco P2P;
- a lista de peers conhecidos comeca a ser preenchida;
- mensagens enviadas em outro peer aparecem no seu chat.

## Persistencia

Cada peer tem persistencia local em volume Docker:

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

- `50` conexoes
- `8` mensagens por `10` segundos por peer

## Problemas comuns

`Docker nao sobe o projeto`

- confirme que o Docker Desktop esta aberto;
- teste `docker --version`;
- teste `docker compose version`.

`Nao conecta ao chat da turma`

- confira se `BOOTSTRAP_PEERS` aponta para o IP local e porta corretos do peer inicial;
- confira se `P2P_ADVERTISE_HOST` e `P2P_ADVERTISE_PORT` sao alcancaveis a partir de outra maquina da mesma rede;
- confira se os dois dispositivos estao no mesmo Wi-Fi ou na mesma LAN;
- confira se o peer inicial ainda esta online.

`A porta 8000 esta ocupada`

- troque `HTTP_PORT` no `.env.student`, por exemplo para `8010`;
- depois abra `http://localhost:8010`.

## Estrutura do projeto

- [app.py](c:/projetos/Peer_to_Peer/app.py): no P2P, API HTTP e WebSocket
- [static/index.html](c:/projetos/Peer_to_Peer/static/index.html): interface web
- [Dockerfile](c:/projetos/Peer_to_Peer/Dockerfile): imagem da aplicacao
- [docker-compose.yml](c:/projetos/Peer_to_Peer/docker-compose.yml): compose principal para peer real
- [docker-compose.student.yml](c:/projetos/Peer_to_Peer/docker-compose.student.yml): compose para alunos

## Fontes

- Docker Docs: https://docs.docker.com/get-started/get-docker/
