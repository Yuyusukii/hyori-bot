# Arquivo extraido de bot.py para manter o projeto organizado.
from .core import *

# =========================
# SISTEMA DE MUSICA
# =========================

@dataclass
class MusicTrack:
    title: str
    webpage_url: str
    requester_id: int
    requester_name: str
    duration: int = 0
    thumbnail: str = ""
    uploader: str = ""
    stream_url: str = ""


class MusicPlayer:
    def __init__(self, guild_id):
        self.guild_id = int(guild_id)
        self.queue = deque()
        self.current = None
        self.voice_client = None
        self.text_channel = None
        self.control_message = None
        self.last_status = "Aguardando musicas."
        self.closed = False
        self.lock = asyncio.Lock()


def pegar_music_player(guild_id):
    guild_id = int(guild_id)
    if guild_id not in MUSIC_PLAYERS:
        MUSIC_PLAYERS[guild_id] = MusicPlayer(guild_id)
    return MUSIC_PLAYERS[guild_id]


def music_deps_status():
    if yt_dlp is None:
        return False, "A dependencia `yt-dlp` nao esta instalada. Rode o `.bat` novamente para instalar."
    if davey is None:
        return False, "A dependencia `davey` nao esta instalada. Rode o `.bat` novamente para instalar voz no Discord."
    if imageio_ffmpeg is None and not shutil.which("ffmpeg"):
        return False, "FFmpeg nao foi encontrado. Rode o `.bat` novamente para instalar `imageio-ffmpeg`."
    return True, ""


def ffmpeg_executavel():
    if imageio_ffmpeg is not None:
        try:
            return imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            pass
    return shutil.which("ffmpeg") or "ffmpeg"


def parece_url(texto):
    texto = str(texto or "").strip().lower()
    return texto.startswith("http://") or texto.startswith("https://")


def formatar_duracao(segundos):
    segundos = int(segundos or 0)
    if segundos <= 0:
        return "ao vivo"
    horas, resto = divmod(segundos, 3600)
    minutos, secs = divmod(resto, 60)
    if horas:
        return f"{horas}:{minutos:02}:{secs:02}"
    return f"{minutos}:{secs:02}"


def url_youtube_entry(entry):
    if not entry:
        return None
    url = entry.get("webpage_url") or entry.get("url") or entry.get("id")
    if not url:
        return None
    url = str(url)
    if parece_url(url):
        return url
    if len(url) == 11 and "/" not in url:
        return f"https://www.youtube.com/watch?v={url}"
    return url


def extrair_info_musica(entrada, flat=False):
    if yt_dlp is None:
        raise RuntimeError("yt-dlp nao instalado")
    opts = dict(MUSIC_YTDL_OPTIONS)
    opts["extract_flat"] = bool(flat)
    with yt_dlp.YoutubeDL(opts) as ydl:
        return ydl.extract_info(entrada, download=False)


def track_de_entry(entry, requester):
    url = url_youtube_entry(entry)
    if not url:
        return None
    return MusicTrack(
        title=str(entry.get("title") or "Musica sem nome"),
        webpage_url=url,
        requester_id=int(requester.id),
        requester_name=str(getattr(requester, "display_name", requester)),
        duration=int(entry.get("duration") or 0),
        thumbnail=str(entry.get("thumbnail") or ""),
        uploader=str(entry.get("uploader") or entry.get("channel") or ""),
    )


async def buscar_tracks_musica(consulta, requester):
    consulta = str(consulta or "").strip()
    if not consulta:
        raise ValueError("Informe o nome ou link da musica.")

    entrada = consulta if parece_url(consulta) else f"ytsearch1:{consulta}"
    info = await asyncio.to_thread(extrair_info_musica, entrada, True)
    if not info:
        raise ValueError("Nao encontrei nada para essa busca.")

    entries = [entry for entry in (info.get("entries") or []) if entry]
    tracks = []
    if entries:
        for entry in entries[:MUSIC_MAX_PLAYLIST_ADD]:
            track = track_de_entry(entry, requester)
            if track:
                tracks.append(track)
    else:
        track = track_de_entry(info, requester)
        if track:
            tracks.append(track)

    if not tracks:
        raise ValueError("Nao consegui carregar nenhuma musica dessa busca.")
    return tracks, info


def escolher_stream_audio(info):
    if info.get("url"):
        return info["url"]
    formatos = info.get("formats") or []
    candidatos = [
        fmt for fmt in formatos
        if fmt.get("url") and fmt.get("acodec") != "none" and fmt.get("vcodec") == "none"
    ]
    if not candidatos:
        candidatos = [fmt for fmt in formatos if fmt.get("url") and fmt.get("acodec") != "none"]
    if not candidatos:
        return None
    candidatos.sort(key=lambda fmt: float(fmt.get("abr") or fmt.get("tbr") or 0), reverse=True)
    return candidatos[0]["url"]


async def preparar_stream_track(track):
    info = await asyncio.to_thread(extrair_info_musica, track.webpage_url, False)
    if not info:
        raise ValueError("Nao consegui abrir essa musica.")
    entries = [entry for entry in (info.get("entries") or []) if entry]
    if entries:
        info = entries[0]
    stream = escolher_stream_audio(info)
    if not stream:
        raise ValueError("Nao encontrei um audio valido para essa musica.")

    track.stream_url = stream
    track.title = str(info.get("title") or track.title)
    track.webpage_url = str(info.get("webpage_url") or track.webpage_url)
    track.duration = int(info.get("duration") or track.duration or 0)
    track.thumbnail = str(info.get("thumbnail") or track.thumbnail or "")
    track.uploader = str(info.get("uploader") or info.get("channel") or track.uploader or "")
    return track


def embed_menu_musica(player, guild=None, encerrado=False):
    cor = discord.Color.from_rgb(255, 102, 204)
    embed = embed_padrao("🎧 Eclipse Music", None, cor)
    embed.set_author(name="Painel de Musica", icon_url=getattr(bot.user.display_avatar, "url", None) if bot.user else None)

    vc = player.voice_client
    canal = getattr(vc, "channel", None)
    status = player.last_status or "Aguardando."
    if encerrado:
        embed.description = "```Sessao encerrada.```"
        embed.add_field(name="Status", value=status, inline=False)
        embed.set_footer(text="Eclipse Legends Music | Finalizado")
        return embed

    if player.current:
        musica = player.current
        titulo = discord.utils.escape_markdown(musica.title)
        embed.description = (
            f"**Tocando agora**\n"
            f"[{titulo}]({musica.webpage_url})\n\n"
            f"```{status}```"
        )
        embed.add_field(name="Duracao", value=f"`{formatar_duracao(musica.duration)}`", inline=True)
        embed.add_field(name="Pedido por", value=f"`{musica.requester_name}`", inline=True)
        embed.add_field(name="Na fila", value=f"`{len(player.queue)}` musica(s)", inline=True)
        if musica.uploader:
            embed.add_field(name="Canal", value=f"`{musica.uploader[:40]}`", inline=True)
        if musica.thumbnail:
            embed.set_thumbnail(url=musica.thumbnail)
    else:
        embed.description = (
            "**Nenhuma musica tocando agora.**\n"
            "Use `!tocar nome/link` ou `!tocar link_da_playlist` para comecar.\n\n"
            f"```{status}```"
        )
        embed.add_field(name="Na fila", value=f"`{len(player.queue)}` musica(s)", inline=True)

    if canal:
        embed.add_field(name="Call", value=f"`{canal.name}`", inline=True)

    if player.queue:
        proximas = []
        for i, track in enumerate(list(player.queue)[:5], 1):
            titulo = discord.utils.escape_markdown(track.title)
            proximas.append(f"`{i}.` {titulo[:70]}")
        if len(player.queue) > 5:
            proximas.append(f"`+{len(player.queue) - 5}` musicas na fila")
        embed.add_field(name="Proximas", value="\n".join(proximas), inline=False)

    embed.set_footer(text="Eclipse Legends Music | Pausar • Proxima • Finalizar")
    return embed


class MusicControlView(discord.ui.View):
    def __init__(self, guild_id, encerrado=False):
        super().__init__(timeout=None)
        self.guild_id = int(guild_id)
        player = MUSIC_PLAYERS.get(self.guild_id)
        vc = getattr(player, "voice_client", None)

        if vc and vc.is_paused():
            self.pausar_ou_continuar.label = "Continuar"
            self.pausar_ou_continuar.emoji = "▶️"
            self.pausar_ou_continuar.style = discord.ButtonStyle.success
        else:
            self.pausar_ou_continuar.label = "Pausar"
            self.pausar_ou_continuar.emoji = "⏸️"
            self.pausar_ou_continuar.style = discord.ButtonStyle.primary

        if encerrado or not player:
            for item in self.children:
                item.disabled = True
        else:
            self.proxima.disabled = not bool(player.current or player.queue)

    async def interaction_check(self, interaction):
        player = MUSIC_PLAYERS.get(self.guild_id)
        vc = getattr(player, "voice_client", None)
        canal = getattr(vc, "channel", None)
        if not player or not vc or not vc.is_connected() or not canal:
            await interaction.response.send_message("O player de musica nao esta ativo.", ephemeral=True)
            return False
        if getattr(interaction.user.guild_permissions, "manage_guild", False):
            return True
        user_voice = getattr(interaction.user, "voice", None)
        if not user_voice or user_voice.channel != canal:
            await interaction.response.send_message("Entre na mesma call do bot para usar os controles.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Pausar", emoji="⏸️", style=discord.ButtonStyle.primary)
    async def pausar_ou_continuar(self, interaction, button):
        player = MUSIC_PLAYERS.get(self.guild_id)
        vc = player.voice_client
        if vc.is_paused():
            vc.resume()
            player.last_status = f"Musica retomada por {interaction.user.display_name}."
        elif vc.is_playing():
            vc.pause()
            player.last_status = f"Musica pausada por {interaction.user.display_name}."
        else:
            player.last_status = "Nao ha musica tocando agora."
        await interaction.response.defer()
        await atualizar_menu_musica(player)

    @discord.ui.button(label="Proxima", emoji="⏭️", style=discord.ButtonStyle.secondary)
    async def proxima(self, interaction, button):
        player = MUSIC_PLAYERS.get(self.guild_id)
        vc = player.voice_client
        player.last_status = f"Pulando para a proxima a pedido de {interaction.user.display_name}."
        await interaction.response.defer()
        if vc.is_playing() or vc.is_paused():
            vc.stop()
        else:
            await iniciar_proxima_musica(self.guild_id)
        await atualizar_menu_musica(player)

    @discord.ui.button(label="Finalizar", emoji="⏹️", style=discord.ButtonStyle.danger)
    async def finalizar(self, interaction, button):
        await interaction.response.defer()
        await finalizar_player_musica(
            self.guild_id,
            f"Sessao finalizada por {interaction.user.display_name}.",
            desconectar=True,
        )


async def atualizar_menu_musica(player, encerrado=False):
    if not player or not player.text_channel:
        return
    embed = embed_menu_musica(player, getattr(player.text_channel, "guild", None), encerrado=encerrado)
    view = MusicControlView(player.guild_id, encerrado=encerrado)
    try:
        if player.control_message:
            await player.control_message.edit(embed=embed, view=view)
        else:
            player.control_message = await player.text_channel.send(embed=embed, view=view)
    except (discord.NotFound, discord.Forbidden):
        player.control_message = None
    except discord.HTTPException:
        try:
            player.control_message = await player.text_channel.send(embed=embed, view=view)
        except discord.HTTPException:
            pass


async def conectar_player_musica(ctx):
    ok, erro = music_deps_status()
    if not ok:
        await ctx.send(f"❌ {erro}")
        return None
    if not getattr(ctx, "guild", None):
        await ctx.send("Esse comando so funciona dentro de um servidor.")
        return None
    voice_state = getattr(ctx.author, "voice", None)
    canal = getattr(voice_state, "channel", None)
    if not canal:
        await ctx.send("Entre em uma call primeiro, ai eu entro com voce.")
        return None

    player = pegar_music_player(ctx.guild.id)
    player.closed = False
    player.text_channel = ctx.channel
    vc = getattr(ctx.guild, "voice_client", None)
    try:
        if vc and vc.is_connected():
            if vc.channel != canal:
                await vc.move_to(canal)
            player.voice_client = vc
        else:
            player.voice_client = await canal.connect(self_deaf=True)
    except RuntimeError as exc:
        await ctx.send(f"❌ Nao consegui ativar voz: `{exc}`. Rode o `.bat` novamente para instalar as dependencias.")
        return None
    except discord.ClientException:
        player.voice_client = getattr(ctx.guild, "voice_client", None)
    except (discord.Forbidden, discord.HTTPException) as exc:
        await ctx.send(f"❌ Nao consegui entrar na call: `{exc}`")
        return None

    player.last_status = f"Conectado em {canal.name}. Vou ficar ate a call esvaziar ou me desconectarem."
    await atualizar_menu_musica(player)
    return player


async def tocar_consulta_musica(ctx, consulta):
    player = await conectar_player_musica(ctx)
    if not player:
        return

    async with ctx.typing():
        try:
            tracks, info = await buscar_tracks_musica(consulta, ctx.author)
        except Exception as exc:
            await ctx.send(f"❌ Nao consegui carregar essa musica/playlist: `{exc}`")
            return

    espaco = max(0, MUSIC_MAX_QUEUE - len(player.queue) - (1 if player.current else 0))
    if espaco <= 0:
        await ctx.send(f"Fila cheia. Limite atual: `{MUSIC_MAX_QUEUE}` musicas.")
        return
    tracks = tracks[:espaco]
    player.queue.extend(tracks)

    tipo = "playlist" if len(tracks) > 1 else "musica"
    origem = info.get("title") or consulta
    player.last_status = f"Adicionado {len(tracks)} {tipo}(s) de {origem}."
    await atualizar_menu_musica(player)

    vc = player.voice_client
    if vc and vc.is_connected() and not vc.is_playing() and not vc.is_paused():
        await iniciar_proxima_musica(ctx.guild.id)


async def iniciar_proxima_musica(guild_id):
    player = MUSIC_PLAYERS.get(int(guild_id))
    if not player or player.closed:
        return

    async with player.lock:
        vc = player.voice_client
        if not vc or not vc.is_connected():
            return
        if vc.is_playing() or vc.is_paused():
            return
        if not player.queue:
            player.current = None
            player.last_status = "Fila vazia. Continuo na call aguardando novas musicas."
            await atualizar_menu_musica(player)
            return

        track = player.queue.popleft()
        player.current = track
        player.last_status = "Carregando audio do YouTube..."
        await atualizar_menu_musica(player)

        try:
            await preparar_stream_track(track)
            source = discord.FFmpegPCMAudio(
                track.stream_url,
                executable=ffmpeg_executavel(),
                before_options=MUSIC_FFMPEG_BEFORE_OPTIONS,
                options=MUSIC_FFMPEG_OPTIONS,
            )
            vc.play(
                source,
                after=lambda error: bot.loop.call_soon_threadsafe(
                    asyncio.create_task,
                    musica_finalizada(int(guild_id), error),
                ),
            )
            player.last_status = "Tocando agora."
            await atualizar_menu_musica(player)
        except Exception as exc:
            player.last_status = f"Falhei nessa musica e vou tentar a proxima: {exc}"
            if player.text_channel:
                try:
                    await player.text_channel.send(f"⚠️ Pulei **{track.title}**: `{exc}`")
                except discord.HTTPException:
                    pass
            player.current = None
            bot.loop.create_task(iniciar_proxima_musica(guild_id))


async def musica_finalizada(guild_id, error=None):
    player = MUSIC_PLAYERS.get(int(guild_id))
    if not player or player.closed:
        return
    if error and player.text_channel:
        try:
            await player.text_channel.send(f"⚠️ Erro no player: `{error}`")
        except discord.HTTPException:
            pass
    player.current = None
    await iniciar_proxima_musica(guild_id)


async def finalizar_player_musica(guild_id, motivo="Sessao de musica finalizada.", desconectar=True):
    player = MUSIC_PLAYERS.get(int(guild_id))
    if not player:
        return
    player.closed = True
    player.queue.clear()
    player.current = None
    player.last_status = motivo
    vc = player.voice_client
    if vc:
        try:
            if vc.is_playing() or vc.is_paused():
                vc.stop()
        except Exception:
            pass
        if desconectar and vc.is_connected():
            try:
                await vc.disconnect(force=True)
            except discord.HTTPException:
                pass
    await atualizar_menu_musica(player, encerrado=True)
    MUSIC_PLAYERS.pop(int(guild_id), None)


async def verificar_auto_saida_musica(guild):
    if not guild:
        return
    player = MUSIC_PLAYERS.get(int(guild.id))
    if not player or player.closed:
        return
    vc = player.voice_client or getattr(guild, "voice_client", None)
    canal = getattr(vc, "channel", None)
    if not vc or not vc.is_connected() or not canal:
        return
    humanos = [m for m in canal.members if not getattr(m, "bot", False)]
    if not humanos:
        await finalizar_player_musica(
            guild.id,
            "Todo mundo saiu da call. Desconectei automaticamente.",
            desconectar=True,
        )


async def exigir_player_musica_ativo(ctx):
    if not getattr(ctx, "guild", None):
        await ctx.send("Esse comando so funciona dentro de um servidor.")
        return None
    player = MUSIC_PLAYERS.get(int(ctx.guild.id))
    vc = getattr(player, "voice_client", None) if player else None
    if not player or not vc or not vc.is_connected():
        await ctx.send("Nao existe uma sessao de musica ativa. Use `!tocar nome/link`.")
        return None
    return player


async def reagir_comando(ctx, emoji):
    try:
        await ctx.message.add_reaction(emoji)
    except (discord.Forbidden, discord.HTTPException, AttributeError):
        pass
