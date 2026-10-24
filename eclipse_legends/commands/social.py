# Arquivo extraido de bot.py para manter o projeto organizado.
from ..core import *
from ..database import *
from ..gacha import *
from ..social import *
from ..rpg import *
from ..music import *

# =========================
# SISTEMA SOCIAL / AURA
# =========================

@bot.group(name="perfil", aliases=["profile"], invoke_without_command=True)
async def perfil(ctx, membro: discord.Member = None):
    membro = membro or ctx.author
    user = pegar_social_user(membro.id)
    checar_conquistas_social(membro.id)
    user = pegar_social_user(membro.id)
    try:
        buffer = await asyncio.to_thread(gerar_card_social, membro, user)
        arquivo = discord.File(buffer, filename=f"perfil_{membro.id}.png")
        await ctx.send(file=arquivo)
    except Exception:
        prox = xp_para_proximo_social(user["nivel"])
        embed = embed_padrao(f"🌟 Perfil Social de {membro.display_name}", cor=discord.Color.magenta())
        embed.add_field(name="Nivel", value=str(user["nivel"]), inline=True)
        embed.add_field(name="XP", value=f"{user['xp']}/{prox}\n{barra_percentual(user['xp'], prox)}", inline=False)
        embed.add_field(name="Reputacao", value=str(user["reputacao"]), inline=True)
        embed.add_field(name="Cargo/Rank", value=cargo_social_nome(user), inline=True)
        embed.add_field(name="Aura", value=user["aura"], inline=True)
        embed.add_field(name="Mensagens", value=str(user["mensagens"]), inline=True)
        embed.add_field(name="Call", value=f"{int(user['call_seconds']) // 60} min", inline=True)
        embed.add_field(name="Titulo", value=user["titulo"], inline=True)
        embed.add_field(name="Bio", value=user["bio"] or "Sem bio.", inline=False)
        await ctx.send(embed=embed)


@perfil.command(name="editar")
async def perfil_editar(ctx, campo: str = None, *, valor: str = None):
    user = pegar_social_user(ctx.author.id)
    if not campo or valor is None:
        await ctx.send("Use: `!perfil editar bio texto`, `cor #ff66cc`, `fundo url`, `icon url` ou `titulo titulo`.")
        return

    campo = normalizar(campo)
    valor = valor.strip()
    if campo == "bio":
        if int(user["nivel"]) < 5:
            await ctx.send("Bio personalizada libera no nivel social 5.")
            return
        salvar_social_user(ctx.author.id, bio=valor[:120])
    elif campo == "cor":
        if int(user["nivel"]) < 10:
            await ctx.send("Cor personalizada libera no nivel social 10.")
            return
        if not (valor.startswith("#") and len(valor) == 7):
            await ctx.send("Use uma cor hexadecimal, exemplo: `#ff66cc`.")
            return
        salvar_social_user(ctx.author.id, profile_color=valor)
    elif campo == "fundo":
        if int(user["nivel"]) < 20:
            await ctx.send("Fundo personalizado libera no nivel social 20.")
            return
        salvar_social_user(ctx.author.id, profile_bg=valor[:500])
    elif campo == "icon":
        salvar_social_user(ctx.author.id, profile_icon=valor[:500])
    elif campo == "titulo":
        await escolher_titulo_social(ctx, valor)
        return
    else:
        await ctx.send("Campo invalido. Use `bio`, `cor`, `fundo`, `icon` ou `titulo`.")
        return
    await ctx.send("✅ Perfil social atualizado.")


@perfil.command(name="loja")
async def perfil_loja(ctx):
    linhas = []
    for key, item in SOCIAL_SHOP.items():
        linhas.append(f"`{key}` - **{item['nome']}** | {item['tipo']} | 💰 `{item['preco']}` | nivel `{item['nivel']}+`")
    await ctx.send(embed=embed_padrao("🛍️ Loja de Perfil", "\n".join(linhas), discord.Color.magenta()))


@perfil.command(name="comprar")
async def perfil_comprar(ctx, item_key: str = None):
    if not item_key:
        await ctx.send("Use: `!perfil comprar fundo_cyberpunk`.")
        return
    item_key = normalizar(item_key)
    item = SOCIAL_SHOP.get(item_key)
    if not item:
        await ctx.send("Item nao encontrado. Use `!perfil loja`.")
        return
    user = pegar_social_user(ctx.author.id)
    if int(user["nivel"]) < int(item["nivel"]):
        await ctx.send(f"Esse item exige nivel social `{item['nivel']}`.")
        return
    if int(user["moedas"]) < int(item["preco"]):
        await ctx.send(f"Moedas insuficientes. Voce tem `{user['moedas']}`.")
        return
    with abrir_db() as db:
        db.execute(
            "INSERT OR IGNORE INTO social_inventory(user_id, item_key, tipo, valor) VALUES (?, ?, ?, ?)",
            (ctx.author.id, item_key, item["tipo"], item["valor"]),
        )
        db.execute("UPDATE social_users SET moedas = moedas - ? WHERE user_id = ?", (item["preco"], ctx.author.id))
    await ctx.send(f"✅ Comprou **{item['nome']}**.")


@perfil.command(name="equipar")
async def perfil_equipar(ctx, item_key: str = None):
    if not item_key:
        await ctx.send("Use: `!perfil equipar moldura_dourada`.")
        return
    item_key = normalizar(item_key)
    with abrir_db() as db:
        item = db.execute(
            "SELECT * FROM social_inventory WHERE user_id = ? AND item_key = ?",
            (ctx.author.id, item_key),
        ).fetchone()
    if not item:
        await ctx.send("Voce nao possui esse item.")
        return
    if item["tipo"] == "color":
        salvar_social_user(ctx.author.id, profile_color=item["valor"])
    elif item["tipo"] == "frame":
        salvar_social_user(ctx.author.id, frame=item["valor"])
    elif item["tipo"] == "background":
        salvar_social_user(ctx.author.id, profile_bg="")
    elif item["tipo"] == "badge":
        adicionar_conquista_social(ctx.author.id, f"badge_{item_key}", item["valor"].upper(), "")
    await ctx.send("✅ Item equipado/aplicado ao perfil.")


@perfil.command(name="titulo")
async def perfil_titulo(ctx, *, titulo: str = None):
    await escolher_titulo_social(ctx, titulo)


async def escolher_titulo_social(ctx, titulo):
    if not titulo:
        await ctx.send("Use: `!titulo escolher \"A Lenda\"`.")
        return
    titulo = titulo.strip().strip('"')
    with abrir_db() as db:
        row = db.execute(
            "SELECT 1 FROM social_titles WHERE user_id = ? AND lower(titulo) = lower(?)",
            (ctx.author.id, titulo),
        ).fetchone()
    if not row and titulo not in ("Sem titulo", "Sem título"):
        await ctx.send("Voce ainda nao desbloqueou esse titulo. Veja `!titulos`.")
        return
    salvar_social_user(ctx.author.id, titulo=titulo)
    await ctx.send(f"✅ Titulo equipado: **{titulo}**.")


@bot.group(name="titulo", aliases=["titulos"], invoke_without_command=True)
async def titulo(ctx):
    user = pegar_social_user(ctx.author.id)
    with abrir_db() as db:
        rows = db.execute("SELECT titulo FROM social_titles WHERE user_id = ? ORDER BY titulo", (ctx.author.id,)).fetchall()
    titulos = ["Sem titulo"] + [row["titulo"] for row in rows]
    await ctx.send(embed=embed_padrao("🏷️ Titulos Desbloqueados", "\n".join(f"`{t}`" for t in titulos[:40]), discord.Color.magenta()))


@titulo.command(name="escolher")
async def titulo_escolher(ctx, *, titulo: str = None):
    await escolher_titulo_social(ctx, titulo)


@bot.command(name="conquistas")
async def conquistas(ctx, membro: discord.Member = None):
    membro = membro or ctx.author
    pegar_social_user(membro.id)
    checar_conquistas_social(membro.id)
    with abrir_db() as db:
        rows = db.execute(
            "SELECT nome, titulo, unlocked_at FROM social_achievements WHERE user_id = ? ORDER BY unlocked_at DESC LIMIT 20",
            (membro.id,),
        ).fetchall()
    if not rows:
        await ctx.send("Nenhuma conquista desbloqueada ainda.")
        return
    linhas = [f"🏅 **{row['nome']}**" + (f" | titulo `{row['titulo']}`" if row["titulo"] else "") for row in rows]
    await ctx.send(embed=embed_padrao(f"🏅 Conquistas de {membro.display_name}", "\n".join(linhas), discord.Color.gold()))


@bot.command(name="rep")
async def rep(ctx, membro: discord.Member = None, tipo: str = "ajuda"):
    if membro is None:
        await ctx.send("Use: `!rep @usuario ajuda`.")
        return
    if membro.bot:
        await ctx.send("Bots nao recebem reputacao.")
        return
    if membro.id == ctx.author.id:
        await ctx.send("Voce nao pode dar reputacao para si mesmo.")
        return
    giver = pegar_social_user(ctx.author.id)
    receiver = pegar_social_user(membro.id)
    hoje = hoje_chave()
    with abrir_db() as db:
        hoje_count = db.execute(
            "SELECT COUNT(*) AS total FROM social_rep_log WHERE giver_id = ? AND date(created_at) = date('now')",
            (ctx.author.id,),
        ).fetchone()["total"]
        par = db.execute(
            """
            SELECT created_at FROM social_rep_log
            WHERE giver_id = ? AND receiver_id = ?
            ORDER BY id DESC LIMIT 1
            """,
            (ctx.author.id, membro.id),
        ).fetchone()
    if int(hoje_count) >= SOCIAL_REP_DAILY_LIMIT:
        await ctx.send("Voce ja deu reputacao hoje.")
        return
    if par:
        try:
            ultima = datetime.fromisoformat(par["created_at"])
            if (datetime.utcnow() - ultima).days < SOCIAL_REP_PAIR_COOLDOWN_DAYS:
                await ctx.send("Voce ja deu reputacao para essa pessoa recentemente.")
                return
        except ValueError:
            pass

    tipo_key = normalizar(tipo)
    info = SOCIAL_REP_TYPES.get(tipo_key)
    if not info:
        await ctx.send("Tipo invalido. Use: `ajuda`, `engracado`, `confiavel`, `criativo`, `toxico`, `spam`, `golpe`.")
        return
    suspeito = 1 if int(receiver["reputacao"]) < -5 and info["valor"] < 0 else 0
    nova_rep = int(receiver["reputacao"]) + int(info["valor"])
    with abrir_db() as db:
        db.execute(
            "INSERT INTO social_rep_log(giver_id, receiver_id, tipo, valor, suspeito) VALUES (?, ?, ?, ?, ?)",
            (ctx.author.id, membro.id, tipo_key, info["valor"], suspeito),
        )
        db.execute(
            "UPDATE social_users SET reputacao = ?, aura = ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?",
            (nova_rep, aura_social({**dict(receiver), "reputacao": nova_rep}), membro.id),
        )
    checar_conquistas_social(membro.id)
    await aplicar_cargos_sociais(membro, pegar_social_user(membro.id))
    sinal = "+" if info["valor"] > 0 else ""
    await ctx.send(f"✅ {ctx.author.mention} deu **{sinal}{info['valor']} {info['label']}** para {membro.mention}.")


@bot.command(name="elogiar")
async def elogiar(ctx, membro: discord.Member = None):
    await rep.callback(ctx, membro, "ajuda")


@bot.command(name="rank")
async def rank_social(ctx, tipo: str = "nivel"):
    tipo = normalizar(tipo)
    ordenacoes = {
        "xp": ("xp DESC", "XP"),
        "nivel": ("nivel DESC, xp DESC", "Nivel"),
        "rep": ("reputacao DESC, nivel DESC", "Reputacao"),
        "mensagens": ("mensagens DESC", "Mensagens"),
        "call": ("call_seconds DESC", "Call"),
        "semanal": ("weekly_xp DESC", "Semanal"),
        "mensal": ("monthly_xp DESC", "Mensal"),
    }
    if tipo not in ordenacoes:
        await ctx.send("Use: `!rank xp`, `nivel`, `rep`, `mensagens`, `call`, `semanal` ou `mensal`.")
        return
    order, label = ordenacoes[tipo]
    with abrir_db() as db:
        rows = db.execute(
            f"""
            SELECT user_id, nivel, xp, reputacao, mensagens, call_seconds, weekly_xp, monthly_xp
            FROM social_users
            ORDER BY {order}
            LIMIT 10
            """
        ).fetchall()
    if not rows:
        await ctx.send("Ainda nao ha dados sociais.")
        return
    linhas = []
    for i, row in enumerate(rows, 1):
        if tipo == "rep":
            extra = f"Rep `{row['reputacao']}`"
        elif tipo == "mensagens":
            extra = f"Mensagens `{row['mensagens']}`"
        elif tipo == "call":
            extra = f"Call `{int(row['call_seconds']) // 60} min`"
        elif tipo == "semanal":
            extra = f"XP semanal `{row['weekly_xp']}`"
        elif tipo == "mensal":
            extra = f"XP mensal `{row['monthly_xp']}`"
        else:
            extra = f"Nv `{row['nivel']}` | XP `{row['xp']}/{xp_para_proximo_social(row['nivel'])}`"
        linhas.append(f"**{i}.** <@{row['user_id']}> | {extra}")
    await ctx.send(embed=embed_padrao(f"🏆 Rank Social {label}", "\n".join(linhas), discord.Color.gold()))


