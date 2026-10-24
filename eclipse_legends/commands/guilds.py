# Arquivo extraido de bot.py para manter o projeto organizado.
from ..core import *
from ..database import *
from ..gacha import *
from ..social import *
from ..rpg import *
from ..music import *

# =========================
# PVP, GUILDAS E RANKING
# =========================

def simular_pvp_local(a, b):
    a_stats = stats_efetivos(a)
    b_stats = stats_efetivos(b)
    a_hp = a_stats["hp_max"]
    b_hp = b_stats["hp_max"]
    log = [f"⚔️ **{a['nome']}** desafia **{b['nome']}**."]
    dano_a = 0
    dano_b = 0
    for turno in range(1, 13):
        if a_hp <= 0 or b_hp <= 0:
            break
        for atacante, defensor in ((a, b), (b, a)):
            if a_hp <= 0 or b_hp <= 0:
                break
            atk_stats = a_stats if atacante["user_id"] == a["user_id"] else b_stats
            def_stats = b_stats if atacante["user_id"] == a["user_id"] else a_stats
            if random.random() < def_stats["esquiva"]:
                log.append(f"💨 {defensor['nome']} esquivou.")
                continue
            bruto = poder_principal(atacante, atk_stats) + random.randint(-5, 12) - def_stats["defesa"] * 0.45
            dano, critou = dano_com_crit(max(1, bruto), atk_stats["crit"])
            if atacante["user_id"] == a["user_id"]:
                b_hp -= dano
                dano_a += dano
            else:
                a_hp -= dano
                dano_b += dano
            log.append(f"Turno {turno}: **{atacante['nome']}** causa **{dano}**" + (" CRITICO!" if critou else "."))
    venceu_a = a_hp >= b_hp
    return {"vencedor": a if venceu_a else b, "perdedor": b if venceu_a else a, "log": log, "dano_a": dano_a, "dano_b": dano_b}


@commands.cooldown(1, 25, commands.BucketType.user)
@bot.command(name="pvp", aliases=["duelo"])
async def pvp(ctx, membro: discord.Member = None, modo: str = "casual"):
    if membro is None:
        await ctx.send("Use: `!pvp @usuario casual` ou `!pvp @usuario ranqueado`.")
        return
    if membro.bot or membro.id == ctx.author.id:
        await ctx.send("Escolha outro jogador real.")
        return
    a = pegar_player(ctx.author.id)
    b = pegar_player(membro.id)
    if not a or not b:
        await ctx.send("Os dois jogadores precisam ter personagem.")
        return
    modo_key = normalizar(modo)
    resultado = simular_pvp_local(a, b)
    vencedor = resultado["vencedor"]
    perdedor = resultado["perdedor"]
    linhas = resultado["log"]
    linhas.append(f"🏆 Vencedor: **{vencedor['nome']}**.")

    if modo_key in ("ranqueado", "ranked", "rank"):
        v_wins = int(vencedor["pvp_vitorias"]) + 1
        p_losses = int(perdedor["pvp_derrotas"]) + 1
        salvar_player(vencedor["user_id"], pvp_vitorias=v_wins, rank=rank_por_pontos(v_wins, vencedor["pvp_derrotas"]))
        salvar_player(perdedor["user_id"], pvp_derrotas=p_losses, rank=rank_por_pontos(perdedor["pvp_vitorias"], p_losses))
        progresso_quest(vencedor["user_id"], "pvp", 1)
        mensagens = aplicar_xp(vencedor["user_id"], 60 + int(vencedor["nivel"]) * 8, 45)
        linhas.append("📈 Ranqueado atualizado.")
        linhas.extend(mensagens)
    await ctx.send(embed=embed_padrao("⚔️ PvP", resumir_lista(linhas, 3800), discord.Color.red()))


@bot.group(name="guilda", invoke_without_command=True)
async def guilda(ctx):
    await guilda_perfil.callback(ctx)


@guilda.command(name="criar")
async def guilda_criar(ctx, *, nome: str = None):
    player = pegar_player(ctx.author.id)
    if not player:
        await ctx.send(exigir_player_msg())
        return
    if not nome:
        await ctx.send("Use: `!guilda criar Nome da Guilda`.")
        return
    nome = nome[:32]
    with abrir_db() as db:
        membro = db.execute("SELECT guild_id FROM guild_membros WHERE user_id = ?", (ctx.author.id,)).fetchone()
        if membro:
            await ctx.send("Voce ja esta em uma guilda.")
            return
        try:
            cur = db.execute("INSERT INTO guildas(nome, dono_id) VALUES (?, ?)", (nome, ctx.author.id))
            guild_id = cur.lastrowid
            db.execute("INSERT INTO guild_membros(user_id, guild_id, cargo) VALUES (?, ?, 'lider')", (ctx.author.id, guild_id))
            db.commit()
        except sqlite3.IntegrityError:
            await ctx.send("Ja existe uma guilda com esse nome.")
            return
    salvar_player(ctx.author.id, guild_id=guild_id)
    await ctx.send(f"🏰 Guilda **{nome}** criada.")


@guilda.command(name="entrar")
async def guilda_entrar(ctx, *, nome: str = None):
    player = pegar_player(ctx.author.id)
    if not player:
        await ctx.send(exigir_player_msg())
        return
    if not nome:
        await ctx.send("Use: `!guilda entrar Nome da Guilda`.")
        return
    with abrir_db() as db:
        membro = db.execute("SELECT guild_id FROM guild_membros WHERE user_id = ?", (ctx.author.id,)).fetchone()
        if membro:
            await ctx.send("Voce ja esta em uma guilda.")
            return
        guild = db.execute("SELECT * FROM guildas WHERE lower(nome) = lower(?)", (nome[:32],)).fetchone()
        if not guild:
            await ctx.send("Guilda nao encontrada.")
            return
        db.execute("INSERT INTO guild_membros(user_id, guild_id, cargo) VALUES (?, ?, 'membro')", (ctx.author.id, guild["id"]))
        db.commit()
    salvar_player(ctx.author.id, guild_id=guild["id"])
    await ctx.send(f"🏰 Voce entrou na guilda **{guild['nome']}**.")


@guilda.command(name="sair")
async def guilda_sair(ctx):
    with abrir_db() as db:
        membro = db.execute("SELECT * FROM guild_membros WHERE user_id = ?", (ctx.author.id,)).fetchone()
        if not membro:
            await ctx.send("Voce nao esta em uma guilda.")
            return
        if membro["cargo"] == "lider":
            await ctx.send("Lideres nao podem sair diretamente. Transfira a lideranca ou apague manualmente depois.")
            return
        db.execute("DELETE FROM guild_membros WHERE user_id = ?", (ctx.author.id,))
        db.commit()
    salvar_player(ctx.author.id, guild_id=None)
    await ctx.send("Voce saiu da guilda.")


@guilda.command(name="perfil")
async def guilda_perfil(ctx, *, nome: str = None):
    with abrir_db() as db:
        if nome:
            guild = db.execute("SELECT * FROM guildas WHERE lower(nome) = lower(?)", (nome[:32],)).fetchone()
        else:
            guild = db.execute(
                """
                SELECT g.*
                FROM guild_membros gm
                JOIN guildas g ON g.id = gm.guild_id
                WHERE gm.user_id = ?
                """,
                (ctx.author.id,),
            ).fetchone()
        if not guild:
            await ctx.send("Guilda nao encontrada. Use `!guilda criar Nome`.")
            return
        membros = db.execute("SELECT COUNT(*) AS total FROM guild_membros WHERE guild_id = ?", (guild["id"],)).fetchone()["total"]
    embed = embed_padrao(f"🏰 {guild['nome']}", cor=discord.Color.dark_blue())
    embed.add_field(name="Nivel", value=str(guild["nivel"]), inline=True)
    embed.add_field(name="Membros", value=str(membros), inline=True)
    embed.add_field(name="Ouro", value=str(guild["ouro"]), inline=True)
    embed.add_field(name="Guerras", value=f"{guild['vitorias']}V/{guild['derrotas']}D", inline=True)
    embed.add_field(name="Buff coletivo", value=f"+{min(12, int(guild['nivel']) * 2)} defesa", inline=True)
    await ctx.send(embed=embed)


@guilda.command(name="membros")
async def guilda_membros(ctx):
    with abrir_db() as db:
        guild = db.execute(
            """
            SELECT g.*
            FROM guild_membros gm
            JOIN guildas g ON g.id = gm.guild_id
            WHERE gm.user_id = ?
            """,
            (ctx.author.id,),
        ).fetchone()
        if not guild:
            await ctx.send("Voce nao esta em uma guilda.")
            return
        rows = db.execute(
            """
            SELECT p.nome, gm.cargo, p.nivel, p.classe
            FROM guild_membros gm
            LEFT JOIN players p ON p.user_id = gm.user_id
            WHERE gm.guild_id = ?
            ORDER BY CASE gm.cargo WHEN 'lider' THEN 0 ELSE 1 END, p.nivel DESC
            LIMIT 30
            """,
            (guild["id"],),
        ).fetchall()
    linhas = [f"**{row['nome'] or '???'}** | {row['cargo']} | Nv `{row['nivel'] or 1}` | {row['classe'] or 'sem classe'}" for row in rows]
    await ctx.send(embed=embed_padrao(f"🏰 Membros de {guild['nome']}", "\n".join(linhas), discord.Color.dark_blue()))


@guilda.command(name="canal", aliases=["chat"])
async def guilda_canal(ctx):
    if not ctx.guild:
        await ctx.send("Esse comando precisa ser usado dentro de um servidor.")
        return
    with abrir_db() as db:
        guild = db.execute(
            """
            SELECT g.*
            FROM guild_membros gm
            JOIN guildas g ON g.id = gm.guild_id
            WHERE gm.user_id = ?
            """,
            (ctx.author.id,),
        ).fetchone()
        if not guild:
            await ctx.send("Voce nao esta em uma guilda.")
            return
        membros = db.execute("SELECT user_id FROM guild_membros WHERE guild_id = ?", (guild["id"],)).fetchall()

    nome_canal = "guilda-" + normalizar(guild["nome"]).replace("_", "-")[:42]
    existente = discord.utils.get(ctx.guild.text_channels, name=nome_canal)
    if existente:
        await ctx.send(f"💬 Canal privado da guilda: {existente.mention}")
        return

    overwrites = {
        ctx.guild.default_role: discord.PermissionOverwrite(view_channel=False),
        ctx.guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
    }
    for row in membros:
        membro = ctx.guild.get_member(int(row["user_id"]))
        if membro:
            overwrites[membro] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)

    try:
        canal = await ctx.guild.create_text_channel(
            nome_canal,
            overwrites=overwrites,
            topic=f"Chat privado da guilda {guild['nome']} em Eclipse Legends.",
            reason="Canal privado de guilda criado pelo bot Eclipse Legends.",
        )
    except discord.Forbidden:
        await ctx.send("Nao consegui criar o canal. Preciso da permissao `Gerenciar Canais`.")
        return
    await ctx.send(f"💬 Canal privado criado: {canal.mention}")


@guilda.command(name="doar")
async def guilda_doar(ctx, valor: int = None):
    player = pegar_player(ctx.author.id)
    if not player:
        await ctx.send(exigir_player_msg())
        return
    if valor is None or valor <= 0:
        await ctx.send("Use: `!guilda doar 100`.")
        return
    if int(player["ouro"]) < valor:
        await ctx.send("Ouro insuficiente.")
        return
    with abrir_db() as db:
        membro = db.execute("SELECT guild_id FROM guild_membros WHERE user_id = ?", (ctx.author.id,)).fetchone()
        if not membro:
            await ctx.send("Voce nao esta em uma guilda.")
            return
        db.execute("UPDATE guildas SET ouro = ouro + ?, xp = xp + ? WHERE id = ?", (valor, valor // 2, membro["guild_id"]))
        guild = db.execute("SELECT nivel, xp FROM guildas WHERE id = ?", (membro["guild_id"],)).fetchone()
        if int(guild["xp"]) >= int(guild["nivel"]) * 1000:
            db.execute("UPDATE guildas SET nivel = nivel + 1, xp = 0 WHERE id = ?", (membro["guild_id"],))
        db.commit()
    salvar_player(ctx.author.id, ouro=int(player["ouro"]) - valor)
    await ctx.send(f"🏰 Doacao de `{valor}` ouro enviada para a guilda.")


@guilda.command(name="ranking")
async def guilda_ranking(ctx):
    with abrir_db() as db:
        rows = db.execute("SELECT nome, nivel, vitorias, ouro FROM guildas ORDER BY nivel DESC, vitorias DESC, ouro DESC LIMIT 10").fetchall()
    if not rows:
        await ctx.send("Ainda nao ha guildas.")
        return
    linhas = [f"**{i}. {row['nome']}** | Nv `{row['nivel']}` | Guerras `{row['vitorias']}` | Ouro `{row['ouro']}`" for i, row in enumerate(rows, 1)]
    await ctx.send(embed=embed_padrao("🏰 Ranking de Guildas", "\n".join(linhas), discord.Color.dark_blue()))


@guilda.command(name="guerra")
async def guilda_guerra(ctx, *, nome: str = None):
    if not nome:
        await ctx.send("Use: `!guilda guerra Nome da Guilda`.")
        return
    with abrir_db() as db:
        minha = db.execute(
            """
            SELECT g.*
            FROM guild_membros gm
            JOIN guildas g ON g.id = gm.guild_id
            WHERE gm.user_id = ?
            """,
            (ctx.author.id,),
        ).fetchone()
        outra = db.execute("SELECT * FROM guildas WHERE lower(nome) = lower(?)", (nome[:32],)).fetchone()
        if not minha or not outra or minha["id"] == outra["id"]:
            await ctx.send("Guilda alvo invalida.")
            return
        poder_minha = int(minha["nivel"]) * 100 + int(minha["ouro"]) // 20 + random.randint(1, 200)
        poder_outra = int(outra["nivel"]) * 100 + int(outra["ouro"]) // 20 + random.randint(1, 200)
        venceu = poder_minha >= poder_outra
        db.execute("UPDATE guildas SET vitorias = vitorias + ?, derrotas = derrotas + ? WHERE id = ?", (1 if venceu else 0, 0 if venceu else 1, minha["id"]))
        db.execute("UPDATE guildas SET vitorias = vitorias + ?, derrotas = derrotas + ? WHERE id = ?", (0 if venceu else 1, 1 if venceu else 0, outra["id"]))
        db.commit()
    await ctx.send(f"⚔️ Guerra: **{minha['nome']}** ({poder_minha}) vs **{outra['nome']}** ({poder_outra})\nResultado: **{'vitoria' if venceu else 'derrota'}**.")


# =========================
# BOSS MUNDIAL E EVOLUCAO
# =========================

def spawn_world_boss(force=False):
    nomes = ["Astaroth, Devorador do Eclipse", "Serafim Negro", "Hydra do Vazio", "Rei Demônio"]
    with abrir_db() as db:
        atual = db.execute("SELECT * FROM world_boss WHERE id = 1").fetchone()
        if atual and atual["ativo"] and not force:
            try:
                expira = datetime.fromisoformat(atual["expira_em"])
                if expira > datetime.utcnow():
                    return atual
            except ValueError:
                pass
        nivel = random.randint(8, 30)
        hp = 5000 + nivel * 850
        expira = (datetime.utcnow() + timedelta(hours=12)).isoformat(timespec="seconds")
        db.execute("DELETE FROM world_boss_damage WHERE boss_id = 1")
        db.execute(
            """
            INSERT OR REPLACE INTO world_boss(id, nome, nivel, hp, hp_max, ativo, expira_em)
            VALUES (1, ?, ?, ?, ?, 1, ?)
            """,
            (random.choice(nomes), nivel, hp, hp, expira),
        )
        db.commit()
        return db.execute("SELECT * FROM world_boss WHERE id = 1").fetchone()


@bot.group(name="boss", invoke_without_command=True)
async def boss(ctx):
    await boss_status.callback(ctx)


@boss.command(name="status")
async def boss_status(ctx):
    boss_row = spawn_world_boss(False)
    with abrir_db() as db:
        danos = db.execute(
            """
            SELECT p.nome, d.dano
            FROM world_boss_damage d
            LEFT JOIN players p ON p.user_id = d.user_id
            WHERE d.boss_id = 1
            ORDER BY d.dano DESC
            LIMIT 5
            """
        ).fetchall()
    linhas = [f"**{boss_row['nome']}** | nivel `{boss_row['nivel']}`", f"HP `{boss_row['hp']}/{boss_row['hp_max']}`\n{barra(boss_row['hp'], boss_row['hp_max'], 18)}"]
    if danos:
        linhas.append("\nRanking de dano:")
        linhas.extend(f"**{i}. {row['nome'] or '???'}** - `{row['dano']}`" for i, row in enumerate(danos, 1))
    linhas.append("\nAtaque com `!boss atacar`.")
    await ctx.send(embed=embed_padrao("👑 Boss Mundial", "\n".join(linhas), discord.Color.red()))


@boss.command(name="atacar")
async def boss_atacar(ctx):
    player = pegar_player(ctx.author.id)
    if not player:
        await ctx.send(exigir_player_msg())
        return
    if int(player["energia"]) < 2:
        await ctx.send("Voce precisa de 2 energia para atacar o boss mundial.")
        return
    boss_row = spawn_world_boss(False)
    if not boss_row["ativo"] or boss_row["hp"] <= 0:
        boss_row = spawn_world_boss(True)
    stats = stats_efetivos(player)
    dano = int((poder_principal(player, stats) + stats["sorte"] + random.randint(20, 80)) * (1 + int(player["nivel"]) / 80))
    novo_hp = max(0, int(boss_row["hp"]) - dano)
    salvar_player(ctx.author.id, energia=int(player["energia"]) - 2, boss_damage=int(player["boss_damage"] or 0) + dano)
    finalizado = novo_hp <= 0
    with abrir_db() as db:
        db.execute("UPDATE world_boss SET hp = ?, ativo = ? WHERE id = 1", (novo_hp, 0 if finalizado else 1))
        db.execute(
            """
            INSERT INTO world_boss_damage(boss_id, user_id, dano)
            VALUES (1, ?, ?)
            ON CONFLICT(boss_id, user_id) DO UPDATE SET dano = dano + excluded.dano
            """,
            (ctx.author.id, dano),
        )
        rankings = db.execute(
            "SELECT user_id, dano FROM world_boss_damage WHERE boss_id = 1 ORDER BY dano DESC LIMIT 10"
        ).fetchall()
        db.commit()
    texto = f"🔥 Voce causou **{dano}** de dano em **{boss_row['nome']}**.\nHP restante: `{novo_hp}/{boss_row['hp_max']}`."
    if finalizado:
        texto += "\n\n👑 Boss mundial derrotado! Recompensas:"
        for pos, row in enumerate(rankings, 1):
            premio_xp = max(80, int(900 / pos))
            premio_ouro = max(90, int(1200 / pos))
            aplicar_xp(row["user_id"], premio_xp, premio_ouro)
            alvo = pegar_player(row["user_id"])
            texto += f"\n**{pos}. {alvo['nome'] if alvo else row['user_id']}** ganhou `{premio_xp}` XP e `{premio_ouro}` ouro."
        spawn_world_boss(True)
    await ctx.send(embed=embed_padrao("👑 Ataque ao Boss", resumir_lista(texto), discord.Color.red()))


@bot.command(name="evoluir")
async def evoluir(ctx):
    player = pegar_player(ctx.author.id)
    if not player:
        await ctx.send(exigir_player_msg())
        return
    if player["classe_avancada"] != "Nenhuma":
        await ctx.send(f"Voce ja evoluiu para **{player['classe_avancada']}**.")
        return
    if int(player["nivel"]) < 30:
        await ctx.send("Classe avancada libera no nivel 30.")
        return
    avancada = CLASSES_RPG[normalizar(player["classe"])]["avancada"]
    salvar_player(ctx.author.id, classe_avancada=avancada, pontos=int(player["pontos"]) + 10)
    await ctx.send(f"✨ Classe avancada desbloqueada: **{avancada}**. Voce ganhou 10 pontos.")


@bot.command(name="transformar")
async def transformar(ctx, forma: str = "Eclipse"):
    player = pegar_player(ctx.author.id)
    if not player:
        await ctx.send(exigir_player_msg())
        return
    if int(player["nivel"]) < 20:
        await ctx.send("Transformacoes liberam no nivel 20.")
        return
    forma_key = forma.title()
    if forma_key not in ("Eclipse", "Guardiao"):
        await ctx.send("Formas disponiveis: `Eclipse` ou `Guardiao`.")
        return
    salvar_player(ctx.author.id, transformacao=forma_key)
    await ctx.send(f"🧬 Transformacao ativa: **{forma_key}**.")


@bot.command(name="reencarnar")
async def reencarnar(ctx):
    player = pegar_player(ctx.author.id)
    if not player:
        await ctx.send(exigir_player_msg())
        return
    if int(player["nivel"]) < 50:
        await ctx.send("Reencarnacao exige nivel 50.")
        return
    reinc = int(player["reincarnacoes"] or 0) + 1
    salvar_player(
        ctx.author.id,
        nivel=1,
        xp=0,
        pontos=15 + reinc * 5,
        reincarnacoes=reinc,
        hp=int(player["hp_max"]),
        mana=int(player["mana_max"]),
        classe_avancada="Nenhuma",
        transformacao="Nenhuma",
    )
    await ctx.send(f"🧬 Reencarnacao concluida. Resetou para nivel 1 com bonus permanente. Total: `{reinc}`.")


@bot.command(name="ranking")
async def ranking(ctx, tipo: str = "nivel"):
    tipo = normalizar(tipo)
    ordenacoes = {
        "nivel": "nivel DESC, xp DESC, ouro DESC",
        "ouro": "ouro DESC, nivel DESC",
        "pvp": "pvp_vitorias DESC, pvp_derrotas ASC, nivel DESC",
        "boss": "boss_damage DESC, nivel DESC",
    }
    order = ordenacoes.get(tipo, ordenacoes["nivel"])
    with abrir_db() as db:
        rows = db.execute(
            f"""
            SELECT nome, classe, nivel, xp, ouro, rank, pvp_vitorias, pvp_derrotas, boss_damage
            FROM players
            ORDER BY {order}
            LIMIT 10
            """
        ).fetchall()
    if not rows:
        await ctx.send("Ainda nao ha jogadores registrados.")
        return
    linhas = []
    for i, row in enumerate(rows, 1):
        if tipo == "pvp":
            extra = f"Rank `{row['rank']}` | `{row['pvp_vitorias']}V/{row['pvp_derrotas']}D`"
        elif tipo == "ouro":
            extra = f"Ouro `{row['ouro']}`"
        elif tipo == "boss":
            extra = f"Dano boss `{row['boss_damage']}`"
        else:
            extra = f"Nv `{row['nivel']}` | XP `{row['xp']}` | Ouro `{row['ouro']}`"
        linhas.append(f"**{i}. {row['nome']}** | {formatar_nome_classe(row['classe'])} | {extra}")
    await ctx.send(embed=embed_padrao(f"🏆 Ranking {tipo}", "\n".join(linhas), discord.Color.gold()))


