# Arquivo extraido de bot.py para manter o projeto organizado.
from .core import *
from .database import *

# =========================
# HELPERS DO GACHA
# =========================

def normalizar_raridade_gacha(raridade):
    chave = normalizar(raridade)
    aliases = {
        "epico": "epico",
        "épico": "epico",
        "lendario": "lendario",
        "lendário": "lendario",
        "mitico": "mitico",
        "mítico": "mitico",
    }
    return aliases.get(chave, chave if chave in GACHA_RARIDADES else "comum")


def nome_raridade_gacha(raridade):
    chave = normalizar_raridade_gacha(raridade)
    info = GACHA_RARIDADES[chave]
    return f"{info['emoji']} {info['nome']}"


def chave_personagem_gacha(nome, anime, imagem=""):
    base = f"{nome}|{anime}|{imagem}".encode("utf-8", errors="ignore")
    return hashlib.sha1(base).hexdigest()[:18]


def preparar_catalogo_gacha(dados):
    personagens = []
    for item in dados:
        if not isinstance(item, dict):
            continue
        nome = str(item.get("nome") or "").strip()
        anime = str(item.get("anime") or "").strip()
        imagem = str(item.get("imagem") or "").strip()
        if not nome or not anime:
            continue
        raridade = normalizar_raridade_gacha(item.get("raridade", "comum"))
        personagens.append(
            {
                "key": chave_personagem_gacha(nome, anime, imagem),
                "nome": nome[:120],
                "anime": anime[:160],
                "imagem": imagem,
                "raridade": raridade,
            }
        )
    return personagens


def carregar_catalogo_gacha(force=False):
    if GACHA_CATALOGO_CACHE["loaded"] and not force:
        return GACHA_CATALOGO_CACHE["personagens"]

    dados = None
    erro = None
    try:
        req = urllib.request.Request(GACHA_LIBRARY_URL, headers={"User-Agent": "Hyori-Eclipse-Legends/1.0"})
        with urllib.request.urlopen(req, timeout=25) as resposta:
            dados = json.loads(resposta.read().decode("utf-8-sig"))
        GACHA_CACHE_PATH.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        erro = str(exc)
        if GACHA_CACHE_PATH.exists():
            try:
                dados = json.loads(GACHA_CACHE_PATH.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                dados = None

    personagens = preparar_catalogo_gacha(dados if isinstance(dados, list) else [])
    por_raridade = {raridade: [] for raridade in GACHA_RARIDADES}
    for personagem in personagens:
        por_raridade.setdefault(personagem["raridade"], []).append(personagem)

    GACHA_CATALOGO_CACHE.update(
        {
            "loaded": True,
            "personagens": personagens,
            "por_raridade": por_raridade,
            "erro": erro,
        }
    )
    return personagens


def pegar_gacha_user(user_id):
    with abrir_db() as db:
        db.execute("INSERT OR IGNORE INTO gacha_users(user_id) VALUES (?)", (int(user_id),))
        return db.execute("SELECT * FROM gacha_users WHERE user_id = ?", (int(user_id),)).fetchone()


def salvar_gacha_user(user_id, **campos):
    if not campos:
        return
    campos["updated_at"] = datetime.utcnow().isoformat(timespec="seconds")
    partes = ", ".join(f"{campo} = ?" for campo in campos)
    valores = list(campos.values()) + [int(user_id)]
    with abrir_db() as db:
        db.execute(f"UPDATE gacha_users SET {partes} WHERE user_id = ?", valores)


def adicionar_personagem_gacha(user_id, personagem):
    with abrir_db() as db:
        db.execute(
            """
            INSERT INTO gacha_collection(user_id, char_key, nome, anime, imagem, raridade, quantidade)
            VALUES (?, ?, ?, ?, ?, ?, 1)
            ON CONFLICT(user_id, char_key) DO UPDATE SET
                quantidade = quantidade + 1,
                last_obtained = CURRENT_TIMESTAMP
            """,
            (
                int(user_id),
                personagem["key"],
                personagem["nome"],
                personagem["anime"],
                personagem.get("imagem", ""),
                personagem["raridade"],
            ),
        )
        db.execute(
            """
            INSERT INTO gacha_history(user_id, char_key, nome, anime, raridade)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                int(user_id),
                personagem["key"],
                personagem["nome"],
                personagem["anime"],
                personagem["raridade"],
            ),
        )


def estatisticas_gacha(user_id):
    with abrir_db() as db:
        row = db.execute(
            """
            SELECT
                COUNT(*) AS unicos,
                COALESCE(SUM(quantidade), 0) AS total,
                COALESCE(SUM(CASE WHEN raridade = 'mitico' THEN 1 ELSE 0 END), 0) AS miticos,
                COALESCE(SUM(CASE WHEN raridade = 'lendario' THEN 1 ELSE 0 END), 0) AS lendarios
            FROM gacha_collection
            WHERE user_id = ?
            """,
            (int(user_id),),
        ).fetchone()
    return row


def sortear_raridade_gacha(pity, garantir_epico=False):
    if int(pity) >= GACHA_PITY_LIMIT:
        return random.choices(["lendario", "mitico"], weights=[78, 22], k=1)[0]

    pesos = {}
    for raridade, info in GACHA_RARIDADES.items():
        pesos[raridade] = float(info["peso"])

    if int(pity) >= 75:
        bonus = (int(pity) - 74) * 0.42
        pesos["lendario"] += bonus
        pesos["mitico"] += bonus * 0.18

    if garantir_epico:
        pesos["comum"] = 0
        pesos["raro"] = 0

    nomes = list(pesos)
    valores = [pesos[nome] for nome in nomes]
    return random.choices(nomes, weights=valores, k=1)[0]


def sortear_personagem_gacha(pity, garantir_epico=False):
    carregar_catalogo_gacha(False)
    raridade = sortear_raridade_gacha(pity, garantir_epico)
    candidatos = GACHA_CATALOGO_CACHE["por_raridade"].get(raridade) or GACHA_CATALOGO_CACHE["personagens"]
    if not candidatos:
        return None
    return random.choice(candidatos)


def cor_gacha(raridade):
    return GACHA_RARIDADES[normalizar_raridade_gacha(raridade)]["cor"]


def rank_raridade_gacha(raridade):
    return GACHA_RARIDADES[normalizar_raridade_gacha(raridade)]["rank"]


def valor_venda_gacha(raridade):
    return GACHA_SELL_VALUES[normalizar_raridade_gacha(raridade)]


def formatar_resultados_gacha(resultados):
    linhas = []
    for i, personagem in enumerate(resultados, 1):
        linhas.append(
            f"`{i:02}` {nome_raridade_gacha(personagem['raridade'])} **{personagem['nome']}** - {personagem['anime']}"
        )
    return linhas


def embed_carta_gacha(row, indice, total, dono_nome=None, filtro=None):
    titulo = f"🎴 {row['nome']}"
    descricao = f"{nome_raridade_gacha(row['raridade'])}\nAnime: **{row['anime']}**"
    embed = embed_padrao(titulo, descricao, cor_gacha(row["raridade"]))
    embed.add_field(name="Quantidade", value=f"`x{row['quantidade']}`", inline=True)
    embed.add_field(name="Duplicatas vendiveis", value=f"`{max(0, int(row['quantidade']) - 1)}`", inline=True)
    embed.add_field(name="Valor da duplicata", value=f"💎 `{valor_venda_gacha(row['raridade'])}`", inline=True)
    if dono_nome:
        embed.add_field(name="Dono", value=dono_nome, inline=True)
    if filtro:
        embed.add_field(name="Filtro", value=filtro, inline=True)
    embed.set_footer(text=f"Eclipse Legends Gacha | Carta {indice + 1}/{total}")
    if row["imagem"]:
        embed.set_image(url=row["imagem"])
    return embed


class GachaCollectionView(discord.ui.View):
    def __init__(self, owner_id, rows, dono_nome=None, filtro=None):
        super().__init__(timeout=180)
        self.owner_id = int(owner_id)
        self.rows = rows
        self.index = 0
        self.dono_nome = dono_nome
        self.filtro = filtro
        self._atualizar_botoes()

    def _embed(self):
        return embed_carta_gacha(self.rows[self.index], self.index, len(self.rows), self.dono_nome, self.filtro)

    def _atualizar_botoes(self):
        disabled = len(self.rows) <= 1
        self.primeiro.disabled = disabled or self.index == 0
        self.anterior.disabled = disabled or self.index == 0
        self.proximo.disabled = disabled or self.index >= len(self.rows) - 1
        self.ultimo.disabled = disabled or self.index >= len(self.rows) - 1

    async def interaction_check(self, interaction):
        if int(interaction.user.id) == self.owner_id:
            return True
        await interaction.response.send_message("Essa colecao nao e sua.", ephemeral=True)
        return False

    @discord.ui.button(label="<<", style=discord.ButtonStyle.secondary)
    async def primeiro(self, interaction, button):
        self.index = 0
        self._atualizar_botoes()
        await interaction.response.edit_message(embed=self._embed(), view=self)

    @discord.ui.button(label="<", style=discord.ButtonStyle.primary)
    async def anterior(self, interaction, button):
        self.index = max(0, self.index - 1)
        self._atualizar_botoes()
        await interaction.response.edit_message(embed=self._embed(), view=self)

    @discord.ui.button(label=">", style=discord.ButtonStyle.primary)
    async def proximo(self, interaction, button):
        self.index = min(len(self.rows) - 1, self.index + 1)
        self._atualizar_botoes()
        await interaction.response.edit_message(embed=self._embed(), view=self)

    @discord.ui.button(label=">>", style=discord.ButtonStyle.secondary)
    async def ultimo(self, interaction, button):
        self.index = len(self.rows) - 1
        self._atualizar_botoes()
        await interaction.response.edit_message(embed=self._embed(), view=self)


def vender_duplicatas_por_raridade(user_id, raridade=None):
    raridade_key = normalizar_raridade_gacha(raridade) if raridade else None
    params = [int(user_id)]
    filtro = ""
    if raridade_key:
        filtro = "AND raridade = ?"
        params.append(raridade_key)

    with abrir_db() as db:
        rows = db.execute(
            f"""
            SELECT id, nome, raridade, quantidade
            FROM gacha_collection
            WHERE user_id = ? {filtro} AND quantidade > 1
            """,
            params,
        ).fetchall()
        total_copias = 0
        ganho = 0
        for row in rows:
            duplicatas = int(row["quantidade"]) - 1
            total_copias += duplicatas
            ganho += duplicatas * valor_venda_gacha(row["raridade"])
            db.execute("UPDATE gacha_collection SET quantidade = 1 WHERE id = ?", (row["id"],))
        if ganho:
            db.execute(
                "INSERT OR IGNORE INTO gacha_users(user_id) VALUES (?)",
                (int(user_id),),
            )
            db.execute(
                "UPDATE gacha_users SET cristais = cristais + ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?",
                (ganho, int(user_id)),
            )
    return {"personagens": len(rows), "copias": total_copias, "cristais": ganho, "raridade": raridade_key}


def vender_duplicata_personagem(user_id, busca, quantidade=None):
    busca_norm = normalizar(busca)
    with abrir_db() as db:
        rows = db.execute(
            """
            SELECT id, nome, anime, raridade, quantidade
            FROM gacha_collection
            WHERE user_id = ?
            ORDER BY quantidade DESC, nome ASC
            """,
            (int(user_id),),
        ).fetchall()
        candidatos = [
            row
            for row in rows
            if busca_norm in normalizar(row["nome"]) or busca_norm in normalizar(row["anime"])
        ]
        if not candidatos:
            return {"erro": "nao_encontrado"}

        row = candidatos[0]
        disponiveis = max(0, int(row["quantidade"]) - 1)
        if disponiveis <= 0:
            return {"erro": "sem_duplicata", "row": row}

        vender = disponiveis if quantidade is None else min(disponiveis, max(1, int(quantidade)))
        ganho = vender * valor_venda_gacha(row["raridade"])
        db.execute(
            "UPDATE gacha_collection SET quantidade = quantidade - ? WHERE id = ?",
            (vender, row["id"]),
        )
        db.execute("INSERT OR IGNORE INTO gacha_users(user_id) VALUES (?)", (int(user_id),))
        db.execute(
            "UPDATE gacha_users SET cristais = cristais + ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?",
            (ganho, int(user_id)),
        )
    return {"row": row, "copias": vender, "cristais": ganho}


def usuario_tem_adm_gacha(ctx):
    if not getattr(ctx, "guild", None):
        return False

    author = getattr(ctx, "author", None)
    if not author:
        return False

    perms = getattr(author, "guild_permissions", None)
    if getattr(perms, "administrator", False) or getattr(perms, "manage_guild", False):
        return True

    roles_env = os.getenv("GACHA_ADMIN_ROLES", "")
    nomes_liberados = set(GACHA_ADMIN_ROLE_NAMES)
    if roles_env.strip():
        nomes_liberados.update(normalizar(nome) for nome in roles_env.split(",") if nome.strip())

    default_role = getattr(ctx.guild, "default_role", None)
    for role in getattr(author, "roles", []) or []:
        if default_role is not None and role == default_role:
            continue
        role_nome = normalizar(getattr(role, "name", ""))
        role_perms = getattr(role, "permissions", None)
        if role_nome in nomes_liberados:
            return True
        if getattr(role_perms, "administrator", False) or getattr(role_perms, "manage_guild", False):
            return True
    return False


async def exigir_adm_gacha(ctx):
    if usuario_tem_adm_gacha(ctx):
        return True
    await ctx.send(
        "❌ Comando administrativo. Precisa de Administrador/Gerenciar Servidor ou cargo `adm`, `admin`, `staff`, `moderador` ou `gacha admin`."
    )
    return False


