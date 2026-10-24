# Arquivo extraido de bot.py para manter o projeto organizado.
from .core import *

# =========================
# BANCO DE DADOS
# =========================

def conectar():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db


@contextmanager
def abrir_db():
    db = conectar()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def colunas_tabela(db, tabela):
    return {row["name"] for row in db.execute(f"PRAGMA table_info({tabela})")}


def adicionar_coluna(db, tabela, coluna, definicao):
    if coluna not in colunas_tabela(db, tabela):
        db.execute(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {definicao}")


def criar_db():
    db = conectar()
    cur = db.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS players (
            user_id INTEGER PRIMARY KEY,
            nome TEXT NOT NULL,
            classe TEXT NOT NULL,
            raca TEXT DEFAULT 'humano',
            origem TEXT DEFAULT 'exilado',
            nivel INTEGER DEFAULT 1,
            xp INTEGER DEFAULT 0,
            ouro INTEGER DEFAULT 100,
            hp INTEGER DEFAULT 100,
            hp_max INTEGER DEFAULT 100,
            mana INTEGER DEFAULT 50,
            mana_max INTEGER DEFAULT 50,
            atk INTEGER DEFAULT 10,
            defesa INTEGER DEFAULT 5,
            forca INTEGER DEFAULT 5,
            agilidade INTEGER DEFAULT 5,
            inteligencia INTEGER DEFAULT 5,
            sorte INTEGER DEFAULT 5,
            pontos INTEGER DEFAULT 0,
            pocao INTEGER DEFAULT 3,
            energia INTEGER DEFAULT 10,
            energia_max INTEGER DEFAULT 10,
            ultima_daily TEXT DEFAULT 'nunca',
            arma TEXT DEFAULT 'Nenhuma',
            armadura TEXT DEFAULT 'Nenhuma',
            monstros_derrotados INTEGER DEFAULT 0,
            monstro_derrotado INTEGER DEFAULT 0,
            rank TEXT DEFAULT 'bronze',
            pvp_vitorias INTEGER DEFAULT 0,
            pvp_derrotas INTEGER DEFAULT 0,
            reincarnacoes INTEGER DEFAULT 0,
            transformacao TEXT DEFAULT 'Nenhuma',
            classe_avancada TEXT DEFAULT 'Nenhuma',
            historia_etapa INTEGER DEFAULT 0,
            guild_id INTEGER,
            boss_damage INTEGER DEFAULT 0,
            ultima_quest_daily TEXT DEFAULT 'nunca',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    for coluna, definicao in {
        "raca": "TEXT DEFAULT 'humano'",
        "origem": "TEXT DEFAULT 'exilado'",
        "mana": "INTEGER DEFAULT 50",
        "mana_max": "INTEGER DEFAULT 50",
        "forca": "INTEGER DEFAULT 5",
        "agilidade": "INTEGER DEFAULT 5",
        "inteligencia": "INTEGER DEFAULT 5",
        "sorte": "INTEGER DEFAULT 5",
        "pontos": "INTEGER DEFAULT 0",
        "monstros_derrotados": "INTEGER DEFAULT 0",
        "monstro_derrotado": "INTEGER DEFAULT 0",
        "rank": "TEXT DEFAULT 'bronze'",
        "pvp_vitorias": "INTEGER DEFAULT 0",
        "pvp_derrotas": "INTEGER DEFAULT 0",
        "reincarnacoes": "INTEGER DEFAULT 0",
        "transformacao": "TEXT DEFAULT 'Nenhuma'",
        "classe_avancada": "TEXT DEFAULT 'Nenhuma'",
        "historia_etapa": "INTEGER DEFAULT 0",
        "guild_id": "INTEGER",
        "boss_damage": "INTEGER DEFAULT 0",
        "ultima_quest_daily": "TEXT DEFAULT 'nunca'",
        "created_at": "TEXT",
        "updated_at": "TEXT",
    }.items():
        adicionar_coluna(db, "players", coluna, definicao)

    if "monstro_derrotado" in colunas_tabela(db, "players"):
        cur.execute(
            """
            UPDATE players
            SET monstros_derrotados = COALESCE(NULLIF(monstros_derrotados, 0), monstro_derrotado, 0)
            WHERE COALESCE(monstros_derrotados, 0) = 0
            """
        )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS inventario (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            item_key TEXT NOT NULL,
            nome TEXT NOT NULL,
            tipo TEXT NOT NULL,
            raridade TEXT NOT NULL,
            quantidade INTEGER DEFAULT 1,
            equipado INTEGER DEFAULT 0,
            forca INTEGER DEFAULT 0,
            defesa_bonus INTEGER DEFAULT 0,
            agilidade INTEGER DEFAULT 0,
            inteligencia INTEGER DEFAULT 0,
            sorte INTEGER DEFAULT 0,
            hp_bonus INTEGER DEFAULT 0,
            mana_bonus INTEGER DEFAULT 0,
            valor INTEGER DEFAULT 0,
            descricao TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, item_key)
        )
        """
    )
    cur.execute("CREATE INDEX IF NOT EXISTS idx_inventario_user ON inventario(user_id)")

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS guildas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT UNIQUE NOT NULL,
            dono_id INTEGER NOT NULL,
            nivel INTEGER DEFAULT 1,
            xp INTEGER DEFAULT 0,
            ouro INTEGER DEFAULT 0,
            vitorias INTEGER DEFAULT 0,
            derrotas INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS guild_membros (
            user_id INTEGER PRIMARY KEY,
            guild_id INTEGER NOT NULL,
            cargo TEXT DEFAULT 'membro',
            joined_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS quests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            quest_key TEXT NOT NULL,
            titulo TEXT NOT NULL,
            tipo TEXT NOT NULL,
            progresso INTEGER DEFAULT 0,
            alvo INTEGER NOT NULL,
            recompensa_xp INTEGER DEFAULT 0,
            recompensa_ouro INTEGER DEFAULT 0,
            ativa INTEGER DEFAULT 1,
            concluida INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cur.execute("CREATE INDEX IF NOT EXISTS idx_quests_user ON quests(user_id)")

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS mercado (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            seller_id INTEGER NOT NULL,
            item_key TEXT NOT NULL,
            nome TEXT NOT NULL,
            tipo TEXT NOT NULL,
            raridade TEXT NOT NULL,
            quantidade INTEGER DEFAULT 1,
            preco INTEGER NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS world_boss (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            nome TEXT NOT NULL,
            nivel INTEGER NOT NULL,
            hp INTEGER NOT NULL,
            hp_max INTEGER NOT NULL,
            ativo INTEGER DEFAULT 1,
            expira_em TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS world_boss_damage (
            boss_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            dano INTEGER DEFAULT 0,
            PRIMARY KEY (boss_id, user_id)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS habilidades (
            user_id INTEGER NOT NULL,
            skill_key TEXT NOT NULL,
            unlocked_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(user_id, skill_key)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS batalhas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            tipo TEXT NOT NULL,
            oponente TEXT NOT NULL,
            venceu INTEGER DEFAULT 0,
            dano INTEGER DEFAULT 0,
            xp INTEGER DEFAULT 0,
            ouro INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS gacha_users (
            user_id INTEGER PRIMARY KEY,
            cristais INTEGER DEFAULT 0,
            tickets INTEGER DEFAULT 0,
            pity INTEGER DEFAULT 0,
            total_pulls INTEGER DEFAULT 0,
            ultima_checkin TEXT DEFAULT 'nunca',
            streak INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS gacha_collection (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            char_key TEXT NOT NULL,
            nome TEXT NOT NULL,
            anime TEXT NOT NULL,
            imagem TEXT DEFAULT '',
            raridade TEXT NOT NULL,
            quantidade INTEGER DEFAULT 1,
            first_obtained TEXT DEFAULT CURRENT_TIMESTAMP,
            last_obtained TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, char_key)
        )
        """
    )
    cur.execute("CREATE INDEX IF NOT EXISTS idx_gacha_collection_user ON gacha_collection(user_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_gacha_collection_rarity ON gacha_collection(raridade)")

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS gacha_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            char_key TEXT NOT NULL,
            nome TEXT NOT NULL,
            anime TEXT NOT NULL,
            raridade TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cur.execute("CREATE INDEX IF NOT EXISTS idx_gacha_history_user ON gacha_history(user_id)")

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS social_users (
            user_id INTEGER PRIMARY KEY,
            xp INTEGER DEFAULT 0,
            nivel INTEGER DEFAULT 1,
            reputacao INTEGER DEFAULT 0,
            mensagens INTEGER DEFAULT 0,
            call_seconds INTEGER DEFAULT 0,
            moedas INTEGER DEFAULT 0,
            titulo TEXT DEFAULT 'Sem titulo',
            bio TEXT DEFAULT '',
            profile_color TEXT DEFAULT '#ff66cc',
            profile_icon TEXT DEFAULT '',
            profile_bg TEXT DEFAULT '',
            frame TEXT DEFAULT '',
            aura TEXT DEFAULT 'Neutra',
            reports INTEGER DEFAULT 0,
            last_message_at TEXT DEFAULT '',
            last_message_hash TEXT DEFAULT '',
            repeated_count INTEGER DEFAULT 0,
            daily_xp INTEGER DEFAULT 0,
            daily_key TEXT DEFAULT '',
            weekly_xp INTEGER DEFAULT 0,
            weekly_key TEXT DEFAULT '',
            monthly_xp INTEGER DEFAULT 0,
            monthly_key TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cur.execute("CREATE INDEX IF NOT EXISTS idx_social_users_rank ON social_users(nivel DESC, xp DESC)")

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS social_rep_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            giver_id INTEGER NOT NULL,
            receiver_id INTEGER NOT NULL,
            tipo TEXT NOT NULL,
            valor INTEGER NOT NULL,
            suspeito INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cur.execute("CREATE INDEX IF NOT EXISTS idx_social_rep_pair ON social_rep_log(giver_id, receiver_id, created_at)")

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS social_achievements (
            user_id INTEGER NOT NULL,
            achievement_key TEXT NOT NULL,
            nome TEXT NOT NULL,
            titulo TEXT DEFAULT '',
            unlocked_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(user_id, achievement_key)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS social_titles (
            user_id INTEGER NOT NULL,
            titulo TEXT NOT NULL,
            unlocked_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(user_id, titulo)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS social_inventory (
            user_id INTEGER NOT NULL,
            item_key TEXT NOT NULL,
            tipo TEXT NOT NULL,
            valor TEXT DEFAULT '',
            acquired_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(user_id, item_key)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS social_voice_sessions (
            user_id INTEGER PRIMARY KEY,
            guild_id INTEGER DEFAULT 0,
            channel_id INTEGER DEFAULT 0,
            started_at TEXT NOT NULL
        )
        """
    )

    cur.execute(
        """
        UPDATE players
        SET
            raca = COALESCE(raca, 'humano'),
            origem = COALESCE(origem, 'exilado'),
            mana = COALESCE(mana, mana_max, 50),
            mana_max = COALESCE(mana_max, 50),
            forca = COALESCE(forca, MAX(5, atk / 2)),
            agilidade = COALESCE(agilidade, 5),
            inteligencia = COALESCE(inteligencia, CASE WHEN classe IN ('mago', 'necromante') THEN atk ELSE 5 END),
            sorte = COALESCE(sorte, 5),
            pontos = COALESCE(pontos, 0),
            rank = COALESCE(rank, 'bronze'),
            created_at = COALESCE(created_at, CURRENT_TIMESTAMP),
            updated_at = CURRENT_TIMESTAMP
        """
    )

    legados = cur.execute(
        """
        SELECT *
        FROM players
        WHERE COALESCE(forca, 5) = 5
          AND COALESCE(agilidade, 5) = 5
          AND COALESCE(inteligencia, 5) = 5
          AND COALESCE(sorte, 5) = 5
          AND COALESCE(mana_max, 50) = 50
        """
    ).fetchall()
    for legado in legados:
        classe_key = normalizar(legado["classe"])
        raca_key = normalizar(legado["raca"] or "humano")
        classe_info = CLASSES_RPG.get(classe_key)
        raca_info = RACAS_RPG.get(raca_key, RACAS_RPG["humano"])
        if not classe_info:
            continue

        hp_base = max(int(legado["hp_max"] or 1), classe_info["hp"] + raca_info["hp"])
        mana_base = max(int(legado["mana_max"] or 1), classe_info["mana"] + raca_info["mana"])
        defesa_base = max(int(legado["defesa"] or 1), classe_info["defesa"] + raca_info["defesa"])
        forca_base = max(1, classe_info["forca"] + raca_info["forca"])
        agilidade_base = max(1, classe_info["agilidade"] + raca_info["agilidade"])
        inteligencia_base = max(1, classe_info["inteligencia"] + raca_info["inteligencia"])
        sorte_base = max(1, classe_info["sorte"] + raca_info["sorte"])
        pontos_base = max(int(legado["pontos"] or 0), 3 + int(raca_info.get("pontos", 0)))

        cur.execute(
            """
            UPDATE players
            SET
                raca = ?,
                hp = MIN(COALESCE(hp, ?), ?),
                hp_max = ?,
                mana = ?,
                mana_max = ?,
                defesa = ?,
                forca = ?,
                agilidade = ?,
                inteligencia = ?,
                sorte = ?,
                pontos = ?,
                atk = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
            """,
            (
                raca_key,
                hp_base,
                hp_base,
                hp_base,
                mana_base,
                mana_base,
                defesa_base,
                forca_base,
                agilidade_base,
                inteligencia_base,
                sorte_base,
                pontos_base,
                forca_base * 2 + inteligencia_base,
                legado["user_id"],
            ),
        )

    db.commit()
    db.close()
