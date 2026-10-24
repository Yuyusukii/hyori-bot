# Arquivo extraido de bot.py para manter o projeto organizado.
from .core import *
from .database import *

# =========================
# HELPERS DO RPG
# =========================

def pegar_player(user_id):
    with abrir_db() as db:
        return db.execute("SELECT * FROM players WHERE user_id = ?", (int(user_id),)).fetchone()


def salvar_player(user_id, **campos):
    if not campos:
        return
    campos["updated_at"] = datetime.utcnow().isoformat(timespec="seconds")
    partes = ", ".join(f"{campo} = ?" for campo in campos)
    valores = list(campos.values()) + [int(user_id)]
    with abrir_db() as db:
        db.execute(f"UPDATE players SET {partes} WHERE user_id = ?", valores)
        db.commit()


def xp_necessario(nivel):
    return int(95 + (nivel ** 1.35) * 82)


def barra(valor, maximo, tamanho=12):
    if maximo <= 0:
        return "░" * tamanho
    valor = max(0, min(valor, maximo))
    cheio = int((valor / maximo) * tamanho)
    return "█" * cheio + "░" * (tamanho - cheio)


def formatar_nome_classe(chave):
    info = CLASSES_RPG.get(normalizar(chave), {})
    return f"{info.get('emoji', '✨')} {info.get('nome', str(chave).title())}"


def formatar_nome_raca(chave):
    info = RACAS_RPG.get(normalizar(chave), {})
    return f"{info.get('emoji', '🧬')} {info.get('nome', str(chave).title())}"


def item_stats(item):
    return {
        "forca": int(item.get("forca", 0)),
        "defesa_bonus": int(item.get("defesa_bonus", 0)),
        "agilidade": int(item.get("agilidade", 0)),
        "inteligencia": int(item.get("inteligencia", 0)),
        "sorte": int(item.get("sorte", 0)),
        "hp_bonus": int(item.get("hp_bonus", 0)),
        "mana_bonus": int(item.get("mana_bonus", 0)),
    }


def adicionar_item(user_id, item_key, quantidade=1):
    item_key = normalizar(item_key)
    item = ITENS.get(item_key)
    if not item:
        return False

    stats = item_stats(item)
    with abrir_db() as db:
        atual = db.execute(
            "SELECT id, quantidade FROM inventario WHERE user_id = ? AND item_key = ?",
            (int(user_id), item_key),
        ).fetchone()
        if atual:
            db.execute(
                "UPDATE inventario SET quantidade = quantidade + ? WHERE id = ?",
                (int(quantidade), atual["id"]),
            )
        else:
            db.execute(
                """
                INSERT INTO inventario (
                    user_id, item_key, nome, tipo, raridade, quantidade,
                    forca, defesa_bonus, agilidade, inteligencia, sorte,
                    hp_bonus, mana_bonus, valor, descricao
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(user_id),
                    item_key,
                    item["nome"],
                    item["tipo"],
                    item["raridade"],
                    int(quantidade),
                    stats["forca"],
                    stats["defesa_bonus"],
                    stats["agilidade"],
                    stats["inteligencia"],
                    stats["sorte"],
                    stats["hp_bonus"],
                    stats["mana_bonus"],
                    int(item.get("valor", 0)),
                    item.get("desc", ""),
                ),
            )
        db.commit()
    progresso_quest(user_id, "item", quantidade)
    return True


def remover_item(user_id, item_key, quantidade=1):
    item_key = normalizar(item_key)
    with abrir_db() as db:
        row = db.execute(
            "SELECT id, quantidade, equipado FROM inventario WHERE user_id = ? AND item_key = ?",
            (int(user_id), item_key),
        ).fetchone()
        if not row or row["quantidade"] < quantidade:
            return False
        if row["equipado"] and row["quantidade"] <= quantidade:
            return False
        if row["quantidade"] == quantidade:
            db.execute("DELETE FROM inventario WHERE id = ?", (row["id"],))
        else:
            db.execute("UPDATE inventario SET quantidade = quantidade - ? WHERE id = ?", (quantidade, row["id"]))
        db.commit()
    return True


def bonus_equipamentos(user_id):
    bonus = {"forca": 0, "defesa": 0, "agilidade": 0, "inteligencia": 0, "sorte": 0, "hp_max": 0, "mana_max": 0}
    with abrir_db() as db:
        rows = db.execute(
            """
            SELECT forca, defesa_bonus, agilidade, inteligencia, sorte, hp_bonus, mana_bonus
            FROM inventario
            WHERE user_id = ? AND equipado = 1
            """,
            (int(user_id),),
        ).fetchall()

    for row in rows:
        bonus["forca"] += int(row["forca"] or 0)
        bonus["defesa"] += int(row["defesa_bonus"] or 0)
        bonus["agilidade"] += int(row["agilidade"] or 0)
        bonus["inteligencia"] += int(row["inteligencia"] or 0)
        bonus["sorte"] += int(row["sorte"] or 0)
        bonus["hp_max"] += int(row["hp_bonus"] or 0)
        bonus["mana_max"] += int(row["mana_bonus"] or 0)
    return bonus


def guild_buff(user_id):
    with abrir_db() as db:
        row = db.execute(
            """
            SELECT g.nivel
            FROM guild_membros gm
            JOIN guildas g ON g.id = gm.guild_id
            WHERE gm.user_id = ?
            """,
            (int(user_id),),
        ).fetchone()
    nivel = int(row["nivel"]) if row else 0
    return min(12, nivel * 2)


def stats_efetivos(player):
    p = dict(player)
    bonus = bonus_equipamentos(p["user_id"])
    buff = guild_buff(p["user_id"])
    transformacao = p.get("transformacao") or "Nenhuma"
    classe_avancada = p.get("classe_avancada") or "Nenhuma"

    stats = {
        "hp_max": int(p["hp_max"] or 1) + bonus["hp_max"],
        "mana_max": int(p["mana_max"] or 1) + bonus["mana_max"],
        "forca": int(p["forca"] or 1) + bonus["forca"],
        "defesa": int(p["defesa"] or 1) + bonus["defesa"] + buff,
        "agilidade": int(p["agilidade"] or 1) + bonus["agilidade"],
        "inteligencia": int(p["inteligencia"] or 1) + bonus["inteligencia"],
        "sorte": int(p["sorte"] or 1) + bonus["sorte"],
    }

    if transformacao == "Eclipse":
        for key in ("forca", "agilidade", "inteligencia"):
            stats[key] += 5 + int(p["reincarnacoes"] or 0)
    elif transformacao == "Guardiao":
        stats["defesa"] += 8
        stats["hp_max"] += 80

    if classe_avancada != "Nenhuma":
        stats["forca"] += 3
        stats["inteligencia"] += 3
        stats["sorte"] += 2

    stats["poder_fisico"] = stats["forca"] * 2 + stats["agilidade"] + int(p["nivel"]) * 2
    stats["poder_magico"] = stats["inteligencia"] * 2 + stats["sorte"] + int(p["nivel"]) * 2
    stats["crit"] = min(0.48, 0.05 + stats["sorte"] * 0.006 + stats["agilidade"] * 0.003)
    stats["esquiva"] = min(0.42, 0.04 + stats["agilidade"] * 0.006 + stats["sorte"] * 0.002)
    return stats


def poder_principal(player, stats=None):
    stats = stats or stats_efetivos(player)
    classe = normalizar(player["classe"])
    if classe in ("mago", "necromante", "paladino"):
        return stats["poder_magico"]
    return stats["poder_fisico"]


def desbloquear_habilidades(user_id, classe, nivel):
    novas = []
    skills = HABILIDADES.get(normalizar(classe), [])
    with abrir_db() as db:
        existentes = {
            row["skill_key"]
            for row in db.execute("SELECT skill_key FROM habilidades WHERE user_id = ?", (int(user_id),)).fetchall()
        }
        for skill in skills:
            if int(nivel) >= skill["nivel"] and skill["key"] not in existentes:
                db.execute("INSERT OR IGNORE INTO habilidades(user_id, skill_key) VALUES (?, ?)", (int(user_id), skill["key"]))
                novas.append(skill["nome"])
        db.commit()
    return novas


def aplicar_xp(user_id, xp_ganho, ouro_ganho=0):
    player = pegar_player(user_id)
    if not player:
        return []

    xp = int(player["xp"]) + int(xp_ganho)
    nivel = int(player["nivel"])
    ouro = int(player["ouro"]) + int(ouro_ganho)
    hp_max = int(player["hp_max"])
    mana_max = int(player["mana_max"])
    pontos = int(player["pontos"] or 0)
    energia_max = int(player["energia_max"] or 10)
    mensagens = []
    subiu = False

    while xp >= xp_necessario(nivel):
        xp -= xp_necessario(nivel)
        nivel += 1
        pontos += 5
        hp_max += 12 + nivel // 2
        mana_max += 8 + nivel // 3
        energia_max += 1 if nivel % 3 == 0 else 0
        subiu = True
        mensagens.append(f"⬆️ Subiu para o nivel **{nivel}** e ganhou **5 pontos** de atributo.")

    campos = {"xp": xp, "nivel": nivel, "ouro": ouro, "pontos": pontos}
    if subiu:
        campos.update(
            {
                "hp": hp_max,
                "hp_max": hp_max,
                "mana": mana_max,
                "mana_max": mana_max,
                "energia_max": energia_max,
                "energia": energia_max,
            }
        )
    salvar_player(user_id, **campos)

    novas = desbloquear_habilidades(user_id, player["classe"], nivel)
    if novas:
        mensagens.append("✨ Novas habilidades: " + ", ".join(f"**{n}**" for n in novas))
    return mensagens


def progresso_quest(user_id, tipo, quantidade=1):
    with abrir_db() as db:
        rows = db.execute(
            """
            SELECT id, progresso, alvo
            FROM quests
            WHERE user_id = ? AND tipo = ? AND ativa = 1 AND concluida = 0
            """,
            (int(user_id), tipo),
        ).fetchall()
        for row in rows:
            novo = min(int(row["alvo"]), int(row["progresso"]) + int(quantidade))
            concluida = 1 if novo >= int(row["alvo"]) else 0
            db.execute(
                "UPDATE quests SET progresso = ?, concluida = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (novo, concluida, row["id"]),
            )
        db.commit()


def evento_global():
    hora = agora().hour
    dia = agora().weekday()
    if hora in (12, 20):
        return {"nome": "Chuva de Loot", "bonus_drop": 0.18, "bonus_ouro": 1.15, "bonus_xp": 1.0}
    if dia >= 5:
        return {"nome": "Invasao de Monstros", "bonus_drop": 0.08, "bonus_ouro": 1.0, "bonus_xp": 1.18}
    if hora in (0, 6, 18):
        return {"nome": "Eclipse Instavel", "bonus_drop": 0.1, "bonus_ouro": 1.08, "bonus_xp": 1.08}
    return {"nome": "Mundo Calmo", "bonus_drop": 0.0, "bonus_ouro": 1.0, "bonus_xp": 1.0}


def sortear_raridade(extra=0.0):
    pesos = []
    nomes = []
    for nome, info in RARIDADES.items():
        peso = info["peso"]
        if nome in ("epico", "lendario", "mitico"):
            peso = max(1, int(peso * (1 + extra * 3)))
        pesos.append(peso)
        nomes.append(nome)
    return random.choices(nomes, weights=pesos, k=1)[0]


def gerar_drop(nivel, sorte=0):
    chance = min(0.55, 0.13 + sorte * 0.005 + evento_global()["bonus_drop"])
    if random.random() > chance:
        return None

    raridade = sortear_raridade(sorte * 0.003)
    candidatos = [key for key, item in ITENS.items() if item["raridade"] == raridade and item["tipo"] != "pocao"]
    if not candidatos:
        candidatos = [key for key in ITENS if ITENS[key]["tipo"] != "pocao"]
    return random.choice(candidatos)


def criar_monstro(regiao_key, nivel_player):
    regiao = REGIOES[regiao_key]
    nome = random.choice(regiao["monstros"])
    base = MONSTROS_BASE[nome].copy()
    dificuldade = regiao["dificuldade"]
    escala = 1 + max(0, nivel_player - 1) * 0.09
    elite = 1.0
    if base["tipo"] == "elite":
        elite = 1.22
    elif base["tipo"] == "boss":
        elite = 1.55

    return {
        "nome": nome,
        "tipo": base["tipo"],
        "hp": int(base["hp"] * dificuldade * escala * elite),
        "hp_max": int(base["hp"] * dificuldade * escala * elite),
        "poder": int(base["poder"] * dificuldade * escala),
        "defesa": int(base["defesa"] * dificuldade * escala),
        "agilidade": int(base["agilidade"] * escala),
        "xp": int(base["xp"] * dificuldade * escala * elite),
        "ouro": int(base["ouro"] * dificuldade * escala * elite),
    }


def dano_com_crit(base, crit_chance):
    critou = random.random() < crit_chance
    dano = base * (1.75 if critou else 1.0)
    return max(1, int(dano)), critou


def aplicar_status_tick(nome, hp, status, log):
    skip = False
    for key in list(status.keys()):
        turnos = status[key]
        if turnos <= 0:
            status.pop(key, None)
            continue
        if key in ("burn", "veneno", "bleed"):
            dano = {"burn": 9, "veneno": 7, "bleed": 6}[key] + random.randint(0, 5)
            hp -= dano
            log.append(f"{nome} sofre **{dano}** por {key}.")
        elif key == "stun":
            skip = True
            log.append(f"{nome} ficou atordoado e perdeu o turno.")
        status[key] -= 1
        if status[key] <= 0:
            status.pop(key, None)
    return hp, skip


def escolher_habilidade(player, mana_atual, cooldowns):
    nivel = int(player["nivel"])
    classe = normalizar(player["classe"])
    disponiveis = [
        skill
        for skill in HABILIDADES.get(classe, [])
        if nivel >= skill["nivel"] and mana_atual >= skill["mana"] and cooldowns.get(skill["key"], 0) <= 0
    ]
    if not disponiveis:
        return None
    disponiveis.sort(key=lambda s: (s.get("mult", 0), s["nivel"]), reverse=True)
    return disponiveis[0] if random.random() < 0.72 else random.choice(disponiveis)


def simular_pve(player, monstro):
    stats = stats_efetivos(player)
    hp = min(int(player["hp"]), stats["hp_max"])
    mana = min(int(player["mana"]), stats["mana_max"])
    pocao = int(player["pocao"] or 0)
    log = [f"⚔️ **{player['nome']}** encontrou **{monstro['nome']}** ({monstro['tipo']})."]
    cooldowns = {}
    status_player = {}
    status_monstro = {}
    defesa_turno = 0
    summon_turns = 0
    dano_total = 0

    for turno in range(1, 16):
        if hp <= 0 or monstro["hp"] <= 0:
            break

        for key in list(cooldowns.keys()):
            cooldowns[key] = max(0, cooldowns[key] - 1)

        hp, skip_player = aplicar_status_tick("Voce", hp, status_player, log)
        monstro["hp"], skip_monstro_tick = aplicar_status_tick(monstro["nome"], monstro["hp"], status_monstro, log)
        if hp <= 0 or monstro["hp"] <= 0:
            break

        log.append(f"**Turno {turno}**")

        if skip_player:
            pass
        elif hp < stats["hp_max"] * 0.3 and pocao > 0:
            cura = 70 + int(player["nivel"]) * 4
            hp = min(stats["hp_max"], hp + cura)
            pocao -= 1
            log.append(f"🧪 Voce usou uma pocao e recuperou **{cura} HP**.")
        else:
            skill = escolher_habilidade(player, mana, cooldowns)
            if skill:
                mana -= skill["mana"]
                cooldowns[skill["key"]] = skill.get("cooldown", 2)
                if skill.get("buff") == "defesa":
                    defesa_turno = 8 + int(stats["defesa"] * 0.35)
                    log.append(f"🛡️ **{skill['nome']}** aumenta sua defesa neste turno.")
                if skill.get("heal"):
                    cura = int(stats["hp_max"] * skill["heal"])
                    hp = min(stats["hp_max"], hp + cura)
                    log.append(f"✨ **{skill['nome']}** cura **{cura} HP**.")
                if skill.get("summon"):
                    summon_turns = max(summon_turns, int(skill["summon"]))
                    log.append(f"☠️ **{skill['nome']}** invoca um aliado por {summon_turns} turnos.")
                if skill.get("mult", 0) > 0:
                    poder = poder_principal(player, stats)
                    bruto = poder * skill["mult"] + random.randint(0, 10 + int(player["nivel"]))
                    bruto -= monstro["defesa"] * 0.55
                    crit_bonus = skill.get("crit_bonus", 0)
                    dano, critou = dano_com_crit(max(1, bruto), stats["crit"] + crit_bonus)
                    monstro["hp"] -= dano
                    dano_total += dano
                    extra = " CRITICO!" if critou else ""
                    log.append(f"✨ **{skill['nome']}** causa **{dano}** de dano.{extra}")
                if skill.get("status") and random.random() < skill.get("chance", 0):
                    status_monstro[skill["status"]] = 2 if skill["status"] != "stun" else 1
                    log.append(f"🌪️ {monstro['nome']} recebeu **{skill['status']}**.")
            elif random.random() < 0.12:
                defesa_turno = 6 + int(stats["defesa"] * 0.25)
                log.append("🛡️ Voce defende e reduz o proximo dano.")
            else:
                poder = poder_principal(player, stats)
                bruto = poder + random.randint(-4, 10 + int(player["nivel"])) - monstro["defesa"] * 0.45
                dano, critou = dano_com_crit(max(1, bruto), stats["crit"])
                monstro["hp"] -= dano
                dano_total += dano
                log.append(f"🗡️ Ataque causa **{dano}** de dano" + (" CRITICO!" if critou else "."))

        if summon_turns > 0 and monstro["hp"] > 0:
            extra = max(3, int(stats["inteligencia"] * 0.9) + random.randint(1, 8))
            monstro["hp"] -= extra
            dano_total += extra
            summon_turns -= 1
            log.append(f"☠️ Invocacao causa **{extra}** de dano.")

        if monstro["hp"] <= 0:
            break

        if skip_monstro_tick:
            continue
        if random.random() < stats["esquiva"] * (0.55 if "slow" in status_monstro else 1.0):
            log.append(f"💨 Voce esquivou do ataque de {monstro['nome']}.")
            continue

        dano_monstro = monstro["poder"] + random.randint(-3, 8) - (stats["defesa"] + defesa_turno) * 0.55
        dano_monstro = max(1, int(dano_monstro))
        hp -= dano_monstro
        log.append(f"💥 {monstro['nome']} causa **{dano_monstro}** de dano.")
        defesa_turno = 0

    venceu = hp > 0 and monstro["hp"] <= 0
    return {
        "venceu": venceu,
        "hp": max(1, hp),
        "mana": max(0, mana),
        "pocao": pocao,
        "log": log,
        "dano": dano_total,
    }


def registrar_batalha(user_id, tipo, oponente, venceu, dano, xp=0, ouro=0):
    with abrir_db() as db:
        db.execute(
            """
            INSERT INTO batalhas(user_id, tipo, oponente, venceu, dano, xp, ouro)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (int(user_id), tipo, oponente, 1 if venceu else 0, int(dano), int(xp), int(ouro)),
        )
        db.commit()


def rank_por_pontos(vitorias, derrotas):
    pontos = int(vitorias) * 3 - int(derrotas)
    if pontos >= 75:
        return "mestre"
    if pontos >= 45:
        return "diamante"
    if pontos >= 25:
        return "platina"
    if pontos >= 12:
        return "ouro"
    if pontos >= 5:
        return "prata"
    return "bronze"
