# Arquivo extraido de bot.py para manter o projeto organizado.
from ..core import *
from ..database import *
from ..gacha import *
from ..social import *
from ..rpg import *
from ..music import *

# =========================
# AJUDA E CADASTRO
# =========================

@bot.command(name="ajuda", aliases=["help", "comandos"])
async def ajuda(ctx):
    embed = embed_padrao(
        "🌑 Eclipse Legends",
        "RPG persistente de turno, exploracao, economia, guildas, PvP e boss mundial.",
        discord.Color.purple(),
    )
    embed.add_field(
        name="Personagem",
        value="`!registrar Nome classe raca origem`\n`!personagem` `!status` `!classes` `!racas` `!upar atributo qtd`\n`!inventario` `!equipar item`",
        inline=False,
    )
    embed.add_field(
        name="Aventura",
        value="`!explorar regiao` `!batalhar regiao` `!usar item` `!regioes` `!habilidades`\n`!quest` `!historia escolha` `!boss status/atacar` `!eventos`",
        inline=False,
    )
    embed.add_field(
        name="Economia e Social",
        value="`!loja` `!comprar item qtd` `!vender item qtd`\n`!mercado listar/vender/comprar` `!guilda criar/entrar/perfil/canal` `!pvp @usuario ranqueado` `!ranking`",
        inline=False,
    )
    embed.add_field(
        name="Perfil Social",
        value=(
            "`!perfil` `!perfil @usuario` `!rep @usuario ajuda`\n"
            "`!elogiar @usuario` `!rank xp/nivel/rep/mensagens/call/semanal/mensal`\n"
            "`!titulo escolher \"A Lenda\"` `!perfil editar bio texto`"
        ),
        inline=False,
    )
    embed.add_field(
        name="Gacha Anime",
        value=(
            "`!checkin` `!gacha roll 1` `!gacha roll 10`\n"
            "`!gacha perfil` `!gacha colecao` `!gacha ver nome`\n"
            "`!gacha vender nome` `!gacha vender comum` `!gacha vender todos`\n"
            "`!gacha ranking` `!adm`"
        ),
        inline=False,
    )
    embed.add_field(
        name="Musica",
        value=(
            "`!entrar` `!tocar nome/link` `!tocar playlist`\n"
            "`!fila` `!pausar` `!continuar` `!proxima` `!sair`\n"
            "`!musica` abre o painel e comandos do player"
        ),
        inline=False,
    )
    embed.add_field(
        name="Imagem IA",
        value=(
            "`!imagem prompt` gera com Stable Diffusion/Hugging Face\n"
            "`!imagem prompt --modelo flux` ou `!flux prompt` usa Flux Schnell\n"
            "`!fluxuncensored prompt` tenta usar Flux Uncensored se houver provider/endpoint\n"
            "`!imageminfo` mostra token/modelos/opcoes (`--wide`, `--vertical`, `--seed`)"
        ),
        inline=False,
    )
    await ctx.send(embed=embed)


@bot.group(name="musica", aliases=["music", "som"], invoke_without_command=True)
async def musica(ctx, *, consulta: str = None):
    if consulta:
        await tocar_consulta_musica(ctx, consulta)
        return

    player = MUSIC_PLAYERS.get(int(ctx.guild.id)) if getattr(ctx, "guild", None) else None
    if player and player.voice_client and player.voice_client.is_connected():
        player.text_channel = ctx.channel
        await atualizar_menu_musica(player)
        return

    embed = embed_padrao(
        "🎧 Eclipse Music",
        "Sistema de musica com YouTube, playlists, fila e painel interativo.",
        discord.Color.from_rgb(255, 102, 204),
    )
    embed.add_field(name="Entrar na call", value="`!entrar` ou `!musica entrar`", inline=False)
    embed.add_field(name="Tocar", value="`!tocar nome/link`\n`!tocar link_da_playlist`", inline=False)
    embed.add_field(name="Fila", value="`!fila`", inline=True)
    embed.add_field(name="Controle", value="`!pausar` `!continuar` `!proxima` `!sair`", inline=True)
    embed.set_footer(text="Eclipse Legends Music | YouTube + playlists")
    await ctx.send(embed=embed)


@musica.command(name="entrar", aliases=["join", "conectar"])
async def musica_entrar(ctx):
    player = await conectar_player_musica(ctx)
    if player:
        await ctx.send(f"🎧 Entrei em **{player.voice_client.channel.name}** e vou ficar ate a call esvaziar.")


@bot.command(name="entrar", aliases=["join", "conectar"])
async def entrar_musica(ctx):
    await musica_entrar.callback(ctx)


@musica.command(name="tocar", aliases=["play", "p"])
async def musica_tocar(ctx, *, consulta: str = None):
    if not consulta:
        await ctx.send("Use: `!tocar nome/link` ou `!tocar link_da_playlist`.")
        return
    await tocar_consulta_musica(ctx, consulta)


@bot.command(name="tocar", aliases=["play", "p"])
async def tocar(ctx, *, consulta: str = None):
    await musica_tocar.callback(ctx, consulta=consulta)


@musica.command(name="playlist", aliases=["pl"])
async def musica_playlist(ctx, *, url: str = None):
    if not url:
        await ctx.send("Use: `!playlist link_da_playlist`.")
        return
    await tocar_consulta_musica(ctx, url)


@bot.command(name="playlist", aliases=["pl"])
async def playlist(ctx, *, url: str = None):
    await musica_playlist.callback(ctx, url=url)


@musica.command(name="fila", aliases=["queue", "q"])
async def musica_fila(ctx):
    player = await exigir_player_musica_ativo(ctx)
    if not player:
        return
    player.text_channel = ctx.channel
    await atualizar_menu_musica(player)


@bot.command(name="fila", aliases=["queue", "q"])
async def fila(ctx):
    await musica_fila.callback(ctx)


@musica.command(name="pausar", aliases=["pause"])
async def musica_pausar(ctx):
    player = await exigir_player_musica_ativo(ctx)
    if not player:
        return
    vc = player.voice_client
    if not vc.is_playing():
        await ctx.send("Nao tem musica tocando agora.")
        return
    vc.pause()
    player.last_status = f"Musica pausada por {ctx.author.display_name}."
    player.text_channel = ctx.channel
    await atualizar_menu_musica(player)
    await reagir_comando(ctx, "⏸️")


@bot.command(name="pausar", aliases=["pause"])
async def pausar(ctx):
    await musica_pausar.callback(ctx)


@musica.command(name="continuar", aliases=["resume", "retomar"])
async def musica_continuar(ctx):
    player = await exigir_player_musica_ativo(ctx)
    if not player:
        return
    vc = player.voice_client
    if not vc.is_paused():
        await ctx.send("A musica nao esta pausada.")
        return
    vc.resume()
    player.last_status = f"Musica retomada por {ctx.author.display_name}."
    player.text_channel = ctx.channel
    await atualizar_menu_musica(player)
    await reagir_comando(ctx, "▶️")


@bot.command(name="continuar", aliases=["resume", "retomar"])
async def continuar(ctx):
    await musica_continuar.callback(ctx)


@musica.command(name="proxima", aliases=["skip", "pular", "next"])
async def musica_proxima(ctx):
    player = await exigir_player_musica_ativo(ctx)
    if not player:
        return
    vc = player.voice_client
    player.last_status = f"Pulando para a proxima a pedido de {ctx.author.display_name}."
    player.text_channel = ctx.channel
    if vc.is_playing() or vc.is_paused():
        vc.stop()
    else:
        await iniciar_proxima_musica(ctx.guild.id)
    await atualizar_menu_musica(player)
    await reagir_comando(ctx, "⏭️")


@bot.command(name="proxima", aliases=["skip", "pular", "next"])
async def proxima(ctx):
    await musica_proxima.callback(ctx)


@musica.command(name="sair", aliases=["leave", "desconectar", "finalizar", "encerrar", "stop"])
async def musica_sair(ctx):
    player = await exigir_player_musica_ativo(ctx)
    if not player:
        return
    await finalizar_player_musica(ctx.guild.id, f"Sessao finalizada por {ctx.author.display_name}.", desconectar=True)
    await reagir_comando(ctx, "⏹️")


@bot.command(name="sair", aliases=["leave", "desconectar", "finalizar", "encerrar", "stop"])
async def sair(ctx):
    await musica_sair.callback(ctx)


@bot.group(name="rpg", invoke_without_command=True)
async def rpg(ctx):
    await ajuda.callback(ctx)


@rpg.command(name="ajuda")
async def rpg_ajuda(ctx):
    await ajuda.callback(ctx)


@bot.command(name="classes")
async def classes(ctx):
    embed = embed_padrao("🧙 Classes", "Use `!registrar Nome classe raca origem`.", discord.Color.blurple())
    for key, info in CLASSES_RPG.items():
        embed.add_field(
            name=f"{info['emoji']} {info['nome']}",
            value=f"{info['descricao']}\nHP `{info['hp']}` Mana `{info['mana']}` For `{info['forca']}` Def `{info['defesa']}` Agi `{info['agilidade']}` Int `{info['inteligencia']}` Sorte `{info['sorte']}`",
            inline=False,
        )
    await ctx.send(embed=embed)


@bot.command(name="racas", aliases=["raças"])
async def racas(ctx):
    embed = embed_padrao("🧬 Racas", "Cada raca altera seus atributos iniciais.", discord.Color.green())
    for key, info in RACAS_RPG.items():
        embed.add_field(
            name=f"{info['emoji']} {info['nome']}",
            value=f"{info['descricao']} Pontos extras `{info['pontos']}`",
            inline=False,
        )
    await ctx.send(embed=embed)


@bot.command(name="origens")
async def origens(ctx):
    linhas = [f"`{key}` - {texto}" for key, texto in ORIGENS_RPG.items()]
    await ctx.send(embed=embed_padrao("📜 Origens", "\n".join(linhas), discord.Color.dark_gold()))


@bot.command(name="registrar", aliases=["register"])
async def registrar(ctx, nome: str = None, classe: str = None, raca: str = "humano", *, origem: str = "exilado"):
    if not nome or not classe:
        await ctx.send("Use: `!registrar Yukki assassino humano exilado` | Veja `!classes`, `!racas` e `!origens`.")
        return

    classe_key = normalizar(classe)
    raca_key = normalizar(raca)
    origem_key = normalizar(origem.split()[0]) if origem else "exilado"
    origem_texto = origem if origem_key not in ORIGENS_RPG else origem_key

    if classe_key not in CLASSES_RPG:
        await ctx.send("Classe invalida. Use `!classes`.")
        return
    if raca_key not in RACAS_RPG:
        await ctx.send("Raca invalida. Use `!racas`.")
        return
    if pegar_player(ctx.author.id):
        await ctx.send("Voce ja tem um personagem. Use `!personagem`.")
        return

    classe_info = CLASSES_RPG[classe_key]
    raca_info = RACAS_RPG[raca_key]
    hp_max = max(50, classe_info["hp"] + raca_info["hp"])
    mana_max = max(10, classe_info["mana"] + raca_info["mana"])
    forca = max(1, classe_info["forca"] + raca_info["forca"])
    defesa = max(1, classe_info["defesa"] + raca_info["defesa"])
    agilidade = max(1, classe_info["agilidade"] + raca_info["agilidade"])
    inteligencia = max(1, classe_info["inteligencia"] + raca_info["inteligencia"])
    sorte = max(1, classe_info["sorte"] + raca_info["sorte"])
    pontos = 3 + raca_info["pontos"]

    with abrir_db() as db:
        db.execute(
            """
            INSERT INTO players (
                user_id, nome, classe, raca, origem, nivel, xp, ouro, hp, hp_max,
                mana, mana_max, atk, defesa, forca, agilidade, inteligencia, sorte,
                pontos, pocao, energia, energia_max, ultima_daily, arma, armadura,
                monstros_derrotados, rank, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, 1, 0, 120, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 3, 12, 12, 'nunca', 'Nenhuma', 'Nenhuma', 0, 'bronze', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (
                ctx.author.id,
                nome[:32],
                classe_key,
                raca_key,
                origem_texto[:120],
                hp_max,
                hp_max,
                mana_max,
                mana_max,
                forca * 2 + inteligencia,
                defesa,
                forca,
                agilidade,
                inteligencia,
                sorte,
                pontos,
            ),
        )
        db.commit()

    adicionar_item(ctx.author.id, "pocao_pequena", 2)
    desbloquear_habilidades(ctx.author.id, classe_key, 1)

    embed = embed_padrao("✅ Personagem Criado", cor=discord.Color.green())
    embed.add_field(name="Nome", value=nome[:32], inline=True)
    embed.add_field(name="Classe", value=formatar_nome_classe(classe_key), inline=True)
    embed.add_field(name="Raca", value=formatar_nome_raca(raca_key), inline=True)
    embed.add_field(name="Origem", value=origem_texto, inline=False)
    embed.add_field(name="Pontos livres", value=str(pontos), inline=True)
    embed.add_field(name="Proximo passo", value="Use `!personagem`, `!upar`, `!explorar floresta` e `!batalhar floresta`.", inline=False)
    await ctx.send(embed=embed)


@rpg.command(name="registrar")
async def rpg_registrar(ctx, nome: str = None, classe: str = None, raca: str = "humano", *, origem: str = "exilado"):
    await registrar.callback(ctx, nome, classe, raca, origem=origem)


@bot.command(name="personagem", aliases=["rpgperfil", "perfilrpg"])
async def personagem(ctx, membro: discord.Member = None):
    membro = membro or ctx.author
    player = pegar_player(membro.id)
    if not player:
        await ctx.send("Esse usuario ainda nao tem personagem.")
        return

    stats = stats_efetivos(player)
    hp = min(int(player["hp"]), stats["hp_max"])
    mana = min(int(player["mana"]), stats["mana_max"])
    embed = embed_padrao(f"👤 {player['nome']}", cor=discord.Color.gold())
    embed.set_thumbnail(url=membro.display_avatar.url)
    embed.add_field(name="Classe", value=formatar_nome_classe(player["classe"]), inline=True)
    embed.add_field(name="Raca", value=formatar_nome_raca(player["raca"]), inline=True)
    embed.add_field(name="Nivel", value=f"{player['nivel']} | XP {player['xp']}/{xp_necessario(player['nivel'])}", inline=True)
    embed.add_field(name="HP", value=f"{hp}/{stats['hp_max']}\n{barra(hp, stats['hp_max'])}", inline=False)
    embed.add_field(name="Mana", value=f"{mana}/{stats['mana_max']}\n{barra(mana, stats['mana_max'])}", inline=False)
    embed.add_field(name="Energia", value=f"{player['energia']}/{player['energia_max']}\n{barra(player['energia'], player['energia_max'])}", inline=False)
    embed.add_field(name="Atributos", value=f"For `{stats['forca']}` Def `{stats['defesa']}` Agi `{stats['agilidade']}` Int `{stats['inteligencia']}` Sorte `{stats['sorte']}`", inline=False)
    embed.add_field(name="Ouro", value=f"💰 {player['ouro']}", inline=True)
    embed.add_field(name="Pontos", value=str(player["pontos"]), inline=True)
    embed.add_field(name="PvP", value=f"{player['rank']} | {player['pvp_vitorias']}V/{player['pvp_derrotas']}D", inline=True)
    embed.add_field(name="Equipado", value=f"Arma: `{player['arma']}`\nArmadura: `{player['armadura']}`", inline=False)
    embed.add_field(name="Evolucao", value=f"Classe avancada: `{player['classe_avancada']}`\nTransformacao: `{player['transformacao']}`\nReencarnacoes: `{player['reincarnacoes']}`", inline=False)
    await ctx.send(embed=embed)


@bot.command(name="status")
async def status(ctx):
    await personagem.callback(ctx, ctx.author)


@rpg.command(name="perfil")
async def rpg_perfil(ctx, membro: discord.Member = None):
    await personagem.callback(ctx, membro or ctx.author)


@rpg.command(name="status")
async def rpg_status(ctx):
    await personagem.callback(ctx, ctx.author)


@bot.command(name="upar", aliases=["atributo"])
async def upar(ctx, atributo: str = None, quantidade: int = 1):
    player = pegar_player(ctx.author.id)
    if not player:
        await ctx.send(exigir_player_msg())
        return
    if not atributo:
        await ctx.send("Use: `!upar forca 3` | atributos: `forca`, `defesa`, `agilidade`, `inteligencia`, `sorte`, `hp`, `mana`.")
        return

    atributo = normalizar(atributo)
    aliases = {"int": "inteligencia", "agi": "agilidade", "def": "defesa", "vida": "hp", "mana_max": "mana"}
    atributo = aliases.get(atributo, atributo)
    if atributo not in ("forca", "defesa", "agilidade", "inteligencia", "sorte", "hp", "mana"):
        await ctx.send("Atributo invalido. Use `forca`, `defesa`, `agilidade`, `inteligencia`, `sorte`, `hp` ou `mana`.")
        return
    quantidade = max(1, min(50, int(quantidade)))
    if int(player["pontos"]) < quantidade:
        await ctx.send(f"Voce so tem `{player['pontos']}` pontos livres.")
        return

    campos = {"pontos": int(player["pontos"]) - quantidade}
    if atributo == "hp":
        campos["hp_max"] = int(player["hp_max"]) + quantidade * 10
        campos["hp"] = int(player["hp"]) + quantidade * 10
    elif atributo == "mana":
        campos["mana_max"] = int(player["mana_max"]) + quantidade * 8
        campos["mana"] = int(player["mana"]) + quantidade * 8
    else:
        campos[atributo] = int(player[atributo]) + quantidade
        if atributo in ("forca", "inteligencia"):
            campos["atk"] = int(player["atk"] or 0) + quantidade * 2
    salvar_player(ctx.author.id, **campos)
    await ctx.send(f"✅ `{quantidade}` ponto(s) aplicado(s) em **{atributo}**.")


