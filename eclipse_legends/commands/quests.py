# Arquivo extraido de bot.py para manter o projeto organizado.
from ..core import *
from ..database import *
from ..gacha import *
from ..social import *
from ..rpg import *
from ..music import *

# =========================
# QUESTS E HISTORIA
# =========================

@bot.group(name="quest", aliases=["quests"], invoke_without_command=True)
async def quest(ctx):
    player = pegar_player(ctx.author.id)
    if not player:
        await ctx.send(exigir_player_msg())
        return
    with abrir_db() as db:
        rows = db.execute(
            "SELECT * FROM quests WHERE user_id = ? AND ativa = 1 ORDER BY concluida DESC, id DESC LIMIT 8",
            (ctx.author.id,),
        ).fetchall()
    if not rows:
        await ctx.send("Voce nao tem quests ativas. Use `!quest diaria`.")
        return
    linhas = []
    for row in rows:
        status_txt = "✅ pronta" if row["concluida"] else "⏳ em progresso"
        linhas.append(f"`#{row['id']}` **{row['titulo']}** - {row['progresso']}/{row['alvo']} | {status_txt} | entregar: `!quest entregar {row['id']}`")
    await ctx.send(embed=embed_padrao("📜 Quests", "\n".join(linhas), discord.Color.dark_gold()))


@quest.command(name="diaria")
async def quest_diaria(ctx):
    player = pegar_player(ctx.author.id)
    if not player:
        await ctx.send(exigir_player_msg())
        return
    hoje = hoje_chave()
    if player["ultima_quest_daily"] == hoje:
        await ctx.send("Voce ja recebeu sua quest diaria hoje. Veja `!quest`.")
        return
    template_key = random.choice(list(QUEST_TEMPLATES.keys()))
    q = QUEST_TEMPLATES[template_key]
    recompensa_xp = q["xp"] + int(player["nivel"]) * 15
    recompensa_ouro = q["ouro"] + int(player["nivel"]) * 12
    with abrir_db() as db:
        db.execute(
            """
            INSERT INTO quests(user_id, quest_key, titulo, tipo, alvo, recompensa_xp, recompensa_ouro)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (ctx.author.id, template_key, q["titulo"], q["tipo"], q["alvo"], recompensa_xp, recompensa_ouro),
        )
        db.commit()
    salvar_player(ctx.author.id, ultima_quest_daily=hoje)
    await ctx.send(f"📜 Quest diaria recebida: **{q['titulo']}**\n{q['desc']}\nRecompensa: `{recompensa_xp}` XP e `{recompensa_ouro}` ouro.")


@quest.command(name="entregar")
async def quest_entregar(ctx, quest_id: int = None):
    player = pegar_player(ctx.author.id)
    if not player:
        await ctx.send(exigir_player_msg())
        return
    if quest_id is None:
        await ctx.send("Use: `!quest entregar id`.")
        return
    with abrir_db() as db:
        row = db.execute(
            "SELECT * FROM quests WHERE id = ? AND user_id = ? AND ativa = 1",
            (quest_id, ctx.author.id),
        ).fetchone()
        if not row:
            await ctx.send("Quest nao encontrada.")
            return
        if not row["concluida"]:
            await ctx.send(f"Quest ainda nao concluida: `{row['progresso']}/{row['alvo']}`.")
            return
        db.execute("UPDATE quests SET ativa = 0, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (quest_id,))
        db.commit()
    mensagens = aplicar_xp(ctx.author.id, row["recompensa_xp"], row["recompensa_ouro"])
    texto = f"✅ Quest entregue: **{row['titulo']}**\nGanhou `{row['recompensa_xp']}` XP e `{row['recompensa_ouro']}` ouro."
    if mensagens:
        texto += "\n" + "\n".join(mensagens)
    await ctx.send(texto)


@bot.command(name="historia")
async def historia(ctx, escolha: str = None):
    player = pegar_player(ctx.author.id)
    if not player:
        await ctx.send(exigir_player_msg())
        return
    etapa = int(player["historia_etapa"] or 0)
    cena = HISTORIA.get(etapa)
    if not cena:
        await ctx.send("📜 Voce concluiu a historia atual. Novos capitulos surgirao em eventos futuros.")
        return
    if not escolha:
        opcoes = ", ".join(f"`{op}`" for op in cena["opcoes"])
        await ctx.send(embed=embed_padrao(f"📜 {cena['titulo']}", f"{cena['texto']}\n\nEscolhas: {opcoes}\nUse `!historia escolha`.", discord.Color.dark_gold()))
        return
    escolha_key = normalizar(escolha)
    if escolha_key not in cena["opcoes"]:
        await ctx.send("Escolha invalida. Use `!historia` para ver opcoes.")
        return
    texto, xp, ouro, bonus = cena["opcoes"][escolha_key]
    campos = {"historia_etapa": etapa + 1}
    for atributo, valor in bonus.items():
        campos[atributo] = int(player[atributo]) + int(valor)
    salvar_player(ctx.author.id, **campos)
    mensagens = aplicar_xp(ctx.author.id, xp, ouro)
    await ctx.send(f"📜 {texto}\nGanhou `{xp}` XP e `{ouro}` ouro." + ("\n" + "\n".join(mensagens) if mensagens else ""))


