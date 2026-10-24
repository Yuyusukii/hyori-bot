# Arquivo extraido de bot.py para manter o projeto organizado.
from ..core import *
from ..database import *
from ..gacha import *
from ..social import *
from ..rpg import *
from ..music import *

# =========================
# GACHA ANIME
# =========================

@bot.group(name="gacha", aliases=["animegacha", "waifu"], invoke_without_command=True)
async def gacha(ctx):
    await gacha_ajuda.callback(ctx)


@gacha.command(name="ajuda", aliases=["help"])
async def gacha_ajuda(ctx):
    embed = embed_padrao(
        "🎰 Gacha Anime",
        "Sistema separado do RPG, com cristais, tickets, pity e colecao propria.",
        discord.Color.magenta(),
    )
    embed.add_field(
        name="Comandos",
        value=(
            "`!checkin` - recompensa diaria\n"
            "`!gacha roll 1` ou `!gacha roll 10` - invocar personagens\n"
            "`!gacha perfil` - saldo e progresso\n"
            "`!gacha colecao [raridade]` - ver cartas com imagem e botoes\n"
            "`!gacha ver nome` - procurar personagem\n"
            "`!gacha vender nome` - vender duplicata de personagem\n"
            "`!gacha vender comum` - vender duplicatas por raridade\n"
            "`!gacha banner` - taxas e biblioteca\n"
            "`!gacha ranking` - ranking de colecionadores"
        ),
        inline=False,
    )
    embed.add_field(
        name="Moeda",
        value=f"Cada invocacao custa `{GACHA_PULL_COST}` cristais ou `1` ticket. O roll x10 garante pelo menos Epico.",
        inline=False,
    )
    await ctx.send(embed=embed)


@gacha.command(name="banner", aliases=["taxas", "rates"])
async def gacha_banner(ctx):
    catalogo = await asyncio.to_thread(carregar_catalogo_gacha, False)
    if not catalogo:
        await ctx.send("Nao consegui carregar a biblioteca de personagens agora.")
        return

    contagens = {
        raridade: len(GACHA_CATALOGO_CACHE["por_raridade"].get(raridade, []))
        for raridade in GACHA_RARIDADES
    }
    linhas = []
    for raridade, info in GACHA_RARIDADES.items():
        linhas.append(f"{info['emoji']} **{info['nome']}** - `{info['peso']}%` base | `{contagens[raridade]}` personagens")
    linhas.append(f"\nPity: lendario/mitico garantido no pull `{GACHA_PITY_LIMIT}` sem alta raridade.")
    linhas.append(f"Fonte: {GACHA_LIBRARY_URL}")
    await ctx.send(embed=embed_padrao("🎰 Banner Atual", "\n".join(linhas), discord.Color.magenta()))


@gacha.command(name="perfil", aliases=["saldo", "profile"])
async def gacha_perfil(ctx, membro: discord.Member = None):
    membro = membro or ctx.author
    user = pegar_gacha_user(membro.id)
    stats = estatisticas_gacha(membro.id)
    total_catalogo = len(await asyncio.to_thread(carregar_catalogo_gacha, False))
    unicos = int(stats["unicos"] or 0)
    progresso = f"{unicos}/{total_catalogo}" if total_catalogo else str(unicos)

    embed = embed_padrao(f"🎰 Gacha de {membro.display_name}", cor=discord.Color.magenta())
    embed.set_thumbnail(url=membro.display_avatar.url)
    embed.add_field(name="Cristais", value=f"💎 `{user['cristais']}`", inline=True)
    embed.add_field(name="Tickets", value=f"🎟️ `{user['tickets']}`", inline=True)
    embed.add_field(name="Pity", value=f"`{user['pity']}/{GACHA_PITY_LIMIT}`", inline=True)
    embed.add_field(name="Colecao", value=f"Unicos `{progresso}`\nTotal com duplicatas `{stats['total']}`", inline=False)
    embed.add_field(name="Altas raridades", value=f"Miticos `{stats['miticos']}` | Lendarios `{stats['lendarios']}`", inline=True)
    embed.add_field(name="Check-in", value=f"Streak `{user['streak']}` | Ultimo `{user['ultima_checkin']}`", inline=True)
    await ctx.send(embed=embed)


@gacha.command(name="checkin", aliases=["daily", "diario"])
async def gacha_checkin(ctx):
    user = pegar_gacha_user(ctx.author.id)
    hoje = hoje_chave()
    if user["ultima_checkin"] == hoje:
        await ctx.send("Voce ja fez o check-in do gacha hoje.")
        return

    ontem = (agora() - timedelta(days=1)).strftime("%Y-%m-%d")
    streak = int(user["streak"] or 0) + 1 if user["ultima_checkin"] == ontem else 1
    bonus_streak = min(streak, 7) * 40
    cristais = GACHA_DAILY_CRISTAIS + bonus_streak
    tickets = GACHA_DAILY_TICKETS + (2 if streak % 7 == 0 else 0)

    salvar_gacha_user(
        ctx.author.id,
        cristais=int(user["cristais"]) + cristais,
        tickets=int(user["tickets"]) + tickets,
        ultima_checkin=hoje,
        streak=streak,
    )
    await ctx.send(f"🎁 Check-in gacha feito! Ganhou **{cristais} cristais**, **{tickets} ticket(s)** e streak `{streak}`.")


@bot.command(name="checkin", aliases=["check-in"])
async def checkin(ctx):
    await gacha_checkin.callback(ctx)


@commands.cooldown(1, 5, commands.BucketType.user)
@gacha.command(name="roll", aliases=["girar", "summon", "tiro", "invocar"])
async def gacha_roll(ctx, quantidade: int = 1):
    catalogo = await asyncio.to_thread(carregar_catalogo_gacha, False)
    if not catalogo:
        await ctx.send("Nao consegui carregar a biblioteca de personagens. Tente `!gacha atualizar` mais tarde.")
        return

    quantidade = max(1, min(10, int(quantidade)))
    user = pegar_gacha_user(ctx.author.id)
    usar_tickets = min(int(user["tickets"]), quantidade)
    faltam = quantidade - usar_tickets
    custo = faltam * GACHA_PULL_COST

    if int(user["cristais"]) < custo:
        await ctx.send(
            f"Voce precisa de `{custo}` cristais para esse roll. Saldo: `{user['cristais']}` cristais e `{user['tickets']}` ticket(s)."
        )
        return

    pity = int(user["pity"])
    total_pulls = int(user["total_pulls"])
    resultados = []
    tem_epico_ou_melhor = False

    for indice in range(quantidade):
        pity += 1
        garantir_epico = quantidade == 10 and indice == quantidade - 1 and not tem_epico_ou_melhor
        personagem = sortear_personagem_gacha(pity, garantir_epico)
        if not personagem:
            await ctx.send("A biblioteca esta vazia no momento.")
            return

        total_pulls += 1
        if rank_raridade_gacha(personagem["raridade"]) >= 3:
            tem_epico_ou_melhor = True
        if personagem["raridade"] in ("lendario", "mitico"):
            pity = 0

        adicionar_personagem_gacha(ctx.author.id, personagem)
        resultados.append(personagem)

    salvar_gacha_user(
        ctx.author.id,
        cristais=int(user["cristais"]) - custo,
        tickets=int(user["tickets"]) - usar_tickets,
        pity=pity,
        total_pulls=total_pulls,
    )

    melhor = max(resultados, key=lambda p: rank_raridade_gacha(p["raridade"]))
    embed = embed_padrao(
        "🎰 Resultado do Gacha",
        f"Usou `{usar_tickets}` ticket(s) e `{custo}` cristais.\nPity atual: `{pity}/{GACHA_PITY_LIMIT}`.",
        cor_gacha(melhor["raridade"]),
    )
    if quantidade == 1:
        personagem = resultados[0]
        embed.add_field(name="Personagem", value=f"{nome_raridade_gacha(personagem['raridade'])} **{personagem['nome']}**", inline=False)
        embed.add_field(name="Anime", value=personagem["anime"], inline=False)
    else:
        embed.add_field(name="Resultados", value=resumir_lista(formatar_resultados_gacha(resultados), 1000), inline=False)
        embed.add_field(name="Melhor pull", value=f"{nome_raridade_gacha(melhor['raridade'])} **{melhor['nome']}**", inline=False)
    if melhor.get("imagem"):
        embed.set_image(url=melhor["imagem"])
    await ctx.send(embed=embed)


@bot.command(name="girar", aliases=["roll", "summon"])
async def girar(ctx, quantidade: int = 1):
    await gacha_roll.callback(ctx, quantidade)


@gacha.command(name="colecao", aliases=["collection", "cards"])
async def gacha_colecao(ctx, raridade: str = None):
    pegar_gacha_user(ctx.author.id)
    raridade_key = normalizar_raridade_gacha(raridade) if raridade else None
    params = [ctx.author.id]
    filtro_sql = ""
    if raridade:
        filtro_sql = "AND raridade = ?"
        params.append(raridade_key)

    with abrir_db() as db:
        rows = db.execute(
            f"""
            SELECT char_key, nome, anime, imagem, raridade, quantidade
            FROM gacha_collection
            WHERE user_id = ? {filtro_sql}
            ORDER BY
                CASE raridade
                    WHEN 'mitico' THEN 5
                    WHEN 'lendario' THEN 4
                    WHEN 'epico' THEN 3
                    WHEN 'raro' THEN 2
                    ELSE 1
                END DESC,
                quantidade DESC,
                nome ASC
            """,
            params,
        ).fetchall()

    if not rows:
        await ctx.send("Sua colecao gacha ainda esta vazia. Use `!checkin` e depois `!gacha roll 1`.")
        return

    filtro = nome_raridade_gacha(raridade_key) if raridade else None
    view = GachaCollectionView(ctx.author.id, rows, ctx.author.display_name, filtro)
    await ctx.send(embed=view._embed(), view=view)


@gacha.command(name="vender", aliases=["sell", "queimar", "trocar"])
async def gacha_vender(ctx, *, entrada: str = None):
    if not entrada:
        await ctx.send(
            "Use: `!gacha vender nome_do_personagem` ou `!gacha vender comum`.\n"
            "A venda remove apenas duplicatas e sempre mantem 1 copia na colecao."
        )
        return

    entrada = entrada.strip()
    alvo = entrada
    quantidade = None
    if " " in entrada:
        possivel_alvo, possivel_qtd = entrada.rsplit(" ", 1)
        if normalizar(possivel_qtd) in ("todos", "tudo", "all", "max") or possivel_qtd.isdigit():
            alvo = possivel_alvo.strip()
            quantidade = possivel_qtd.strip()

    alvo_key = normalizar(alvo)
    raridades_validas = set(GACHA_RARIDADES) | {"todos", "tudo", "all"}
    if alvo_key in raridades_validas:
        raridade = None if alvo_key in ("todos", "tudo", "all") else normalizar_raridade_gacha(alvo)
        resultado = vender_duplicatas_por_raridade(ctx.author.id, raridade)
        if resultado["copias"] <= 0:
            alvo_txt = "todas as raridades" if raridade is None else nome_raridade_gacha(raridade)
            await ctx.send(f"Voce nao tem duplicatas vendiveis em **{alvo_txt}**.")
            return
        alvo_txt = "todas as raridades" if raridade is None else nome_raridade_gacha(raridade)
        await ctx.send(
            f"💎 Venda em massa concluida: **{resultado['copias']} duplicata(s)** de **{resultado['personagens']} personagem(ns)** em **{alvo_txt}** por **{resultado['cristais']} cristais**."
        )
        return

    qtd = None
    if quantidade:
        quantidade_key = normalizar(quantidade)
        if quantidade_key not in ("todos", "tudo", "all", "max"):
            try:
                qtd = max(1, int(quantidade))
            except ValueError:
                await ctx.send("Quantidade invalida. Use numero ou `todos`.")
                return

    resultado = vender_duplicata_personagem(ctx.author.id, alvo, qtd)
    if resultado.get("erro") == "nao_encontrado":
        await ctx.send("Nao encontrei esse personagem na sua colecao.")
        return
    if resultado.get("erro") == "sem_duplicata":
        row = resultado["row"]
        await ctx.send(f"Voce so tem 1 copia de **{row['nome']}**. A venda segura preserva a primeira copia.")
        return

    row = resultado["row"]
    await ctx.send(
        f"💎 Vendeu **{resultado['copias']} duplicata(s)** de **{row['nome']}** ({nome_raridade_gacha(row['raridade'])}) por **{resultado['cristais']} cristais**."
    )


@gacha.command(name="ver", aliases=["personagem", "char", "buscar"])
async def gacha_ver(ctx, *, busca: str = None):
    if not busca:
        await ctx.send("Use: `!gacha ver nome do personagem`.")
        return

    catalogo = await asyncio.to_thread(carregar_catalogo_gacha, False)
    if not catalogo:
        await ctx.send("Nao consegui carregar a biblioteca de personagens.")
        return

    busca_norm = normalizar(busca)
    encontrados = [
        personagem
        for personagem in catalogo
        if busca_norm in normalizar(personagem["nome"]) or busca_norm in normalizar(personagem["anime"])
    ]
    if not encontrados:
        await ctx.send("Nao encontrei esse personagem/anime na biblioteca.")
        return

    encontrados.sort(key=lambda p: (normalizar(p["nome"]) != busca_norm, -rank_raridade_gacha(p["raridade"])))
    personagem = encontrados[0]
    with abrir_db() as db:
        owned = db.execute(
            "SELECT quantidade FROM gacha_collection WHERE user_id = ? AND char_key = ?",
            (ctx.author.id, personagem["key"]),
        ).fetchone()

    embed = embed_padrao(
        personagem["nome"],
        f"{nome_raridade_gacha(personagem['raridade'])}\nAnime: **{personagem['anime']}**",
        cor_gacha(personagem["raridade"]),
    )
    embed.add_field(name="Na sua colecao", value=f"`x{owned['quantidade']}`" if owned else "`nao possui`", inline=True)
    embed.add_field(name="Resultados parecidos", value=str(min(len(encontrados), 25)), inline=True)
    if personagem.get("imagem"):
        embed.set_image(url=personagem["imagem"])
    await ctx.send(embed=embed)


@gacha.command(name="ranking", aliases=["rank"])
async def gacha_ranking(ctx):
    with abrir_db() as db:
        rows = db.execute(
            """
            SELECT
                user_id,
                COUNT(*) AS unicos,
                COALESCE(SUM(quantidade), 0) AS total,
                COALESCE(SUM(CASE WHEN raridade = 'mitico' THEN 1 ELSE 0 END), 0) AS miticos,
                COALESCE(SUM(CASE WHEN raridade = 'lendario' THEN 1 ELSE 0 END), 0) AS lendarios
            FROM gacha_collection
            GROUP BY user_id
            ORDER BY miticos DESC, lendarios DESC, unicos DESC, total DESC
            LIMIT 10
            """
        ).fetchall()

    if not rows:
        await ctx.send("Ainda nao ha colecionadores no gacha.")
        return

    linhas = []
    for i, row in enumerate(rows, 1):
        linhas.append(
            f"**{i}.** <@{row['user_id']}> | Unicos `{row['unicos']}` | Total `{row['total']}` | Miticos `{row['miticos']}` | Lendarios `{row['lendarios']}`"
        )
    await ctx.send(embed=embed_padrao("🏆 Ranking Gacha", "\n".join(linhas), discord.Color.gold()))


@gacha.command(name="historico", aliases=["history"])
async def gacha_historico(ctx):
    with abrir_db() as db:
        rows = db.execute(
            """
            SELECT nome, anime, raridade, created_at
            FROM gacha_history
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT 10
            """,
            (ctx.author.id,),
        ).fetchall()
    if not rows:
        await ctx.send("Voce ainda nao fez nenhum roll.")
        return
    linhas = [
        f"{nome_raridade_gacha(row['raridade'])} **{row['nome']}** - {row['anime']} `{row['created_at']}`"
        for row in rows
    ]
    await ctx.send(embed=embed_padrao("🧾 Historico Gacha", resumir_lista(linhas), discord.Color.magenta()))


@gacha.command(name="atualizar", aliases=["reload", "recarregar"])
async def gacha_atualizar(ctx):
    catalogo = await asyncio.to_thread(carregar_catalogo_gacha, True)
    if not catalogo:
        await ctx.send("Nao consegui atualizar a biblioteca agora.")
        return
    await ctx.send(f"✅ Biblioteca gacha atualizada: `{len(catalogo)}` personagens carregados.")


@bot.group(name="adm", aliases=["gachaadm", "gadm"], invoke_without_command=True)
async def adm(ctx):
    if not await exigir_adm_gacha(ctx):
        return
    embed = embed_padrao(
        "🛠️ Admin Gacha",
        "Comandos administrativos do gacha. Apenas cargos/permissoes liberadas podem usar.",
        discord.Color.dark_red(),
    )
    embed.add_field(name="Adicionar rolls", value="`!adm rolls @usuario quantidade`", inline=False)
    embed.add_field(name="Adicionar cristais", value="`!adm cristais @usuario quantidade`", inline=False)
    embed.add_field(name="Ver saldo", value="`!adm status @usuario`", inline=False)
    embed.add_field(name="Social/Aura max", value="`!adm socialmax @usuario`", inline=False)
    embed.add_field(name="Reset social", value="`!adm socialreset @usuario confirmar`", inline=False)
    embed.add_field(name="Reset global", value="`!adm reset confirmar`", inline=False)
    try:
        await ctx.author.send(embed=embed)
        await ctx.send("📩 Enviei os comandos de admin no seu PV.")
    except (discord.Forbidden, discord.HTTPException, AttributeError):
        await ctx.send(embed=embed)


@adm.command(name="rolls", aliases=["roll", "tickets", "ticket", "addrolls"])
async def adm_rolls(ctx, membro: discord.Member = None, quantidade: int = None):
    if not await exigir_adm_gacha(ctx):
        return
    if membro is None or quantidade is None:
        await ctx.send("Use: `!adm rolls @usuario 10`.")
        return
    if quantidade <= 0:
        await ctx.send("A quantidade precisa ser maior que zero.")
        return

    quantidade = min(int(quantidade), 100000)
    user = pegar_gacha_user(membro.id)
    salvar_gacha_user(membro.id, tickets=int(user["tickets"]) + quantidade)
    await ctx.send(f"✅ Adicionado **{quantidade} roll(s)/ticket(s)** para {membro.mention}.")


@adm.command(name="cristais", aliases=["crystal", "crystals", "gemas", "moeda"])
async def adm_cristais(ctx, membro: discord.Member = None, quantidade: int = None):
    if not await exigir_adm_gacha(ctx):
        return
    if membro is None or quantidade is None:
        await ctx.send("Use: `!adm cristais @usuario 1200`.")
        return
    if quantidade <= 0:
        await ctx.send("A quantidade precisa ser maior que zero.")
        return

    quantidade = min(int(quantidade), 10000000)
    user = pegar_gacha_user(membro.id)
    salvar_gacha_user(membro.id, cristais=int(user["cristais"]) + quantidade)
    await ctx.send(f"✅ Adicionado **{quantidade} cristais** para {membro.mention}.")


@adm.command(name="status", aliases=["saldo"])
async def adm_status(ctx, membro: discord.Member = None):
    if not await exigir_adm_gacha(ctx):
        return
    membro = membro or ctx.author
    user = pegar_gacha_user(membro.id)
    stats = estatisticas_gacha(membro.id)
    await ctx.send(
        f"🛠️ **Gacha de {membro.mention}**\n"
        f"💎 Cristais: `{user['cristais']}`\n"
        f"🎟️ Rolls/Tickets: `{user['tickets']}`\n"
        f"🎯 Pity: `{user['pity']}/{GACHA_PITY_LIMIT}`\n"
        f"🎴 Colecao: `{stats['unicos']}` unicos / `{stats['total']}` total"
    )


@adm.command(name="socialmax", aliases=["auramax", "maxsocial", "max"])
async def adm_socialmax(ctx, membro: discord.Member = None):
    if not await exigir_adm_gacha(ctx):
        return
    membro = membro or ctx.author
    pegar_social_user(membro.id)
    nivel = 100
    salvar_social_user(
        membro.id,
        nivel=nivel,
        xp=0,
        reputacao=999,
        moedas=99999,
        mensagens=1000,
        call_seconds=600 * 60,
        titulo="A Lenda",
        aura="Lendaria",
    )
    for titulo_nome in SOCIAL_TITLES:
        desbloquear_titulo_social(membro.id, titulo_nome)
    adicionar_conquista_social(membro.id, "admin_social_max", "Aura Maximizada", "A Lenda")
    await aplicar_cargos_sociais(membro, pegar_social_user(membro.id))
    await ctx.send(f"✨ {membro.mention} agora esta no **nivel social 100**, Aura **Lendaria** e com **99999 moedas**.")


@adm.command(name="socialreset", aliases=["resetsocial", "aurareset", "resetaura"])
async def adm_socialreset(ctx, membro: discord.Member = None, confirmacao: str = None):
    if not await exigir_adm_gacha(ctx):
        return
    if membro is None:
        await ctx.send("Use: `!adm socialreset @usuario confirmar`.")
        return
    if normalizar(confirmacao) not in ("confirmar", "confirma", "sim", "yes"):
        await ctx.send(
            "⚠️ Isso limpa o Social/Aura desse usuario: nivel, XP, moedas, icon, fundo, cor, bio, titulo, conquistas e inventario social.\n"
            "Para confirmar use: `!adm socialreset @usuario confirmar`"
        )
        return

    with abrir_db() as db:
        db.execute(
            """
            INSERT OR REPLACE INTO social_users (
                user_id, xp, nivel, reputacao, mensagens, call_seconds, moedas,
                titulo, bio, profile_color, profile_icon, profile_bg, frame, aura,
                reports, last_message_at, last_message_hash, repeated_count,
                daily_xp, daily_key, weekly_xp, weekly_key, monthly_xp, monthly_key,
                created_at, updated_at
            )
            VALUES (?, 0, 1, 0, 0, 0, 0, 'Sem titulo', '', '#ff66cc', '', '', '', 'Neutra',
                    0, '', '', 0, 0, ?, 0, ?, 0, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (membro.id, hoje_chave(), semana_chave(), mes_chave()),
        )
        db.execute("DELETE FROM social_rep_log WHERE giver_id = ? OR receiver_id = ?", (membro.id, membro.id))
        db.execute("DELETE FROM social_achievements WHERE user_id = ?", (membro.id,))
        db.execute("DELETE FROM social_titles WHERE user_id = ?", (membro.id,))
        db.execute("DELETE FROM social_inventory WHERE user_id = ?", (membro.id,))
        db.execute("DELETE FROM social_voice_sessions WHERE user_id = ?", (membro.id,))
    await ctx.send(f"♻️ Social/Aura de {membro.mention} foi resetado para o inicio.")


@adm.command(name="reset", aliases=["resetar", "wipe"])
async def adm_reset(ctx, confirmacao: str = None):
    if not await exigir_adm_gacha(ctx):
        return
    if normalizar(confirmacao) not in ("confirmar", "confirma", "sim", "yes"):
        await ctx.send(
            "⚠️ Isso apaga **todo o gacha de todos os usuarios**: saldos, tickets, colecoes e historico.\n"
            "Para confirmar use: `!adm reset confirmar`"
        )
        return

    with abrir_db() as db:
        db.execute("DELETE FROM gacha_history")
        db.execute("DELETE FROM gacha_collection")
        db.execute("DELETE FROM gacha_users")
    await ctx.send("🧨 Reset global do gacha concluido. Todos comecam do zero.")


