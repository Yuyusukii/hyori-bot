# Arquivo extraido de bot.py para manter o projeto organizado.
from ..core import *
from ..database import *
from ..gacha import *
from ..social import *
from ..rpg import *
from ..music import *

# =========================
# EXPLORACAO E COMBATE
# =========================

@bot.command(name="regioes", aliases=["regions"])
async def regioes(ctx):
    linhas = []
    for key, info in REGIOES.items():
        linhas.append(f"`{key}` {info['emoji']} **{info['nome']}** | nivel recomendado `{info['nivel']}+` | dificuldade `{info['dificuldade']}x`")
    await ctx.send(embed=embed_padrao("🧭 Regioes", "\n".join(linhas), discord.Color.dark_green()))


@bot.command(name="eventos", aliases=["evento"])
async def eventos(ctx):
    evento = evento_global()
    await ctx.send(embed=embed_padrao("🌪️ Evento Dinamico", f"Agora: **{evento['nome']}**\nBonus ouro `{evento['bonus_ouro']}x` | bonus XP `{evento['bonus_xp']}x` | bonus drop `{int(evento['bonus_drop'] * 100)}%`", discord.Color.magenta()))


@bot.command(name="habilidades", aliases=["skills"])
async def habilidades(ctx, membro: discord.Member = None):
    membro = membro or ctx.author
    player = pegar_player(membro.id)
    if not player:
        await ctx.send("Esse usuario ainda nao tem personagem.")
        return
    linhas = []
    for skill in HABILIDADES.get(normalizar(player["classe"]), []):
        status_skill = "✅" if int(player["nivel"]) >= int(skill["nivel"]) else "🔒"
        linhas.append(f"{status_skill} **{skill['nome']}** | nv `{skill['nivel']}` | mana `{skill['mana']}` | cd `{skill.get('cooldown', 0)}`")
    await ctx.send(embed=embed_padrao(f"🧠 Habilidades de {player['nome']}", "\n".join(linhas), discord.Color.blurple()))


@commands.cooldown(1, 8, commands.BucketType.user)
@bot.command(name="explorar")
async def explorar(ctx, regiao: str = "floresta"):
    player = pegar_player(ctx.author.id)
    if not player:
        await ctx.send(exigir_player_msg())
        return
    regiao_key = normalizar(regiao)
    if regiao_key not in REGIOES:
        await ctx.send("Regiao invalida. Use `!regioes`.")
        return
    info = REGIOES[regiao_key]
    if int(player["nivel"]) < int(info["nivel"]):
        await ctx.send(f"Essa regiao recomenda nivel `{info['nivel']}+`. Evolua mais um pouco.")
        return
    if int(player["energia"]) <= 0:
        await ctx.send("Voce esta sem energia. Use `!daily` ou `!descansar`.")
        return

    energia = int(player["energia"]) - 1
    evento = random.choices(
        ["ouro", "item", "monstro", "npc", "armadilha", "nada"],
        weights=[22, 15, 24, 10, 12, 17],
        k=1,
    )[0]
    stats = stats_efetivos(player)
    salvar_player(ctx.author.id, energia=energia)
    progresso_quest(ctx.author.id, "explorar", 1)
    linhas = [f"{info['emoji']} **{player['nome']}** explorou **{info['nome']}**."]

    if evento == "ouro":
        ganho = int((random.randint(35, 95) + int(player["nivel"]) * 8) * evento_global()["bonus_ouro"])
        salvar_player(ctx.author.id, ouro=int(player["ouro"]) + ganho)
        linhas.append(f"💰 Encontrou **{ganho} ouro** em um bau antigo.")
    elif evento == "item":
        drop = gerar_drop(int(player["nivel"]), stats["sorte"]) or "pocao_pequena"
        adicionar_item(ctx.author.id, drop, 1)
        linhas.append(f"🎒 Encontrou **{ITENS[drop]['nome']}** ({ITENS[drop]['raridade']}).")
    elif evento == "monstro":
        monstro = criar_monstro(regiao_key, int(player["nivel"]))
        linhas.append(f"👾 Rastros de **{monstro['nome']}** apareceram. Use `!batalhar {regiao_key}` para enfrentar.")
    elif evento == "npc":
        ganho = 35 + int(player["nivel"]) * 5
        mensagens = aplicar_xp(ctx.author.id, ganho, 0)
        linhas.append(f"🧙 Um NPC compartilhou conhecimento. Voce ganhou **{ganho} XP**.")
        linhas.extend(mensagens)
    elif evento == "armadilha":
        dano = random.randint(10, 35) + int(info["dificuldade"] * 6)
        novo_hp = max(1, int(player["hp"]) - dano)
        salvar_player(ctx.author.id, hp=novo_hp)
        linhas.append(f"🪤 Uma armadilha causou **{dano} dano**.")
    else:
        linhas.append("🌫️ Nada aconteceu, mas a regiao ficou mapeada.")

    await ctx.send(embed=embed_padrao("🧭 Exploracao", "\n".join(linhas), discord.Color.green()))


@commands.cooldown(1, 15, commands.BucketType.user)
@bot.command(name="batalhar", aliases=["batalha", "fight"])
async def batalhar(ctx, regiao: str = "floresta"):
    player = pegar_player(ctx.author.id)
    if not player:
        await ctx.send(exigir_player_msg())
        return
    regiao_key = normalizar(regiao)
    if regiao_key not in REGIOES:
        await ctx.send("Regiao invalida. Use `!regioes`.")
        return
    info = REGIOES[regiao_key]
    if int(player["nivel"]) < int(info["nivel"]):
        await ctx.send(f"Essa regiao recomenda nivel `{info['nivel']}+`.")
        return
    if int(player["hp"]) <= 1:
        await ctx.send("Voce esta sem HP. Use `!descansar` ou pocoes.")
        return
    if int(player["energia"]) <= 0:
        await ctx.send("Voce esta sem energia. Use `!daily` ou `!descansar`.")
        return

    salvar_player(ctx.author.id, energia=int(player["energia"]) - 1)
    player = pegar_player(ctx.author.id)
    monstro = criar_monstro(regiao_key, int(player["nivel"]))
    resultado = simular_pve(player, monstro.copy())
    evento = evento_global()
    linhas = resultado["log"]

    xp_ganho = 0
    ouro_ganho = 0
    if resultado["venceu"]:
        xp_ganho = int(monstro["xp"] * evento["bonus_xp"])
        ouro_ganho = int(monstro["ouro"] * evento["bonus_ouro"])
        salvar_player(
            ctx.author.id,
            hp=resultado["hp"],
            mana=resultado["mana"],
            pocao=resultado["pocao"],
            monstros_derrotados=int(player["monstros_derrotados"] or 0) + 1,
            monstro_derrotado=int(player["monstro_derrotado"] or 0) + 1 if "monstro_derrotado" in player.keys() else 1,
        )
        linhas.append(f"🏆 Vitoria! Ganhou **{xp_ganho} XP** e **{ouro_ganho} ouro**.")
        mensagens = aplicar_xp(ctx.author.id, xp_ganho, ouro_ganho)
        linhas.extend(mensagens)
        progresso_quest(ctx.author.id, "combate", 1)
        drop = gerar_drop(int(player["nivel"]), stats_efetivos(player)["sorte"])
        if drop:
            adicionar_item(ctx.author.id, drop, 1)
            linhas.append(f"🎁 Drop: **{ITENS[drop]['nome']}** ({ITENS[drop]['raridade']}).")
    else:
        perda = min(int(player["ouro"]), random.randint(15, 70))
        salvar_player(ctx.author.id, hp=1, mana=resultado["mana"], pocao=resultado["pocao"], ouro=int(player["ouro"]) - perda)
        linhas.append(f"☠️ Derrota. Voce escapou com 1 HP e perdeu **{perda} ouro**.")

    registrar_batalha(ctx.author.id, "pve", monstro["nome"], resultado["venceu"], resultado["dano"], xp_ganho, ouro_ganho)
    await ctx.send(embed=embed_padrao("⚔️ Batalha por Turnos", resumir_lista(linhas, 3800), discord.Color.red() if not resultado["venceu"] else discord.Color.gold()))


@bot.command(name="descansar")
async def descansar(ctx):
    player = pegar_player(ctx.author.id)
    if not player:
        await ctx.send(exigir_player_msg())
        return
    stats = stats_efetivos(player)
    salvar_player(ctx.author.id, hp=stats["hp_max"], mana=stats["mana_max"], energia=int(player["energia_max"]))
    await ctx.send("🛌 Voce descansou e recuperou HP, mana e energia.")


@bot.command(name="usar", aliases=["curar", "use"])
async def usar(ctx, *, item_nome: str = "pocao_pequena"):
    player = pegar_player(ctx.author.id)
    if not player:
        await ctx.send(exigir_player_msg())
        return

    item_key = normalizar(item_nome or "pocao_pequena")
    stats = stats_efetivos(player)

    if item_key in ("pocao", "pocao_antiga") and int(player["pocao"] or 0) > 0:
        cura = 60 + int(player["nivel"]) * 3
        novo_hp = min(stats["hp_max"], int(player["hp"]) + cura)
        salvar_player(ctx.author.id, hp=novo_hp, pocao=int(player["pocao"]) - 1)
        await ctx.send(f"🧪 Voce usou uma pocao antiga e recuperou **{novo_hp - int(player['hp'])} HP**.")
        return

    with abrir_db() as db:
        item = db.execute(
            "SELECT * FROM inventario WHERE user_id = ? AND item_key = ?",
            (ctx.author.id, item_key),
        ).fetchone()

    if not item:
        await ctx.send("Voce nao possui esse item. Veja `!inventario`.")
        return
    if item["tipo"] != "pocao":
        await ctx.send("Esse item nao pode ser usado diretamente.")
        return

    info = ITENS.get(item["item_key"], {})
    cura = int(info.get("cura", 0))
    mana_rec = int(info.get("mana", 0))
    novo_hp = min(stats["hp_max"], int(player["hp"]) + cura)
    novo_mana = min(stats["mana_max"], int(player["mana"]) + mana_rec)

    if novo_hp == int(player["hp"]) and novo_mana == int(player["mana"]):
        await ctx.send("Seu HP/mana ja estao cheios.")
        return
    if not remover_item(ctx.author.id, item_key, 1):
        await ctx.send("Nao foi possivel usar esse item agora.")
        return

    salvar_player(ctx.author.id, hp=novo_hp, mana=novo_mana)
    partes = []
    if novo_hp > int(player["hp"]):
        partes.append(f"{novo_hp - int(player['hp'])} HP")
    if novo_mana > int(player["mana"]):
        partes.append(f"{novo_mana - int(player['mana'])} mana")
    await ctx.send(f"🧪 Usou **{item['nome']}** e recuperou **{', '.join(partes)}**.")


@bot.command(name="daily", aliases=["diario"])
async def daily(ctx):
    player = pegar_player(ctx.author.id)
    if not player:
        await ctx.send(exigir_player_msg())
        return
    hoje = hoje_chave()
    if player["ultima_daily"] == hoje:
        await ctx.send("Voce ja coletou sua recompensa diaria hoje.")
        return
    recompensa = 140 + int(player["nivel"]) * 25 + int(player["reincarnacoes"] or 0) * 100
    salvar_player(
        ctx.author.id,
        ouro=int(player["ouro"]) + recompensa,
        energia=int(player["energia_max"]),
        ultima_daily=hoje,
    )
    adicionar_item(ctx.author.id, "pocao_pequena", 1)
    await ctx.send(f"🎁 Daily coletado: **{recompensa} ouro**, energia cheia e **1 Pocao Pequena**.")


