# Arquivo extraido de bot.py para manter o projeto organizado.
from .core import *
from .database import *

# =========================
# HELPERS SOCIAL / AURA
# =========================

def semana_chave():
    ano, semana, _ = agora().isocalendar()
    return f"{ano}-W{semana:02d}"


def mes_chave():
    return agora().strftime("%Y-%m")


def xp_para_proximo_social(nivel):
    nivel = max(1, int(nivel))
    if nivel <= 10:
        return int((875 / 36) * (nivel ** 2) + (925 / 12) * nivel - (25 / 18))
    return int(3000 * ((nivel / 10) ** 2.038))


def barra_percentual(valor, maximo, tamanho=18):
    if maximo <= 0:
        return "░" * tamanho
    pct = max(0, min(1, valor / maximo))
    cheio = int(pct * tamanho)
    return "█" * cheio + "░" * (tamanho - cheio)


def pegar_social_user(user_id):
    with abrir_db() as db:
        db.execute("INSERT OR IGNORE INTO social_users(user_id, daily_key, weekly_key, monthly_key) VALUES (?, ?, ?, ?)",
                   (int(user_id), hoje_chave(), semana_chave(), mes_chave()))
        resetar_periodos_social_db(db, int(user_id))
        return db.execute("SELECT * FROM social_users WHERE user_id = ?", (int(user_id),)).fetchone()


def resetar_periodos_social_db(db, user_id):
    hoje = hoje_chave()
    semana = semana_chave()
    mes = mes_chave()
    user = db.execute("SELECT daily_key, weekly_key, monthly_key FROM social_users WHERE user_id = ?", (int(user_id),)).fetchone()
    if not user:
        return
    updates = {}
    if user["daily_key"] != hoje:
        updates["daily_key"] = hoje
        updates["daily_xp"] = 0
    if user["weekly_key"] != semana:
        updates["weekly_key"] = semana
        updates["weekly_xp"] = 0
    if user["monthly_key"] != mes:
        updates["monthly_key"] = mes
        updates["monthly_xp"] = 0
    if updates:
        partes = ", ".join(f"{k} = ?" for k in updates)
        db.execute(f"UPDATE social_users SET {partes} WHERE user_id = ?", list(updates.values()) + [int(user_id)])


def salvar_social_user(user_id, **campos):
    if not campos:
        return
    campos["updated_at"] = datetime.utcnow().isoformat(timespec="seconds")
    partes = ", ".join(f"{campo} = ?" for campo in campos)
    valores = list(campos.values()) + [int(user_id)]
    with abrir_db() as db:
        db.execute(f"UPDATE social_users SET {partes} WHERE user_id = ?", valores)


def aura_social(user):
    rep = int(user["reputacao"] or 0)
    nivel = int(user["nivel"] or 1)
    conquistas = contar_conquistas_social(user["user_id"])
    reports = int(user["reports"] or 0)
    score = rep * 3 + nivel * 2 + conquistas * 6 - reports * 15
    if rep < -10 or score < -30:
        return "Toxica"
    if score >= 900:
        return "Lendaria"
    if score >= 180:
        return "Positiva"
    if rep < 0 or reports > 0:
        return "Caotica"
    return "Neutra"


def cargo_social_nome(user):
    nivel = int(user["nivel"] or 1)
    rep = int(user["reputacao"] or 0)
    base = "Novato"
    for req, nome in sorted(SOCIAL_LEVEL_ROLES.items()):
        if nivel >= req:
            base = nome
    rep_rank = ""
    for req, nome in sorted(SOCIAL_REP_ROLES.items()):
        if rep >= req:
            rep_rank = nome
    return f"{base} / {rep_rank}" if rep_rank else base


def contar_conquistas_social(user_id):
    with abrir_db() as db:
        row = db.execute("SELECT COUNT(*) AS total FROM social_achievements WHERE user_id = ?", (int(user_id),)).fetchone()
    return int(row["total"] or 0)


def desbloquear_titulo_social(user_id, titulo):
    if not titulo:
        return
    with abrir_db() as db:
        db.execute("INSERT OR IGNORE INTO social_titles(user_id, titulo) VALUES (?, ?)", (int(user_id), titulo))


def adicionar_conquista_social(user_id, chave, nome, titulo=""):
    with abrir_db() as db:
        antes = db.execute(
            "SELECT 1 FROM social_achievements WHERE user_id = ? AND achievement_key = ?",
            (int(user_id), chave),
        ).fetchone()
        db.execute(
            """
            INSERT OR IGNORE INTO social_achievements(user_id, achievement_key, nome, titulo)
            VALUES (?, ?, ?, ?)
            """,
            (int(user_id), chave, nome, titulo),
        )
    if titulo:
        desbloquear_titulo_social(user_id, titulo)
    return antes is None


def checar_conquistas_social(user_id):
    user = pegar_social_user(user_id)
    novas = []
    checks = [
        ("primeiro_passo", "Primeiro Passo", "O Sumido", int(user["mensagens"]) >= 1),
        ("tagarela", "Tagarela", "O Tagarela", int(user["mensagens"]) >= 1000),
        ("lenda_viva", "Lenda Viva", "A Lenda", int(user["nivel"]) >= 100),
        ("popular", "Popular", "O Conselheiro", int(user["reputacao"]) >= 100),
        ("mentor", "Mentor", "O Conselheiro", contar_reps_por_tipo(user_id, "ajuda") >= 50),
        ("mestre_call", "Mestre da Call", "O Mestre da Call", int(user["call_seconds"]) >= 600 * 60),
        ("madrugador", "Madrugador", "", 5 <= agora().hour <= 8 and int(user["mensagens"]) >= 1),
        ("noturno", "Noturno", "", agora().hour <= 4 and int(user["mensagens"]) >= 1),
    ]
    for chave, nome, titulo, condicao in checks:
        if condicao and adicionar_conquista_social(user_id, chave, nome, titulo):
            novas.append(nome)
    for titulo, req in SOCIAL_TITLES.items():
        ok = True
        if "level" in req and int(user["nivel"]) < req["level"]:
            ok = False
        if "rep" in req and int(user["reputacao"]) < req["rep"]:
            ok = False
        if "call_minutes" in req and int(user["call_seconds"]) < req["call_minutes"] * 60:
            ok = False
        if "achievement" in req:
            with abrir_db() as db:
                ach = db.execute(
                    "SELECT 1 FROM social_achievements WHERE user_id = ? AND achievement_key = ?",
                    (int(user_id), req["achievement"]),
                ).fetchone()
            if not ach:
                ok = False
        if ok:
            desbloquear_titulo_social(user_id, titulo)
    return novas


def contar_reps_por_tipo(user_id, tipo):
    with abrir_db() as db:
        row = db.execute(
            "SELECT COUNT(*) AS total FROM social_rep_log WHERE receiver_id = ? AND tipo = ? AND valor > 0",
            (int(user_id), normalizar(tipo)),
        ).fetchone()
    return int(row["total"] or 0)


async def aplicar_cargos_sociais(member, user):
    if not getattr(member, "guild", None):
        return
    guild = member.guild
    roles_to_add = []
    for nivel, role_name in SOCIAL_LEVEL_ROLES.items():
        if int(user["nivel"]) >= nivel:
            role = discord.utils.get(guild.roles, name=role_name)
            if role and role not in member.roles:
                roles_to_add.append(role)
    for rep, role_name in SOCIAL_REP_ROLES.items():
        if int(user["reputacao"]) >= rep:
            role = discord.utils.get(guild.roles, name=role_name)
            if role and role not in member.roles:
                roles_to_add.append(role)
    if roles_to_add:
        try:
            await member.add_roles(*roles_to_add, reason="Recompensa social do bot")
        except (discord.Forbidden, discord.HTTPException):
            pass


def usuario_mutado_social(member):
    for role in getattr(member, "roles", []) or []:
        if normalizar(getattr(role, "name", "")) in ("muted", "mute", "silenciado", "castigado"):
            return True
    return False


def canal_ignorado_social(channel):
    ids = {x.strip() for x in os.getenv("SOCIAL_IGNORED_CHANNELS", "").split(",") if x.strip()}
    return str(getattr(channel, "id", "")) in ids


def calcular_xp_mensagem(message, user):
    conteudo = " ".join(str(getattr(message, "content", "") or "").split())
    if len(conteudo) < SOCIAL_MIN_MESSAGE_LEN:
        return 0, "curta"
    msg_hash = hashlib.sha1(conteudo.lower().encode("utf-8", errors="ignore")).hexdigest()
    if msg_hash == (user["last_message_hash"] or ""):
        return 0, "repetida"

    xp = random.randint(12, 22)
    repetidas = int(user["repeated_count"] or 0)
    if repetidas >= 2:
        xp = max(2, xp // 3)

    try:
        last = datetime.fromisoformat(user["last_message_at"]) if user["last_message_at"] else None
    except ValueError:
        last = None
    if last:
        delta = (datetime.utcnow() - last).total_seconds()
        if delta < SOCIAL_MESSAGE_COOLDOWN:
            return 0, "cooldown"
        if delta < 8:
            xp = max(1, xp // 4)
    if int(user["daily_xp"] or 0) >= SOCIAL_DAILY_XP_LIMIT:
        return 0, "limite"
    xp = min(xp, SOCIAL_DAILY_XP_LIMIT - int(user["daily_xp"] or 0))
    return xp, msg_hash


async def adicionar_xp_social(member, xp, motivo="atividade"):
    if xp <= 0:
        return []
    user = pegar_social_user(member.id)
    xp_total = int(user["xp"]) + int(xp)
    nivel = int(user["nivel"])
    mensagens = []
    while xp_total >= xp_para_proximo_social(nivel):
        xp_total -= xp_para_proximo_social(nivel)
        nivel += 1
        mensagens.append(f"⬆️ {member.mention} subiu para o nivel social **{nivel}**!")
    with abrir_db() as db:
        db.execute(
            """
            UPDATE social_users
            SET xp = ?, nivel = ?, daily_xp = daily_xp + ?, weekly_xp = weekly_xp + ?,
                monthly_xp = monthly_xp + ?, moedas = moedas + ?, aura = ?, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
            """,
            (xp_total, nivel, int(xp), int(xp), int(xp), max(1, int(xp) // 4), aura_social({**dict(user), "xp": xp_total, "nivel": nivel}), int(member.id)),
        )
    checar_conquistas_social(member.id)
    user_atual = pegar_social_user(member.id)
    await aplicar_cargos_sociais(member, user_atual)
    return mensagens


def hex_para_rgb(valor, padrao=(255, 102, 204)):
    valor = str(valor or "").strip()
    if valor.startswith("#") and len(valor) == 7:
        try:
            return tuple(int(valor[i:i + 2], 16) for i in (1, 3, 5))
        except ValueError:
            return padrao
    return padrao


def carregar_imagem_url(url, size):
    if not url:
        return None
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Hyori-Social-Profile/1.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = resp.read(5_000_000)
        img = Image.open(BytesIO(data)).convert("RGBA")
        return img.resize(size)
    except Exception:
        return None


def fonte_social(tamanho, bold=False):
    nomes = ["arialbd.ttf" if bold else "arial.ttf", "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"]
    for nome in nomes:
        try:
            return ImageFont.truetype(nome, tamanho)
        except OSError:
            continue
    return ImageFont.load_default()


def limitar_texto(draw, texto, fonte, largura_max):
    texto = str(texto or "")
    if draw.textlength(texto, font=fonte) <= largura_max:
        return texto
    sufixo = "..."
    while texto and draw.textlength(texto + sufixo, font=fonte) > largura_max:
        texto = texto[:-1]
    return texto + sufixo if texto else sufixo


def misturar_cor(a, b, t):
    return tuple(int(a[i] * (1 - t) + b[i] * t) for i in range(3))


def desenhar_round_layer(base, box, radius, fill=None, outline=None, width=1):
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    layer_draw = ImageDraw.Draw(layer)
    layer_draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)
    base.alpha_composite(layer)


def desenhar_ellipse_layer(base, box, fill=None, outline=None, width=1):
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    layer_draw = ImageDraw.Draw(layer)
    layer_draw.ellipse(box, fill=fill, outline=outline, width=width)
    base.alpha_composite(layer)


def desenhar_line_layer(base, coords, fill, width=1):
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    layer_draw = ImageDraw.Draw(layer)
    layer_draw.line(coords, fill=fill, width=width)
    base.alpha_composite(layer)


def desenhar_gradiente(base, cor):
    w, h = base.size
    draw = ImageDraw.Draw(base)
    escura = (9, 10, 20)
    profunda = (18, 20, 34)
    for y in range(h):
        for x in range(w):
            diagonal = (x / w) * 0.62 + (y / h) * 0.38
            r, g, b = misturar_cor(escura, profunda, diagonal)
            brilho = max(0, 1 - (((x - w * 0.72) / (w * 0.55)) ** 2 + ((y - h * 0.2) / (h * 0.9)) ** 2))
            r = min(255, int(r + cor[0] * brilho * 0.22))
            g = min(255, int(g + cor[1] * brilho * 0.22))
            b = min(255, int(b + cor[2] * brilho * 0.22))
            draw.point((x, y), fill=(r, g, b, 255))


def aura_cor(nome):
    cores = {
        "Lendaria": (255, 205, 87),
        "Positiva": (70, 221, 160),
        "Neutra": (145, 157, 180),
        "Caotica": (176, 104, 255),
        "Toxica": (255, 78, 102),
    }
    return cores.get(str(nome), (145, 157, 180))


def formatar_tempo_curto(seconds):
    minutos = max(0, int(seconds or 0) // 60)
    horas, mins = divmod(minutos, 60)
    if horas:
        return f"{horas}h {mins}m"
    return f"{minutos} min"


def desenhar_pill(base, draw, box, texto, fonte, fill, outline=None, text_fill=(255, 255, 255)):
    desenhar_round_layer(base, box, (box[3] - box[1]) // 2, fill=fill, outline=outline, width=1)
    tw = draw.textlength(texto, font=fonte)
    th = draw.textbbox((0, 0), texto, font=fonte)[3]
    x = box[0] + ((box[2] - box[0]) - tw) / 2
    y = box[1] + ((box[3] - box[1]) - th) / 2 - 2
    draw.text((x, y), texto, font=fonte, fill=text_fill)


def desenhar_stat_card(base, draw, box, label, valor, cor):
    x1, y1, x2, y2 = box
    desenhar_round_layer(base, box, 18, fill=(18, 21, 34, 220), outline=(255, 255, 255, 46), width=1)
    desenhar_round_layer(base, (x1 + 14, y1 + 14, x1 + 20, y2 - 14), 3, fill=cor + (235,))
    label_font = fonte_social(14, True)
    value_font = fonte_social(23, True)
    draw.text((x1 + 32, y1 + 13), limitar_texto(draw, label.upper(), label_font, x2 - x1 - 44), fill=(174, 182, 205), font=label_font)
    draw.text((x1 + 32, y1 + 39), limitar_texto(draw, str(valor), value_font, x2 - x1 - 42), fill=(255, 255, 255), font=value_font)


def gerar_card_social(member, user):
    cor = hex_para_rgb(user["profile_color"])
    w, h = 1100, 520
    bg = Image.new("RGBA", (w, h), (0, 0, 0, 255))
    bg_custom = carregar_imagem_url(user["profile_bg"], (w, h))
    if bg_custom:
        bg = bg_custom.filter(ImageFilter.GaussianBlur(2))
        overlay = Image.new("RGBA", (w, h), (3, 5, 12, 165))
        bg.alpha_composite(overlay)
    else:
        desenhar_gradiente(bg, cor)

    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse((w - 360, -150, w + 160, 370), fill=cor + (92,))
    gd.ellipse((-160, h - 300, 330, h + 120), fill=(90, 180, 255, 45))
    gd.ellipse((320, 70, 760, 470), fill=(255, 255, 255, 16))
    bg.alpha_composite(glow.filter(ImageFilter.GaussianBlur(48)))

    draw = ImageDraw.Draw(bg)
    margin = 34
    panel = (margin, margin, w - margin, h - margin)
    desenhar_round_layer(bg, panel, 34, fill=(8, 10, 18, 220), outline=cor + (170,), width=2)
    desenhar_round_layer(bg, (panel[0] + 10, panel[1] + 10, panel[2] - 10, panel[3] - 10), 28, outline=(255, 255, 255, 32), width=1)
    desenhar_round_layer(bg, (panel[0] + 28, panel[1] + 24, panel[2] - 28, panel[1] + 27), 2, fill=cor + (135,))

    for i in range(5):
        y = 76 + i * 74
        desenhar_line_layer(bg, (785, y, 1030, y + 84), fill=cor + (24,), width=2)

    icon_url = user["profile_icon"] or getattr(getattr(member, "display_avatar", None), "url", "")
    avatar_size = 158
    avatar_pos = (76, 86)
    avatar = carregar_imagem_url(icon_url, (avatar_size, avatar_size))
    ring_box = (avatar_pos[0] - 11, avatar_pos[1] - 11, avatar_pos[0] + avatar_size + 11, avatar_pos[1] + avatar_size + 11)
    desenhar_ellipse_layer(bg, ring_box, fill=cor + (54,), outline=cor + (230,), width=5)
    desenhar_ellipse_layer(bg, (ring_box[0] + 8, ring_box[1] + 8, ring_box[2] - 8, ring_box[3] - 8), outline=(255, 255, 255, 130), width=2)
    if avatar:
        mask = Image.new("L", (avatar_size, avatar_size), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, avatar_size, avatar_size), fill=255)
        bg.paste(avatar, avatar_pos, mask)
    else:
        draw.ellipse((avatar_pos[0], avatar_pos[1], avatar_pos[0] + avatar_size, avatar_pos[1] + avatar_size), fill=cor + (245,))
        inicial = (str(getattr(member, "display_name", "?") or "?").strip()[:1] or "?").upper()
        inicial_font = fonte_social(72, True)
        ix = avatar_pos[0] + avatar_size / 2 - draw.textlength(inicial, font=inicial_font) / 2
        draw.text((ix, avatar_pos[1] + 38), inicial, fill=(255, 255, 255), font=inicial_font)

    nome = getattr(member, "display_name", str(member))[:28]
    titulo = user["titulo"] or "Sem titulo"
    rep = int(user["reputacao"] or 0)
    nivel = int(user["nivel"] or 1)
    xp = int(user["xp"] or 0)
    prox = xp_para_proximo_social(nivel)
    pct = 0 if prox <= 0 else max(0, min(1, xp / prox))
    aura = user["aura"] or "Neutra"
    aura_rgb = aura_cor(aura)

    small = fonte_social(17, True)
    name_font = fonte_social(48, True)
    title_font = fonte_social(22)
    draw.text((276, 72), "SOCIAL AURA", fill=cor, font=small)
    draw.text((276, 98), limitar_texto(draw, nome, name_font, 500), fill=(255, 255, 255), font=name_font)
    desenhar_pill(bg, draw, (820, 72, 1014, 116), f"AURA {aura.upper()}", fonte_social(17, True), aura_rgb + (90,), outline=aura_rgb + (205,))
    desenhar_pill(bg, draw, (276, 160, 570, 202), limitar_texto(draw, titulo, title_font, 230), title_font, (255, 255, 255, 26), outline=(255, 255, 255, 62))
    rank_font = fonte_social(16, True)
    rank_text = limitar_texto(draw, f"RANK {cargo_social_nome(user).upper()}", rank_font, 286)
    desenhar_pill(bg, draw, (590, 160, 906, 202), rank_text, rank_font, cor + (58,), outline=cor + (145,))

    lvl_box = (86, 270, 224, 408)
    desenhar_round_layer(bg, lvl_box, 28, fill=(255, 255, 255, 22), outline=(255, 255, 255, 48), width=1)
    draw.text((126, 286), "NIVEL", fill=(180, 188, 208), font=fonte_social(16, True))
    lvl_text = str(nivel)
    lvl_font = fonte_social(50, True)
    draw.text((155 - draw.textlength(lvl_text, font=lvl_font) / 2, 312), lvl_text, fill=(255, 255, 255), font=lvl_font)
    draw.text((115, 374), f"{int(pct * 100)}% XP", fill=cor, font=fonte_social(18, True))

    bar_x, bar_y, bar_w, bar_h = 276, 232, 700, 34
    draw.text((bar_x, bar_y - 34), f"XP ATUAL  {xp:,} / {prox:,}".replace(",", "."), fill=(218, 223, 238), font=fonte_social(20, True))
    desenhar_round_layer(bg, (bar_x, bar_y, bar_x + bar_w, bar_y + bar_h), 17, fill=(255, 255, 255, 24), outline=(255, 255, 255, 44), width=1)
    filled = max(10, int(bar_w * pct))
    desenhar_round_layer(bg, (bar_x, bar_y, bar_x + filled, bar_y + bar_h), 17, fill=cor + (238,))
    desenhar_round_layer(bg, (bar_x + 8, bar_y + 7, bar_x + max(9, filled - 8), bar_y + 15), 6, fill=(255, 255, 255, 48))
    draw.text((bar_x + bar_w + 18, bar_y + 4), f"{int(pct * 100)}%", fill=(255, 255, 255), font=fonte_social(22, True))

    stats = [
        ("REP", rep),
        ("MENSAGENS", user["mensagens"]),
        ("CALL", formatar_tempo_curto(user["call_seconds"])),
        ("FEITOS", contar_conquistas_social(user["user_id"])),
        ("MOEDAS", user["moedas"]),
    ]
    card_y = 300
    card_w = 142
    gap = 8
    for i, (label, value) in enumerate(stats):
        x = 276 + i * (card_w + gap)
        desenhar_stat_card(bg, draw, (x, card_y, x + card_w, card_y + 86), label, value, cor)

    bio = (user["bio"] or "Sem bio definida. Use !perfil editar bio <texto>.")[:140]
    bio_box = (276, 414, 1012, 468)
    desenhar_round_layer(bg, bio_box, 20, fill=(0, 0, 0, 82), outline=(255, 255, 255, 32), width=1)
    draw.text((300, 425), limitar_texto(draw, bio, fonte_social(20), 680), fill=(220, 226, 240), font=fonte_social(20))

    buffer = BytesIO()
    bg.convert("RGB").save(buffer, format="PNG", optimize=True)
    buffer.seek(0)
    return buffer
