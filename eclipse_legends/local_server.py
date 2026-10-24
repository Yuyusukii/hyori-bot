import os

from aiohttp import web


def _env_ativo(nome, padrao=True):
    valor = os.getenv(nome)
    if valor is None:
        return padrao
    return valor.strip().lower() not in {"0", "false", "nao", "não", "off"}


def _porta_local():
    valor = os.getenv("LOCAL_SERVER_PORT", "8080").strip()
    try:
        porta = int(valor)
    except ValueError as exc:
        raise RuntimeError("LOCAL_SERVER_PORT precisa ser um numero inteiro.") from exc
    if not 1 <= porta <= 65535:
        raise RuntimeError("LOCAL_SERVER_PORT precisa estar entre 1 e 65535.")
    return porta


class LocalServer:
    def __init__(self, bot, host, port):
        self.bot = bot
        self.host = host
        self.port = port
        self.runner = None

    def _status(self):
        conectado = self.bot.is_ready()
        latencia = round(self.bot.latency * 1000) if conectado else None
        return {
            "service": "Eclipse Legends",
            "status": "online" if conectado else "starting",
            "discord_connected": conectado,
            "latency_ms": latencia,
            "guilds": len(self.bot.guilds),
        }

    async def pagina_inicial(self, _request):
        status = self._status()
        texto_status = "ONLINE" if status["discord_connected"] else "INICIANDO"
        cor = "#22c55e" if status["discord_connected"] else "#f59e0b"
        html = f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Eclipse Legends</title>
  <style>
    body {{ background:#080b16; color:#e7eaf3; font-family:Segoe UI,sans-serif; display:grid;
           min-height:100vh; place-items:center; margin:0; }}
    main {{ background:#11172a; border:1px solid #27304d; border-radius:18px; padding:32px;
            width:min(430px,calc(100% - 48px)); box-shadow:0 18px 60px #0008; }}
    h1 {{ margin:0 0 8px; }}
    .status {{ color:{cor}; font-weight:700; letter-spacing:.08em; }}
    dl {{ display:grid; grid-template-columns:1fr auto; gap:10px; margin:24px 0 0; }}
    dt {{ color:#9da8c7; }} dd {{ margin:0; }}
  </style>
</head>
<body><main>
  <div class="status">{texto_status}</div>
  <h1>Eclipse Legends</h1>
  <div>Servidor local do bot</div>
  <dl>
    <dt>Discord conectado</dt><dd>{"sim" if status["discord_connected"] else "não"}</dd>
    <dt>Servidores Discord</dt><dd>{status["guilds"]}</dd>
    <dt>Latência</dt><dd>{status["latency_ms"] if status["latency_ms"] is not None else "-"} ms</dd>
  </dl>
</main></body>
</html>"""
        return web.Response(text=html, content_type="text/html")

    async def health(self, _request):
        return web.json_response(self._status())

    async def start(self):
        app = web.Application()
        app.add_routes(
            [
                web.get("/", self.pagina_inicial),
                web.get("/health", self.health),
            ]
        )
        self.runner = web.AppRunner(app, access_log=None)
        await self.runner.setup()
        try:
            site = web.TCPSite(self.runner, self.host, self.port)
            await site.start()
        except Exception:
            await self.runner.cleanup()
            self.runner = None
            raise
        print(f"Servidor local ativo em http://{self.host}:{self.port}/")

    async def stop(self):
        if self.runner is None:
            return
        await self.runner.cleanup()
        self.runner = None
        print("Servidor local encerrado.")


async def iniciar_servidor_local(bot):
    if not _env_ativo("LOCAL_SERVER_ENABLED"):
        print("Servidor local desativado por LOCAL_SERVER_ENABLED.")
        return None

    host = os.getenv("LOCAL_SERVER_HOST", "127.0.0.1").strip() or "127.0.0.1"
    servidor = LocalServer(bot, host, _porta_local())
    try:
        await servidor.start()
    except OSError as exc:
        raise RuntimeError(
            f"Nao foi possivel iniciar o servidor local em {host}:{servidor.port}. "
            "A porta pode estar em uso; altere LOCAL_SERVER_PORT no arquivo .env."
        ) from exc
    return servidor
