import asyncio
import json
import logging
import os
import sqlite3
import time
import uuid
from collections import deque
from contextlib import suppress

from aiohttp import WSMsgType, web


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)


class PeerNode:
    def __init__(self) -> None:
        self.peer_name = os.getenv("PEER_NAME", "peer")
        self.http_host = os.getenv("HTTP_HOST", "0.0.0.0")
        self.http_port = int(os.getenv("HTTP_PORT", "8000"))
        self.p2p_bind_host = os.getenv("P2P_BIND_HOST", "0.0.0.0")
        self.p2p_port = int(os.getenv("P2P_PORT", "7000"))
        self.p2p_advertise_host = os.getenv("P2P_ADVERTISE_HOST", self.peer_name)
        self.bootstrap_peers = self._parse_peers(os.getenv("BOOTSTRAP_PEERS", ""))
        self.db_path = os.getenv("DB_PATH", "/data/chat.db")
        self.max_connections = int(os.getenv("MAX_CONNECTIONS", "20"))
        self.message_rate_limit = int(os.getenv("MESSAGE_RATE_LIMIT", "8"))
        self.rate_limit_window = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "10"))
        self.connected_peers: dict[str, dict] = {}
        self.known_peers: set[str] = set(self.bootstrap_peers)
        self.seen_messages: set[str] = set()
        self.messages: list[dict] = []
        self.websockets: set[web.WebSocketResponse] = set()
        self.server: asyncio.base_events.Server | None = None
        self.background_tasks: list[asyncio.Task] = []
        self.db: sqlite3.Connection | None = None
        self.peer_message_times: dict[str, deque[float]] = {}

    def _parse_peers(self, raw_peers: str) -> list[str]:
        peers = []
        for item in raw_peers.split(","):
            peer = item.strip()
            if peer:
                peers.append(peer)
        return peers

    def _self_address(self) -> str:
        return f"{self.p2p_advertise_host}:{self.p2p_port}"

    async def start(self) -> None:
        self.init_db()
        self.load_known_peers()
        self.load_messages()
        self.server = await asyncio.start_server(
            self.handle_peer_connection,
            self.p2p_bind_host,
            self.p2p_port,
        )
        logging.info("Peer %s ouvindo P2P em %s", self.peer_name, self.p2p_port)

        self.background_tasks.append(asyncio.create_task(self.bootstrap_loop()))
        self.background_tasks.append(asyncio.create_task(self.health_loop()))

    async def stop(self) -> None:
        for task in self.background_tasks:
            task.cancel()
        for task in self.background_tasks:
            with suppress(asyncio.CancelledError):
                await task

        for peer_id, peer in list(self.connected_peers.items()):
            await self._disconnect_peer(peer_id, peer)

        if self.server:
            self.server.close()
            await self.server.wait_closed()

        if self.db is not None:
            self.db.close()
            self.db = None

    def init_db(self) -> None:
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

        self.db = sqlite3.connect(self.db_path)
        self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                author TEXT NOT NULL,
                content TEXT NOT NULL,
                origin TEXT NOT NULL,
                timestamp INTEGER NOT NULL
            )
            """
        )
        self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS known_peers (
                address TEXT PRIMARY KEY
            )
            """
        )
        self.db.commit()

    def load_known_peers(self) -> None:
        if self.db is None:
            return

        rows = self.db.execute(
            """
            SELECT address
            FROM known_peers
            """
        ).fetchall()

        persisted_peers = {row[0] for row in rows if row[0]}
        self.known_peers.update(persisted_peers)

    def load_messages(self) -> None:
        if self.db is None:
            return

        rows = self.db.execute(
            """
            SELECT id, author, content, origin, timestamp
            FROM messages
            ORDER BY timestamp ASC
            LIMIT 100
            """
        ).fetchall()

        self.messages = [
            {
                "type": "chat",
                "id": row[0],
                "author": row[1],
                "content": row[2],
                "origin": row[3],
                "timestamp": row[4],
            }
            for row in rows
        ]
        self.seen_messages.update(message["id"] for message in self.messages)

    def save_message(self, message: dict) -> None:
        if self.db is None:
            return

        self.db.execute(
            """
            INSERT OR IGNORE INTO messages (id, author, content, origin, timestamp)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                message["id"],
                message["author"],
                message["content"],
                message["origin"],
                message["timestamp"],
            ),
        )
        self.db.execute(
            """
            DELETE FROM messages
            WHERE id NOT IN (
                SELECT id
                FROM messages
                ORDER BY timestamp DESC
                LIMIT 100
            )
            """
        )
        self.db.commit()

    def add_known_peer(self, address: str) -> None:
        if not address or address == self._self_address():
            return

        if address in self.known_peers:
            return

        self.known_peers.add(address)
        if self.db is None:
            return

        self.db.execute(
            """
            INSERT OR IGNORE INTO known_peers (address)
            VALUES (?)
            """,
            (address,),
        )
        self.db.commit()

    def remove_known_peer(self, address: str) -> None:
        if address in self.bootstrap_peers:
            return

        self.known_peers.discard(address)
        if self.db is None:
            return

        self.db.execute(
            """
            DELETE FROM known_peers
            WHERE address = ?
            """,
            (address,),
        )
        self.db.commit()

    async def bootstrap_loop(self) -> None:
        await asyncio.sleep(2)
        while True:
            for address in list(self.known_peers):
                if address == self._self_address():
                    continue
                if address in self.connected_peers:
                    continue
                await self.connect_to_peer(address)
            await asyncio.sleep(5)

    async def health_loop(self) -> None:
        while True:
            payload = {
                "type": "peer_list",
                "peers": sorted(self.active_peer_ids() | self.known_peers | {self._self_address()}),
            }
            await self.broadcast(payload)
            await asyncio.sleep(10)

    async def connect_to_peer(self, address: str) -> None:
        if len(self.connected_peers) >= self.max_connections:
            return

        try:
            host, port_text = address.split(":")
            reader, writer = await asyncio.open_connection(host, int(port_text))
        except Exception as exc:
            logging.debug("Falha ao conectar em %s: %s", address, exc)
            return

        logging.info("%s conectado ao peer %s", self.peer_name, address)
        await self.register_connection(reader, writer, announced_address=address)

    async def register_connection(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        announced_address: str | None = None,
    ) -> None:
        peer_id = announced_address or self._writer_address(writer)
        self.connected_peers[peer_id] = {
            "reader": reader,
            "writer": writer,
        }
        self.add_known_peer(peer_id)

        await self.send_json(
            writer,
            {
                "type": "hello",
                "peer_name": self.peer_name,
                "address": self._self_address(),
            },
        )

        task = asyncio.create_task(self.read_peer_messages(peer_id, reader, writer))
        self.connected_peers[peer_id]["task"] = task
        await self.notify_web_clients()

    async def handle_peer_connection(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        if len(self.connected_peers) >= self.max_connections:
            logging.warning("%s rejeitou conexao por limite maximo", self.peer_name)
            writer.close()
            with suppress(Exception):
                await writer.wait_closed()
            return

        peer_id = self._writer_address(writer)
        logging.info("%s recebeu conexão de %s", self.peer_name, peer_id)
        await self.register_connection(reader, writer, announced_address=peer_id)

    def _writer_address(self, writer: asyncio.StreamWriter) -> str:
        host, port = writer.get_extra_info("peername")[:2]
        return f"{host}:{port}"

    async def read_peer_messages(
        self,
        peer_id: str,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        try:
            while not reader.at_eof():
                raw = await reader.readline()
                if not raw:
                    break

                payload = json.loads(raw.decode())
                new_peer_id = await self.process_peer_payload(peer_id, payload, writer)
                if new_peer_id != peer_id:
                    self.remove_known_peer(peer_id)
                    self.connected_peers[new_peer_id] = self.connected_peers.pop(peer_id)
                    self.peer_message_times[new_peer_id] = self.peer_message_times.pop(peer_id, deque())
                    peer_id = new_peer_id
        except Exception as exc:
            logging.debug("Leitura encerrada com %s: %s", peer_id, exc)
        finally:
            peer = self.connected_peers.get(peer_id)
            if peer:
                await self._disconnect_peer(peer_id, peer)

    async def process_peer_payload(
        self,
        peer_id: str,
        payload: dict,
        writer: asyncio.StreamWriter,
    ) -> str:
        message_type = payload.get("type")

        if message_type == "hello":
            announced_address = payload.get("address")
            if not announced_address:
                raise ConnectionError("peer sem endereco anunciado")

            self.remove_known_peer(peer_id)
            self.add_known_peer(announced_address)
            logging.info("%s identificou peer %s", self.peer_name, announced_address)
            return announced_address

        if message_type == "peer_list":
            for address in payload.get("peers", []):
                self.add_known_peer(address)
            await self.notify_web_clients()
            return peer_id

        if message_type == "chat":
            if not self._allow_peer_message(peer_id):
                logging.warning("%s limitou mensagens do peer %s", self.peer_name, peer_id)
                return peer_id

            message_id = payload.get("id")
            if not message_id or message_id in self.seen_messages:
                return peer_id

            self.seen_messages.add(message_id)
            self.messages.append(payload)
            self.messages = self.messages[-100:]
            self.save_message(payload)
            await self.notify_web_clients()
            await self.broadcast(payload, exclude={peer_id})
            return peer_id

        if message_type == "ping":
            await self.send_json(writer, {"type": "pong"})

        return peer_id

    async def _disconnect_peer(self, peer_id: str, peer: dict) -> None:
        self.connected_peers.pop(peer_id, None)
        self.peer_message_times.pop(peer_id, None)
        task = peer.get("task")
        if task and task is not asyncio.current_task():
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

        writer = peer["writer"]
        writer.close()
        with suppress(Exception):
            await writer.wait_closed()
        await self.notify_web_clients()

    async def send_json(self, writer: asyncio.StreamWriter, payload: dict) -> None:
        writer.write((json.dumps(payload) + "\n").encode())
        await writer.drain()

    async def broadcast(self, payload: dict, exclude: set[str] | None = None) -> None:
        exclude = exclude or set()
        for peer_id, peer in list(self.connected_peers.items()):
            if peer_id in exclude:
                continue
            try:
                await self.send_json(peer["writer"], payload)
            except Exception:
                await self._disconnect_peer(peer_id, peer)

    async def create_message(self, author: str, content: str) -> dict:
        message = {
            "type": "chat",
            "id": str(uuid.uuid4()),
            "author": author,
            "content": content,
            "origin": self.peer_name,
            "timestamp": int(time.time()),
        }
        self.seen_messages.add(message["id"])
        self.messages.append(message)
        self.messages = self.messages[-100:]
        self.save_message(message)
        await self.notify_web_clients()
        await self.broadcast(message)
        return message

    def snapshot(self) -> dict:
        return {
            "peer_name": self.peer_name,
            "p2p_address": self._self_address(),
            "known_peers": sorted(self.active_peer_ids() | self.known_peers),
            "messages": self.messages[-100:],
        }

    def active_peer_ids(self) -> set[str]:
        return set(self.connected_peers.keys())

    def _allow_peer_message(self, peer_id: str) -> bool:
        now = time.time()
        timestamps = self.peer_message_times.setdefault(peer_id, deque())

        while timestamps and now - timestamps[0] > self.rate_limit_window:
            timestamps.popleft()

        if len(timestamps) >= self.message_rate_limit:
            return False

        timestamps.append(now)
        return True

    async def notify_web_clients(self) -> None:
        if not self.websockets:
            return

        payload = json.dumps(self.snapshot())
        dead_clients = set()
        for ws in self.websockets:
            try:
                await ws.send_str(payload)
            except Exception:
                dead_clients.add(ws)
        self.websockets -= dead_clients


async def index(_: web.Request) -> web.Response:
    with open("static/index.html", "r", encoding="utf-8") as handler:
        return web.Response(text=handler.read(), content_type="text/html")


async def get_state(request: web.Request) -> web.Response:
    node: PeerNode = request.app["node"]
    return web.json_response(node.snapshot())


async def post_message(request: web.Request) -> web.Response:
    node: PeerNode = request.app["node"]
    data = await request.json()
    author = (data.get("author") or "Anonimo").strip()[:30]
    content = (data.get("content") or "").strip()[:300]
    if not content:
        return web.json_response({"error": "Mensagem vazia"}, status=400)

    message = await node.create_message(author=author, content=content)
    return web.json_response(message, status=201)


async def websocket_handler(request: web.Request) -> web.WebSocketResponse:
    node: PeerNode = request.app["node"]
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    node.websockets.add(ws)
    await ws.send_json(node.snapshot())

    async for msg in ws:
        if msg.type == WSMsgType.ERROR:
            logging.warning("WebSocket encerrado com erro: %s", ws.exception())

    node.websockets.discard(ws)
    return ws


async def on_startup(app: web.Application) -> None:
    await app["node"].start()


async def on_cleanup(app: web.Application) -> None:
    await app["node"].stop()


def create_app() -> web.Application:
    app = web.Application()
    node = PeerNode()
    app["node"] = node
    app.router.add_get("/", index)
    app.router.add_get("/api/state", get_state)
    app.router.add_post("/api/messages", post_message)
    app.router.add_get("/ws", websocket_handler)
    app.router.add_static("/static/", path="static", show_index=False)
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    return app


if __name__ == "__main__":
    web.run_app(
        create_app(),
        host=os.getenv("HTTP_HOST", "0.0.0.0"),
        port=int(os.getenv("HTTP_PORT", "8000")),
    )
