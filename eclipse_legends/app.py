from .core import bot, carregar_env, os
from .database import criar_db

_MODULES_LOADED = False


def carregar_modulos():
    global _MODULES_LOADED
    if _MODULES_LOADED:
        return

    from . import events  # noqa: F401
    from .commands import help_rpg  # noqa: F401
    from .commands import economy  # noqa: F401
    from .commands import adventure  # noqa: F401
    from .commands import quests  # noqa: F401
    from .commands import guilds  # noqa: F401
    from .commands import social  # noqa: F401
    from .commands import gacha_admin  # noqa: F401
    from .commands import images  # noqa: F401
    from .commands import utility  # noqa: F401

    _MODULES_LOADED = True


carregar_modulos()


def main():
    criar_db()
    token = os.getenv("DISCORD_TOKEN") or os.getenv("TOKEN")
    if not token or token.strip().lower().startswith("coloque"):
        raise SystemExit(
            "Token nao encontrado. Crie um arquivo .env com DISCORD_TOKEN=seu_token_do_discord."
        )
    bot.run(token)
