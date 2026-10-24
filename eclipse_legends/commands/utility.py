# Arquivo extraido de bot.py para manter o projeto organizado.
from ..core import *
from ..database import *
from ..gacha import *
from ..social import *
from ..rpg import *
from ..music import *

# =========================
# UTILIDADES E ERROS
# =========================

@bot.command(name="ping")
async def ping(ctx):
    latencia = bot.latency
    if not isinstance(latencia, (int, float)) or not math.isfinite(latencia):
        await ctx.send("🏓 Pong!")
        return
    await ctx.send(f"🏓 Pong! `{round(latencia * 1000)}ms`")


@bot.command(name="deletar")
async def deletar(ctx):
    player = pegar_player(ctx.author.id)
    if not player:
        await ctx.send("Voce nao tem personagem.")
        return
    with abrir_db() as db:
        db.execute("DELETE FROM players WHERE user_id = ?", (ctx.author.id,))
        db.execute("DELETE FROM inventario WHERE user_id = ?", (ctx.author.id,))
        db.execute("DELETE FROM quests WHERE user_id = ?", (ctx.author.id,))
        db.execute("DELETE FROM habilidades WHERE user_id = ?", (ctx.author.id,))
        db.execute("DELETE FROM guild_membros WHERE user_id = ?", (ctx.author.id,))
        db.commit()
    await ctx.send("🗑️ Seu personagem foi deletado.")


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"⏳ Aguarde `{error.retry_after:.1f}s` para usar esse comando novamente.")
        return
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ Falta informacao no comando. Use `!ajuda`.")
        return
    if isinstance(error, commands.BadArgument):
        await ctx.send("❌ Argumento invalido. Confira usuario, item ou quantidade.")
        return
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ Voce nao tem permissao para usar isso.")
        return
    await ctx.send(f"❌ Erro: `{error}`")
    raise error
