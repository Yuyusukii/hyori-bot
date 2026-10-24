from contextlib import contextmanager
import asyncio
from collections import deque
from dataclasses import dataclass
import hashlib
from io import BytesIO
import json
import math
import os
import random
import shutil
import sqlite3
import unicodedata
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import discord
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFilter, ImageFont

try:
    import yt_dlp
except ImportError:
    yt_dlp = None

try:
    import imageio_ffmpeg
except ImportError:
    imageio_ffmpeg = None

try:
    import davey
except ImportError:
    davey = None


PREFIXO = "!"
BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "rpg.db"
ENV_PATH = BASE_DIR / ".env"
ENV_LOCAL_PATH = BASE_DIR / ".env.local"
GACHA_CACHE_PATH = BASE_DIR / "personagens_gacha_cache.json"
GACHA_LIBRARY_URL = "https://raw.githubusercontent.com/Yuyusukii/personagens-anime/refs/heads/main/personagens79086.json"
SAO_PAULO = timezone(timedelta(hours=-3))


# =========================
# CONFIGURACAO
# =========================

def carregar_env():
    valores = {}
    for env_path in (ENV_PATH, ENV_LOCAL_PATH):
        if not env_path.exists():
            continue

        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key:
                valores[key] = value

    for key, value in valores.items():
        if key not in os.environ:
            os.environ[key] = value


def agora():
    return datetime.now(SAO_PAULO)


def hoje_chave():
    return agora().strftime("%Y-%m-%d")


def normalizar(texto):
    texto = str(texto or "").strip().lower()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
    return texto.replace(" ", "_")


carregar_env()

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.reactions = True
intents.voice_states = True

class EclipseBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.local_server = None

    async def setup_hook(self):
        await super().setup_hook()
        from .local_server import iniciar_servidor_local

        self.local_server = await iniciar_servidor_local(self)

    async def close(self):
        local_server = self.local_server
        self.local_server = None
        try:
            if local_server is not None:
                await local_server.stop()
        finally:
            await super().close()


bot = EclipseBot(command_prefix=PREFIXO, intents=intents, help_command=None)


# =========================
# DADOS DO RPG
# =========================

CORES = {
    "comum": discord.Color.light_grey(),
    "raro": discord.Color.blue(),
    "epico": discord.Color.purple(),
    "lendario": discord.Color.gold(),
    "mitico": discord.Color.red(),
}

RARIDADES = {
    "comum": {"peso": 60, "mult": 1.0},
    "raro": {"peso": 25, "mult": 1.45},
    "epico": {"peso": 10, "mult": 2.1},
    "lendario": {"peso": 4, "mult": 3.0},
    "mitico": {"peso": 1, "mult": 4.2},
}

GACHA_PULL_COST = 120
GACHA_PITY_LIMIT = 90
GACHA_DAILY_CRISTAIS = 300
GACHA_DAILY_TICKETS = 1
GACHA_ADMIN_ROLE_NAMES = {"adm", "admin", "administrador", "staff", "moderador", "mod", "gacha_admin"}
GACHA_RARIDADES = {
    "comum": {"emoji": "⚪", "nome": "Comum", "peso": 68.0, "cor": discord.Color.light_grey(), "rank": 1},
    "raro": {"emoji": "🔵", "nome": "Raro", "peso": 22.0, "cor": discord.Color.blue(), "rank": 2},
    "epico": {"emoji": "🟣", "nome": "Epico", "peso": 7.0, "cor": discord.Color.purple(), "rank": 3},
    "lendario": {"emoji": "🟡", "nome": "Lendario", "peso": 2.5, "cor": discord.Color.gold(), "rank": 4},
    "mitico": {"emoji": "🔴", "nome": "Mitico", "peso": 0.5, "cor": discord.Color.red(), "rank": 5},
}
GACHA_SELL_VALUES = {
    "comum": 15,
    "raro": 35,
    "epico": 90,
    "lendario": 260,
    "mitico": 900,
}
GACHA_CATALOGO_CACHE = {"loaded": False, "personagens": [], "por_raridade": {}, "erro": None}

SOCIAL_MESSAGE_COOLDOWN = 60
SOCIAL_REP_DAILY_LIMIT = 1
SOCIAL_REP_PAIR_COOLDOWN_DAYS = 7
SOCIAL_DAILY_XP_LIMIT = 1200
SOCIAL_MIN_MESSAGE_LEN = 8
SOCIAL_TITLES = {
    "O Tagarela": {"level": 5, "achievement": "tagarela"},
    "O Conselheiro": {"rep": 50},
    "A Lenda": {"level": 100},
    "O Sumido": {"level": 3},
    "O Mestre da Call": {"call_minutes": 600},
    "O Rei do Server": {"rep": 500, "level": 50},
    "Guardiao Lendario": {"level": 30, "rep": 100},
}
SOCIAL_LEVEL_ROLES = {
    5: "Ativo",
    15: "Frequente",
    20: "Veterano",
    50: "Elite",
    100: "Lenda",
}
SOCIAL_REP_ROLES = {
    100: "Confiavel",
    300: "Respeitado",
    500: "Icone",
}
SOCIAL_SHOP = {
    "fundo_cyberpunk": {"nome": "Fundo Cyberpunk", "tipo": "background", "preco": 2000, "nivel": 20, "valor": "cyberpunk"},
    "fundo_floresta": {"nome": "Fundo Floresta", "tipo": "background", "preco": 1500, "nivel": 20, "valor": "floresta"},
    "moldura_dourada": {"nome": "Moldura Dourada", "tipo": "frame", "preco": 5000, "nivel": 30, "valor": "dourada"},
    "badge_vip": {"nome": "Badge VIP", "tipo": "badge", "preco": 3500, "nivel": 25, "valor": "vip"},
    "cor_neon": {"nome": "Cor Neon", "tipo": "color", "preco": 2500, "nivel": 10, "valor": "#ff66cc"},
}
SOCIAL_REP_TYPES = {
    "ajuda": {"valor": 1, "label": "Ajuda"},
    "engracado": {"valor": 1, "label": "Engracado"},
    "engraçado": {"valor": 1, "label": "Engracado"},
    "confiavel": {"valor": 1, "label": "Confiavel"},
    "confiável": {"valor": 1, "label": "Confiavel"},
    "criativo": {"valor": 1, "label": "Criativo"},
    "toxico": {"valor": -1, "label": "Toxico"},
    "tóxico": {"valor": -1, "label": "Toxico"},
    "spam": {"valor": -1, "label": "Spam"},
    "golpe": {"valor": -1, "label": "Golpe/Fake"},
    "fake": {"valor": -1, "label": "Golpe/Fake"},
}

MUSIC_MAX_QUEUE = 80
MUSIC_MAX_PLAYLIST_ADD = 50
MUSIC_YTDL_OPTIONS = {
    "format": "bestaudio[ext=m4a]/bestaudio/best",
    "quiet": True,
    "no_warnings": True,
    "ignoreerrors": True,
    "nocheckcertificate": True,
    "default_search": "ytsearch",
    "source_address": "0.0.0.0",
}
MUSIC_FFMPEG_BEFORE_OPTIONS = "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
MUSIC_FFMPEG_OPTIONS = "-vn -filter:a volume=0.92"
MUSIC_PLAYERS = {}

CLASSES_RPG = {
    "guerreiro": {
        "emoji": "⚔️",
        "nome": "Guerreiro",
        "descricao": "Alto HP, defesa solida e dano fisico constante.",
        "hp": 145,
        "mana": 35,
        "forca": 12,
        "defesa": 12,
        "agilidade": 6,
        "inteligencia": 3,
        "sorte": 5,
        "avancada": "Berserker Solar",
    },
    "mago": {
        "emoji": "🧙",
        "nome": "Mago",
        "descricao": "Explosao magica, controle e alto custo de mana.",
        "hp": 90,
        "mana": 120,
        "forca": 3,
        "defesa": 4,
        "agilidade": 7,
        "inteligencia": 16,
        "sorte": 7,
        "avancada": "Arcanista Eclipse",
    },
    "arqueiro": {
        "emoji": "🏹",
        "nome": "Arqueiro",
        "descricao": "Critico, esquiva e dano estavel de longo alcance.",
        "hp": 110,
        "mana": 55,
        "forca": 8,
        "defesa": 7,
        "agilidade": 14,
        "inteligencia": 5,
        "sorte": 11,
        "avancada": "Sentinela Lunar",
    },
    "assassino": {
        "emoji": "🗡️",
        "nome": "Assassino",
        "descricao": "Stealth, burst e chance critica alta.",
        "hp": 100,
        "mana": 65,
        "forca": 10,
        "defesa": 5,
        "agilidade": 16,
        "inteligencia": 5,
        "sorte": 10,
        "avancada": "Sombra Absoluta",
    },
    "paladino": {
        "emoji": "🛡️",
        "nome": "Paladino",
        "descricao": "Tank, cura e protecao para guerras longas.",
        "hp": 135,
        "mana": 85,
        "forca": 8,
        "defesa": 14,
        "agilidade": 4,
        "inteligencia": 9,
        "sorte": 6,
        "avancada": "Templario Celeste",
    },
    "necromante": {
        "emoji": "☠️",
        "nome": "Necromante",
        "descricao": "Invocacoes, veneno e drenagem de vida.",
        "hp": 105,
        "mana": 105,
        "forca": 4,
        "defesa": 6,
        "agilidade": 6,
        "inteligencia": 14,
        "sorte": 9,
        "avancada": "Lorde dos Ossos",
    },
}

RACAS_RPG = {
    "humano": {
        "emoji": "🧬",
        "nome": "Humano",
        "descricao": "Balanceado e ganha mais pontos livres.",
        "hp": 8,
        "mana": 8,
        "forca": 1,
        "defesa": 1,
        "agilidade": 1,
        "inteligencia": 1,
        "sorte": 1,
        "pontos": 3,
    },
    "elfo": {
        "emoji": "🧝",
        "nome": "Elfo",
        "descricao": "Agilidade e sorte altas.",
        "hp": -5,
        "mana": 15,
        "forca": 0,
        "defesa": 0,
        "agilidade": 4,
        "inteligencia": 2,
        "sorte": 3,
        "pontos": 1,
    },
    "anao": {
        "emoji": "⛏️",
        "nome": "Anao",
        "descricao": "Defesa e HP superiores.",
        "hp": 25,
        "mana": -5,
        "forca": 2,
        "defesa": 5,
        "agilidade": -2,
        "inteligencia": 0,
        "sorte": 1,
        "pontos": 1,
    },
    "demonio": {
        "emoji": "😈",
        "nome": "Demonio",
        "descricao": "Dano alto com menor suporte.",
        "hp": 10,
        "mana": 10,
        "forca": 4,
        "defesa": 0,
        "agilidade": 1,
        "inteligencia": 3,
        "sorte": -1,
        "pontos": 1,
    },
    "celestial": {
        "emoji": "✨",
        "nome": "Celestial",
        "descricao": "Cura, mana e suporte.",
        "hp": 5,
        "mana": 30,
        "forca": -1,
        "defesa": 2,
        "agilidade": 0,
        "inteligencia": 4,
        "sorte": 2,
        "pontos": 1,
    },
}

ORIGENS_RPG = {
    "exilado": "Foi banido de uma terra esquecida e busca reconstruir o proprio nome.",
    "nobre": "Nasceu entre brasoes, intrigas e promessas antigas.",
    "orfao": "Aprendeu a sobreviver nas ruas antes de ouvir o chamado do Eclipse.",
    "academia": "Foi treinado em uma ordem que estuda magia, armas e monstros.",
    "mercenario": "Vendeu sua espada antes de escolher uma causa maior.",
}

HABILIDADES = {
    "guerreiro": [
        {"key": "corte_profundo", "nivel": 1, "nome": "Corte Profundo", "mana": 8, "mult": 1.25, "cooldown": 2, "status": "bleed", "chance": 0.25},
        {"key": "postura_de_aco", "nivel": 4, "nome": "Postura de Aco", "mana": 10, "mult": 0.0, "cooldown": 4, "buff": "defesa"},
        {"key": "furia_titanica", "nivel": 9, "nome": "Furia Titanica", "mana": 18, "mult": 1.85, "cooldown": 4, "status": "stun", "chance": 0.12},
    ],
    "mago": [
        {"key": "bola_de_fogo", "nivel": 1, "nome": "Bola de Fogo", "mana": 14, "mult": 1.45, "cooldown": 2, "status": "burn", "chance": 0.35},
        {"key": "lanca_de_gelo", "nivel": 5, "nome": "Lanca de Gelo", "mana": 16, "mult": 1.35, "cooldown": 3, "status": "slow", "chance": 0.45},
        {"key": "relampago", "nivel": 10, "nome": "Relampago", "mana": 24, "mult": 1.75, "cooldown": 4, "status": "stun", "chance": 0.28},
        {"key": "explosao_arcana", "nivel": 18, "nome": "Explosao Arcana", "mana": 38, "mult": 2.45, "cooldown": 6},
    ],
    "arqueiro": [
        {"key": "tiro_preciso", "nivel": 1, "nome": "Tiro Preciso", "mana": 8, "mult": 1.25, "cooldown": 2, "crit_bonus": 0.15},
        {"key": "chuva_de_flechas", "nivel": 6, "nome": "Chuva de Flechas", "mana": 18, "mult": 1.65, "cooldown": 4, "status": "bleed", "chance": 0.2},
        {"key": "olho_do_falcao", "nivel": 12, "nome": "Olho do Falcao", "mana": 20, "mult": 2.05, "cooldown": 5, "crit_bonus": 0.3},
    ],
    "assassino": [
        {"key": "golpe_sombrio", "nivel": 1, "nome": "Golpe Sombrio", "mana": 10, "mult": 1.35, "cooldown": 2, "crit_bonus": 0.2},
        {"key": "veneno_negro", "nivel": 5, "nome": "Veneno Negro", "mana": 14, "mult": 1.05, "cooldown": 3, "status": "veneno", "chance": 0.55},
        {"key": "execucao", "nivel": 13, "nome": "Execucao", "mana": 26, "mult": 2.55, "cooldown": 6, "crit_bonus": 0.15},
    ],
    "paladino": [
        {"key": "golpe_sagrado", "nivel": 1, "nome": "Golpe Sagrado", "mana": 10, "mult": 1.25, "cooldown": 2, "heal": 0.22},
        {"key": "luz_guardia", "nivel": 5, "nome": "Luz Guardia", "mana": 18, "mult": 0.0, "cooldown": 4, "buff": "defesa", "heal": 0.35},
        {"key": "julgamento", "nivel": 12, "nome": "Julgamento", "mana": 24, "mult": 1.85, "cooldown": 4, "status": "stun", "chance": 0.18},
    ],
    "necromante": [
        {"key": "drenar_vida", "nivel": 1, "nome": "Drenar Vida", "mana": 12, "mult": 1.2, "cooldown": 2, "heal": 0.45},
        {"key": "invocar_esqueleto", "nivel": 6, "nome": "Invocar Esqueleto", "mana": 20, "mult": 0.9, "cooldown": 4, "summon": 3},
        {"key": "praga", "nivel": 11, "nome": "Praga", "mana": 24, "mult": 1.25, "cooldown": 4, "status": "veneno", "chance": 0.75},
    ],
}

REGIOES = {
    "floresta": {
        "emoji": "🌲",
        "nome": "Floresta",
        "nivel": 1,
        "dificuldade": 1.0,
        "monstros": ["Slime", "Goblin", "Lobo Sombrio", "Bandido"],
    },
    "caverna": {
        "emoji": "🪨",
        "nome": "Caverna",
        "nivel": 4,
        "dificuldade": 1.35,
        "monstros": ["Morcego Rubro", "Orc", "Golem Rachado", "Aranha Cristal"],
    },
    "castelo": {
        "emoji": "🏰",
        "nome": "Castelo",
        "nivel": 8,
        "dificuldade": 1.8,
        "monstros": ["Cavaleiro Caido", "Mago Real", "Gargula", "Comandante Espectral"],
    },
    "inferno": {
        "emoji": "🔥",
        "nome": "Inferno",
        "nivel": 14,
        "dificuldade": 2.45,
        "monstros": ["Imp", "Demonio Carniceiro", "Cao Infernal", "Arauto das Cinzas"],
    },
    "ceu": {
        "emoji": "☁️",
        "nome": "Ceu",
        "nivel": 18,
        "dificuldade": 2.9,
        "monstros": ["Sentinela Celeste", "Serafim Hostil", "Quimera Branca", "Juiz Alado"],
    },
}

MONSTROS_BASE = {
    "Slime": {"hp": 45, "poder": 7, "defesa": 1, "agilidade": 3, "xp": 22, "ouro": 18, "tipo": "comum"},
    "Goblin": {"hp": 65, "poder": 12, "defesa": 3, "agilidade": 8, "xp": 38, "ouro": 32, "tipo": "comum"},
    "Lobo Sombrio": {"hp": 82, "poder": 15, "defesa": 4, "agilidade": 13, "xp": 55, "ouro": 45, "tipo": "comum"},
    "Bandido": {"hp": 75, "poder": 14, "defesa": 5, "agilidade": 10, "xp": 48, "ouro": 42, "tipo": "comum"},
    "Morcego Rubro": {"hp": 78, "poder": 17, "defesa": 4, "agilidade": 18, "xp": 62, "ouro": 54, "tipo": "comum"},
    "Orc": {"hp": 118, "poder": 23, "defesa": 9, "agilidade": 5, "xp": 95, "ouro": 80, "tipo": "elite"},
    "Golem Rachado": {"hp": 150, "poder": 22, "defesa": 15, "agilidade": 2, "xp": 115, "ouro": 95, "tipo": "elite"},
    "Aranha Cristal": {"hp": 100, "poder": 25, "defesa": 7, "agilidade": 16, "xp": 105, "ouro": 90, "tipo": "elite"},
    "Cavaleiro Caido": {"hp": 165, "poder": 32, "defesa": 16, "agilidade": 8, "xp": 160, "ouro": 130, "tipo": "elite"},
    "Mago Real": {"hp": 125, "poder": 39, "defesa": 8, "agilidade": 11, "xp": 175, "ouro": 145, "tipo": "elite"},
    "Gargula": {"hp": 190, "poder": 34, "defesa": 18, "agilidade": 9, "xp": 185, "ouro": 155, "tipo": "elite"},
    "Comandante Espectral": {"hp": 230, "poder": 42, "defesa": 18, "agilidade": 13, "xp": 230, "ouro": 210, "tipo": "boss"},
    "Imp": {"hp": 135, "poder": 41, "defesa": 10, "agilidade": 18, "xp": 220, "ouro": 180, "tipo": "elite"},
    "Demonio Carniceiro": {"hp": 260, "poder": 55, "defesa": 22, "agilidade": 10, "xp": 330, "ouro": 290, "tipo": "boss"},
    "Cao Infernal": {"hp": 200, "poder": 48, "defesa": 15, "agilidade": 24, "xp": 285, "ouro": 240, "tipo": "elite"},
    "Arauto das Cinzas": {"hp": 330, "poder": 62, "defesa": 24, "agilidade": 15, "xp": 420, "ouro": 360, "tipo": "boss"},
    "Sentinela Celeste": {"hp": 245, "poder": 55, "defesa": 25, "agilidade": 18, "xp": 390, "ouro": 320, "tipo": "elite"},
    "Serafim Hostil": {"hp": 275, "poder": 62, "defesa": 20, "agilidade": 24, "xp": 430, "ouro": 370, "tipo": "boss"},
    "Quimera Branca": {"hp": 360, "poder": 70, "defesa": 28, "agilidade": 17, "xp": 530, "ouro": 470, "tipo": "boss"},
    "Juiz Alado": {"hp": 420, "poder": 78, "defesa": 30, "agilidade": 20, "xp": 620, "ouro": 560, "tipo": "boss"},
}

ITENS = {
    "pocao_pequena": {"nome": "Pocao Pequena", "tipo": "pocao", "raridade": "comum", "preco": 45, "valor": 20, "cura": 60, "desc": "Cura 60 HP."},
    "pocao_mana": {"nome": "Pocao de Mana", "tipo": "pocao", "raridade": "comum", "preco": 55, "valor": 25, "mana": 55, "desc": "Recupera 55 mana."},
    "elixir_total": {"nome": "Elixir Total", "tipo": "pocao", "raridade": "raro", "preco": 220, "valor": 90, "cura": 180, "mana": 100, "desc": "Cura HP e mana."},
    "espada_ferro": {"nome": "Espada de Ferro", "tipo": "arma", "raridade": "comum", "preco": 250, "valor": 95, "forca": 4, "desc": "+4 forca."},
    "cajado_arcano": {"nome": "Cajado Arcano", "tipo": "arma", "raridade": "raro", "preco": 360, "valor": 140, "inteligencia": 7, "mana_bonus": 35, "desc": "+7 inteligencia, +35 mana."},
    "arco_silvestre": {"nome": "Arco Silvestre", "tipo": "arma", "raridade": "raro", "preco": 340, "valor": 135, "agilidade": 5, "sorte": 3, "desc": "+5 agilidade, +3 sorte."},
    "adagas_noite": {"nome": "Adagas da Noite", "tipo": "arma", "raridade": "epico", "preco": 720, "valor": 300, "forca": 5, "agilidade": 6, "sorte": 5, "desc": "+5 forca, +6 agilidade, +5 sorte."},
    "armadura_aco": {"nome": "Armadura de Aco", "tipo": "armadura", "raridade": "comum", "preco": 310, "valor": 120, "defesa_bonus": 8, "hp_bonus": 40, "desc": "+8 defesa, +40 HP."},
    "manto_estrelas": {"nome": "Manto das Estrelas", "tipo": "armadura", "raridade": "epico", "preco": 820, "valor": 340, "defesa_bonus": 5, "inteligencia": 5, "mana_bonus": 80, "desc": "+5 defesa, +5 inteligencia, +80 mana."},
    "anel_sorte": {"nome": "Anel da Sorte", "tipo": "artefato", "raridade": "raro", "preco": 500, "valor": 210, "sorte": 8, "desc": "+8 sorte."},
    "reliquia_eclipse": {"nome": "Reliquia do Eclipse", "tipo": "artefato", "raridade": "lendario", "preco": 2200, "valor": 900, "forca": 6, "inteligencia": 6, "sorte": 6, "desc": "+6 forca, +6 inteligencia, +6 sorte."},
}

LOJA_BASE = [
    "pocao_pequena",
    "pocao_mana",
    "elixir_total",
    "espada_ferro",
    "cajado_arcano",
    "arco_silvestre",
    "armadura_aco",
    "anel_sorte",
]

RANKS = ["bronze", "prata", "ouro", "platina", "diamante", "mestre"]

QUEST_TEMPLATES = {
    "cacador": {"titulo": "Cacador do Eclipse", "tipo": "combate", "alvo": 5, "xp": 180, "ouro": 160, "desc": "Derrote 5 monstros em batalhas ou exploracao."},
    "explorador": {"titulo": "Mapa Rasgado", "tipo": "explorar", "alvo": 4, "xp": 140, "ouro": 120, "desc": "Explore qualquer regiao 4 vezes."},
    "duelista": {"titulo": "Arena de Prata", "tipo": "pvp", "alvo": 1, "xp": 120, "ouro": 90, "desc": "Venca 1 duelo PvP."},
    "colecionador": {"titulo": "Brilho Raro", "tipo": "item", "alvo": 2, "xp": 150, "ouro": 130, "desc": "Encontre ou compre 2 itens."},
}

HISTORIA = {
    0: {
        "titulo": "O Chamado do Eclipse",
        "texto": "Um eclipse cobre o mundo. Uma voz antiga oferece tres caminhos.",
        "opcoes": {
            "luz": ("Voce aceita a luz quebrada do ceu.", 80, 60, {"sorte": 1}),
            "sombra": ("Voce segue a sombra entre as ruinas.", 90, 45, {"agilidade": 1}),
            "chama": ("Voce toca a chama proibida.", 100, 40, {"forca": 1}),
        },
    },
    1: {
        "titulo": "A Cidade Sem Sol",
        "texto": "Portoes negros surgem no horizonte. Uma guilda secreta pede ajuda.",
        "opcoes": {
            "proteger": ("Voce protege os civis e ganha fama.", 130, 80, {"defesa": 1}),
            "investigar": ("Voce investiga os simbolos e descobre magia antiga.", 130, 80, {"inteligencia": 1}),
        },
    },
    2: {
        "titulo": "Coroa Partida",
        "texto": "O rei desapareceu. A coroa chama pelo seu nome.",
        "opcoes": {
            "reivindicar": ("Voce reivindica a coroa partida.", 220, 160, {"forca": 1, "sorte": 1}),
            "destruir": ("Voce destruiu a coroa e libertou ecos presos.", 240, 110, {"inteligencia": 1, "defesa": 1}),
        },
    },
}




# =========================
# HELPERS COMUNS
# =========================

def embed_padrao(titulo, descricao=None, cor=discord.Color.dark_teal()):
    embed = discord.Embed(title=titulo, description=descricao, color=cor)
    embed.set_footer(text="Eclipse Legends")
    return embed


def resumir_lista(linhas, limite=3900):
    texto = "\n".join(linhas)
    if len(texto) <= limite:
        return texto
    return texto[: limite - 20] + "\n..."


def exigir_player_msg():
    return "Crie seu personagem com `!registrar Nome classe raca origem`."
