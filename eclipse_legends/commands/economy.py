# Arquivo extraido de bot.py para manter o projeto organizado.
from ..core import *
from ..database import *
from ..gacha import *
from ..social import *
from ..rpg import *
from ..music import *

# =========================
# INVENTARIO E ECONOMIA
# =========================

@bot.command(name="inventario", aliases=["inv"])
async def inventario(ctx, membro: discord.Member = None):
    membro = membro or ctx.author
    player = pegar_player(membro.id)
    if not player:
        await ctx.send("Esse usuario ainda nao tem personagem.")
        return

    with abrir_db() as db:
        itens = db.execute(
            """
            SELECT item_key, nome, tipo, raridade, quantidade, equipado
            FROM inventario
            WHERE user_id = ?
            ORDER BY equipado DESC, tipo, raridade, nome
            """,
            (int(membro.id),),
        ).fetchall()

    linhas = [f"💰 Ouro: `{player['ouro']}` | 🧪 Pocoes antigas: `{player['pocao']}`"]
    if not itens:
        linhas.append("Inventario vazio.")
    for item in itens:
        eq = " [E]" if item["equipado"] else ""
        linhas.append(f"`{item['item_key']}` x{item['quantidade']} - **{item['nome']}** ({item['raridade']}/{item['tipo']}){eq}")

    await ctx.send(embed=embed_padrao(f"🎒 Inventario de {player['nome']}", resumir_lista(linhas), discord.Color.dark_teal()))


@bot.command(name="equipar")
async def equipar(ctx, *, item_nome: str = None):
    player = pegar_player(ctx.author.id)
    if not player:
        await ctx.send(exigir_player_msg())
        return
    if not item_nome:
        await ctx.send("Use: `!equipar espada_ferro`.")
        return

    item_key = normalizar(item_nome)
    with abrir_db() as db:
        item = db.execute(
            "SELECT * FROM inventario WHERE user_id = ? AND item_key = ?",
            (ctx.author.id, item_key),
        ).fetchone()
        if not item:
            await ctx.send("Voce nao possui esse item.")
            return
        if item["tipo"] not in ("arma", "armadura", "artefato"):
            await ctx.send("Esse item nao pode ser equipado.")
            return
        db.execute("UPDATE inventario SET equipado = 0 WHERE user_id = ? AND tipo = ?", (ctx.author.id, item["tipo"]))
        db.execute("UPDATE inventario SET equipado = 1 WHERE id = ?", (item["id"],))
        campos = {}
        if item["tipo"] == "arma":
            campos["arma"] = item["nome"]
        elif item["tipo"] == "armadura":
            campos["armadura"] = item["nome"]
        db.commit()
    if campos:
        salvar_player(ctx.author.id, **campos)
    await ctx.send(f"✅ Equipado: **{item['nome']}**.")


@bot.command(name="loja", aliases=["shop"])
async def loja(ctx):
    evento = evento_global()
    linhas = [f"Evento atual: **{evento['nome']}**"]
    for key in LOJA_BASE:
        item = ITENS[key]
        linhas.append(f"`{key}` - **{item['nome']}** ({item['raridade']}/{item['tipo']}) | 💰 `{item['preco']}` | {item['desc']}")
    linhas.append("\nComprar: `!comprar item quantidade`")
    await ctx.send(embed=embed_padrao("🏪 Loja Eclipse", resumir_lista(linhas), discord.Color.orange()))


@bot.command(name="comprar")
async def comprar(ctx, item_nome: str = None, quantidade: int = 1):
    player = pegar_player(ctx.author.id)
    if not player:
        await ctx.send(exigir_player_msg())
        return
    if not item_nome:
        await ctx.send("Use: `!comprar pocao_pequena 2`.")
        return

    item_key = normalizar(item_nome)
    if item_key not in ITENS or item_key not in LOJA_BASE:
        await ctx.send("Esse item nao esta na loja. Use `!loja`.")
        return
    quantidade = max(1, min(20, int(quantidade)))
    item = ITENS[item_key]
    preco = int(item["preco"]) * quantidade
    if int(player["ouro"]) < preco:
        await ctx.send(f"Ouro insuficiente. Custa `{preco}`, voce tem `{player['ouro']}`.")
        return

    salvar_player(ctx.author.id, ouro=int(player["ouro"]) - preco)
    adicionar_item(ctx.author.id, item_key, quantidade)
    await ctx.send(f"✅ Comprou **{quantidade}x {item['nome']}** por `{preco}` ouro.")


@bot.command(name="vender")
async def vender(ctx, item_nome: str = None, quantidade: int = 1):
    player = pegar_player(ctx.author.id)
    if not player:
        await ctx.send(exigir_player_msg())
        return
    if not item_nome:
        await ctx.send("Use: `!vender espada_ferro 1`.")
        return
    item_key = normalizar(item_nome)
    quantidade = max(1, min(99, int(quantidade)))

    with abrir_db() as db:
        item = db.execute(
            "SELECT * FROM inventario WHERE user_id = ? AND item_key = ?",
            (ctx.author.id, item_key),
        ).fetchone()
    if not item:
        await ctx.send("Voce nao possui esse item.")
        return
    if item["equipado"] and item["quantidade"] <= quantidade:
        await ctx.send("Desequipe ou mantenha pelo menos 1 unidade antes de vender.")
        return
    if item["quantidade"] < quantidade:
        await ctx.send("Quantidade maior que a disponivel.")
        return

    ganho = int(item["valor"]) * quantidade
    if not remover_item(ctx.author.id, item_key, quantidade):
        await ctx.send("Nao foi possivel vender esse item.")
        return
    salvar_player(ctx.author.id, ouro=int(player["ouro"]) + ganho)
    await ctx.send(f"💰 Vendeu **{quantidade}x {item['nome']}** por `{ganho}` ouro.")


@bot.group(name="mercado", invoke_without_command=True)
async def mercado(ctx):
    await mercado_listar.callback(ctx)


@mercado.command(name="listar")
async def mercado_listar(ctx):
    with abrir_db() as db:
        rows = db.execute(
            "SELECT id, seller_id, nome, item_key, raridade, tipo, quantidade, preco FROM mercado ORDER BY id DESC LIMIT 15"
        ).fetchall()
    if not rows:
        await ctx.send("O mercado esta vazio. Venda com `!mercado vender item quantidade preco`.")
        return
    linhas = []
    for row in rows:
        linhas.append(f"`#{row['id']}` **{row['nome']}** x{row['quantidade']} ({row['raridade']}/{row['tipo']}) - 💰 `{row['preco']}`")
    await ctx.send(embed=embed_padrao("📈 Mercado dos Jogadores", "\n".join(linhas), discord.Color.blue()))


@mercado.command(name="vender")
async def mercado_vender(ctx, item_nome: str = None, quantidade: int = 1, preco: int = None):
    player = pegar_player(ctx.author.id)
    if not player:
        await ctx.send(exigir_player_msg())
        return
    if not item_nome or preco is None:
        await ctx.send("Use: `!mercado vender espada_ferro 1 500`.")
        return
    item_key = normalizar(item_nome)
    quantidade = max(1, min(50, int(quantidade)))
    preco = max(1, int(preco))

    with abrir_db() as db:
        item = db.execute("SELECT * FROM inventario WHERE user_id = ? AND item_key = ?", (ctx.author.id, item_key)).fetchone()
    if not item or item["quantidade"] < quantidade:
        await ctx.send("Voce nao tem essa quantidade.")
        return
    if item["equipado"] and item["quantidade"] <= quantidade:
        await ctx.send("Nao coloque seu item equipado unico no mercado.")
        return
    if not remover_item(ctx.author.id, item_key, quantidade):
        await ctx.send("Nao foi possivel mover esse item para o mercado.")
        return
    with abrir_db() as db:
        db.execute(
            """
            INSERT INTO mercado(seller_id, item_key, nome, tipo, raridade, quantidade, preco)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (ctx.author.id, item_key, item["nome"], item["tipo"], item["raridade"], quantidade, preco),
        )
        db.commit()
    await ctx.send(f"📈 Oferta criada: **{item['nome']}** x{quantidade} por `{preco}` ouro.")


@mercado.command(name="comprar")
async def mercado_comprar(ctx, oferta_id: int = None):
    player = pegar_player(ctx.author.id)
    if not player:
        await ctx.send(exigir_player_msg())
        return
    if oferta_id is None:
        await ctx.send("Use: `!mercado comprar 3`.")
        return
    with abrir_db() as db:
        oferta = db.execute("SELECT * FROM mercado WHERE id = ?", (oferta_id,)).fetchone()
        if not oferta:
            await ctx.send("Oferta nao encontrada.")
            return
        if int(oferta["seller_id"]) == ctx.author.id:
            await ctx.send("Voce nao pode comprar sua propria oferta.")
            return
        if int(player["ouro"]) < int(oferta["preco"]):
            await ctx.send("Ouro insuficiente.")
            return
        vendedor = pegar_player(oferta["seller_id"])
        db.execute("DELETE FROM mercado WHERE id = ?", (oferta_id,))
        db.commit()

    salvar_player(ctx.author.id, ouro=int(player["ouro"]) - int(oferta["preco"]))
    if vendedor:
        salvar_player(oferta["seller_id"], ouro=int(vendedor["ouro"]) + int(oferta["preco"]))
    adicionar_item(ctx.author.id, oferta["item_key"], int(oferta["quantidade"]))
    await ctx.send(f"✅ Comprou **{oferta['nome']}** x{oferta['quantidade']} por `{oferta['preco']}` ouro.")


