# Arquivo extraido de bot.py para manter o projeto organizado.
from .core import *
from .database import *
from .gacha import *
from .social import *
from .music import *

# =========================
# EVENTOS
# =========================

@bot.event
async def on_ready():
    criar_db()
    await asyncio.to_thread(carregar_catalogo_gacha, False)
    await bot.change_presence(activity=discord.Game(name="Eclipse Legends | !ajuda"))
    print(f"Bot conectado como {bot.user}")


@bot.event
async def on_message(message):
    if getattr(message.author, "bot", False):
        return

    if getattr(message, "guild", None) and not str(getattr(message, "content", "")).startswith(PREFIXO):
        if not usuario_mutado_social(message.author) and not canal_ignorado_social(message.channel):
            user = pegar_social_user(message.author.id)
            xp, token = calcular_xp_mensagem(message, user)
            repeated_count = int(user["repeated_count"] or 0)
            if token == "repetida":
                repeated_count += 1
            elif token not in ("curta", "cooldown", "limite"):
                repeated_count = 0

            campos = {
                "mensagens": int(user["mensagens"]) + (1 if token not in ("curta", "repetida") else 0),
                "last_message_at": datetime.utcnow().isoformat(timespec="seconds"),
                "repeated_count": repeated_count,
            }
            if token not in ("curta", "cooldown", "limite", "repetida"):
                campos["last_message_hash"] = token
            salvar_social_user(message.author.id, **campos)

            mensagens_level = await adicionar_xp_social(message.author, xp, "mensagem")
            if mensagens_level:
                try:
                    await message.channel.send("\n".join(mensagens_level[:2]))
                except (discord.Forbidden, discord.HTTPException):
                    pass
            checar_conquistas_social(message.author.id)

    await bot.process_commands(message)


@bot.event
async def on_reaction_add(reaction, user):
    if getattr(user, "bot", False):
        return
    member = user if isinstance(user, discord.Member) else None
    if not member and getattr(reaction.message, "guild", None):
        member = reaction.message.guild.get_member(user.id)
    if not member or usuario_mutado_social(member):
        return
    await adicionar_xp_social(member, random.randint(2, 5), "reacao")


@bot.event
async def on_voice_state_update(member, before, after):
    if bot.user and int(member.id) == int(bot.user.id):
        player = MUSIC_PLAYERS.get(int(member.guild.id))
        if player and after.channel is None:
            player.voice_client = None
            await finalizar_player_musica(
                member.guild.id,
                "Fui desconectado da call. Sessao encerrada.",
                desconectar=False,
            )
        elif player:
            player.voice_client = getattr(member.guild, "voice_client", None)
            player.last_status = f"Continuo conectado em {after.channel.name}."
            await atualizar_menu_musica(player)
        return

    if getattr(member, "bot", False):
        return
    if before.channel is None and after.channel is not None:
        with abrir_db() as db:
            db.execute(
                """
                INSERT OR REPLACE INTO social_voice_sessions(user_id, guild_id, channel_id, started_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    int(member.id),
                    int(getattr(member.guild, "id", 0)),
                    int(getattr(after.channel, "id", 0)),
                    datetime.utcnow().isoformat(timespec="seconds"),
                ),
            )
        pegar_social_user(member.id)
        await verificar_auto_saida_musica(member.guild)
        return

    if before.channel is not None and after.channel is None:
        with abrir_db() as db:
            sessao = db.execute("SELECT started_at FROM social_voice_sessions WHERE user_id = ?", (int(member.id),)).fetchone()
            db.execute("DELETE FROM social_voice_sessions WHERE user_id = ?", (int(member.id),))
        if not sessao:
            await verificar_auto_saida_musica(member.guild)
            return
        try:
            inicio = datetime.fromisoformat(sessao["started_at"])
        except ValueError:
            await verificar_auto_saida_musica(member.guild)
            return
        segundos = max(0, int((datetime.utcnow() - inicio).total_seconds()))
        if segundos < 60:
            await verificar_auto_saida_musica(member.guild)
            return
        minutos = segundos // 60
        xp = min(300, minutos * 5)
        user = pegar_social_user(member.id)
        salvar_social_user(member.id, call_seconds=int(user["call_seconds"]) + segundos)
        await adicionar_xp_social(member, xp, "call")
        checar_conquistas_social(member.id)
        await verificar_auto_saida_musica(member.guild)
        return

    if before.channel is not None and after.channel is not None and before.channel != after.channel:
        with abrir_db() as db:
            sessao = db.execute("SELECT started_at FROM social_voice_sessions WHERE user_id = ?", (int(member.id),)).fetchone()
            db.execute(
                """
                INSERT OR REPLACE INTO social_voice_sessions(user_id, guild_id, channel_id, started_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    int(member.id),
                    int(getattr(member.guild, "id", 0)),
                    int(getattr(after.channel, "id", 0)),
                    datetime.utcnow().isoformat(timespec="seconds"),
                ),
            )
        if sessao:
            try:
                inicio = datetime.fromisoformat(sessao["started_at"])
                segundos = max(0, int((datetime.utcnow() - inicio).total_seconds()))
                if segundos >= 60:
                    user = pegar_social_user(member.id)
                    salvar_social_user(member.id, call_seconds=int(user["call_seconds"]) + segundos)
                    await adicionar_xp_social(member, min(300, (segundos // 60) * 5), "call")
                    checar_conquistas_social(member.id)
            except ValueError:
                pass
        await verificar_auto_saida_musica(member.guild)
