# Geracao de imagem via Hugging Face Stable Diffusion.
import shlex
from dataclasses import dataclass

import aiohttp

from .core import *


HF_IMAGE_DEFAULT_MODEL = "stabilityai/stable-diffusion-3-medium-diffusers"
HF_IMAGE_FLUX_MODEL = "black-forest-labs/FLUX.1-schnell"
HF_IMAGE_FLUX_UNCENSORED_MODEL = "enhanceaiteam/Flux-uncensored"
HF_IMAGE_ROUTER_BASE = "https://router.huggingface.co/hf-inference/models"
HF_IMAGE_DEFAULT_NEGATIVE = (
    "low quality, blurry, distorted, deformed hands, bad anatomy, extra fingers, "
    "watermark, text artifacts, jpeg artifacts"
)
HF_IMAGE_TIMEOUT = 180
HF_IMAGE_ALLOWED_SIZES = {
    "square": (768, 768),
    "wide": (1024, 576),
    "vertical": (768, 1024),
}
HF_IMAGE_BLOCKED_TERMS = {
    "cp",
    "child porn",
    "child pornography",
    "csam",
    "loli",
    "lolicon",
    "shotacon",
    "menor nua",
    "menor nu",
    "crianca nua",
    "criança nua",
    "criança pelada",
    "crianca pelada",
    "nude child",
    "naked child",
    "sexual assault",
    "estupro",
}


@dataclass
class ImageRequest:
    prompt: str
    negative_prompt: str
    width: int
    height: int
    steps: int
    guidance_scale: float
    seed: int | None
    model: str
    model_alias: str


def hf_image_token():
    return os.getenv("HUGGINGFACE_TOKEN") or os.getenv("HF_TOKEN")


def hf_image_models():
    stable = os.getenv("HF_IMAGE_MODEL_STABLE") or os.getenv("HF_IMAGE_MODEL") or HF_IMAGE_DEFAULT_MODEL
    flux = os.getenv("HF_IMAGE_MODEL_FLUX") or HF_IMAGE_FLUX_MODEL
    flux_uncensored = os.getenv("HF_IMAGE_MODEL_FLUX_UNCENSORED") or HF_IMAGE_FLUX_UNCENSORED_MODEL
    return {
        "stable": stable,
        "sd": stable,
        "sdxl": stable,
        "stable_diffusion": stable,
        "stable-diffusion": stable,
        "flux": flux,
        "flux_schnell": flux,
        "flux-schnell": flux,
        "schnell": flux,
        "flux_uncensored": flux_uncensored,
        "flux-uncensored": flux_uncensored,
        "uncensored": flux_uncensored,
    }


def normalizar_modelo_imagem(alias):
    return normalizar(alias).replace("-", "_")


def resolver_modelo_imagem(alias=None):
    alias = (alias or os.getenv("HF_IMAGE_DEFAULT_ALIAS") or "stable").strip()
    if "/" in alias:
        return alias, alias
    modelos = hf_image_models()
    chave = normalizar_modelo_imagem(alias)
    if chave in modelos:
        return modelos[chave], chave
    raise ValueError("Modelo invalido. Use `stable`, `flux` ou `flux_uncensored`.")


def hf_image_model(alias=None):
    return resolver_modelo_imagem(alias)[0]


def hf_image_endpoint(model=None, model_alias=None):
    model = (model or hf_image_model()).strip()
    custom_endpoint = os.getenv("HF_IMAGE_ENDPOINT")
    if custom_endpoint:
        return custom_endpoint
    alias = normalizar_modelo_imagem(model_alias or "")
    if alias in ("flux_uncensored", "uncensored"):
        flux_endpoint = os.getenv("HF_IMAGE_ENDPOINT_FLUX_UNCENSORED")
        if flux_endpoint:
            return flux_endpoint
    if alias in ("flux", "flux_schnell", "schnell"):
        flux_endpoint = os.getenv("HF_IMAGE_ENDPOINT_FLUX")
        if flux_endpoint:
            return flux_endpoint
    if alias in ("stable", "sd", "sdxl", "stable_diffusion"):
        stable_endpoint = os.getenv("HF_IMAGE_ENDPOINT_STABLE")
        if stable_endpoint:
            return stable_endpoint
    base = os.getenv("HF_IMAGE_API_BASE") or HF_IMAGE_ROUTER_BASE
    return f"{base.rstrip('/')}/{model}"


def prompt_imagem_bloqueado(prompt):
    texto = normalizar(prompt).replace("_", " ")
    return any(termo in texto for termo in HF_IMAGE_BLOCKED_TERMS)


def parse_image_request(texto):
    texto = str(texto or "").strip()
    if not texto:
        raise ValueError("Use: `!imagem seu prompt aqui`.")

    try:
        tokens = shlex.split(texto)
    except ValueError:
        tokens = texto.split()

    width, height = HF_IMAGE_ALLOWED_SIZES["square"]
    negative = os.getenv("HF_IMAGE_NEGATIVE_PROMPT") or HF_IMAGE_DEFAULT_NEGATIVE
    steps = int(os.getenv("HF_IMAGE_STEPS", "30"))
    guidance = float(os.getenv("HF_IMAGE_GUIDANCE", "7.5"))
    seed = None
    model_alias = os.getenv("HF_IMAGE_DEFAULT_ALIAS") or "stable"
    prompt_parts = []
    i = 0

    while i < len(tokens):
        token = tokens[i]
        key = token.lower()
        if key in ("--wide", "--paisagem", "--16:9"):
            width, height = HF_IMAGE_ALLOWED_SIZES["wide"]
        elif key in ("--vertical", "--portrait", "--retrato", "--9:16"):
            width, height = HF_IMAGE_ALLOWED_SIZES["vertical"]
        elif key in ("--square", "--quadrado", "--1:1"):
            width, height = HF_IMAGE_ALLOWED_SIZES["square"]
        elif key in ("--modelo", "--model", "--m"):
            if i + 1 >= len(tokens):
                raise ValueError("Use `--modelo stable`, `--modelo flux` ou `--modelo flux_uncensored`.")
            model_alias = tokens[i + 1]
            i += 1
        elif key in ("--flux", "--flux-schnell", "--schnell"):
            model_alias = "flux"
        elif key in ("--flux_uncensored", "--flux-uncensored", "--uncensored"):
            model_alias = "flux_uncensored"
        elif key in ("--sd", "--stable", "--sdxl"):
            model_alias = "stable"
        elif key in ("--neg", "--negative", "--negativo"):
            if i + 1 >= len(tokens):
                raise ValueError("Use `--neg \"texto negativo\"`.")
            negative = tokens[i + 1][:500]
            i += 1
        elif key in ("--seed", "--semente"):
            if i + 1 >= len(tokens):
                raise ValueError("Use `--seed 12345`.")
            seed = max(0, min(2_147_483_647, int(tokens[i + 1])))
            i += 1
        elif key in ("--steps", "--passos"):
            if i + 1 >= len(tokens):
                raise ValueError("Use `--steps 30`.")
            steps = max(10, min(50, int(tokens[i + 1])))
            i += 1
        elif key in ("--cfg", "--guidance"):
            if i + 1 >= len(tokens):
                raise ValueError("Use `--cfg 7.5`.")
            guidance = max(1.0, min(15.0, float(tokens[i + 1].replace(",", "."))))
            i += 1
        else:
            prompt_parts.append(token)
        i += 1

    prompt = " ".join(prompt_parts).strip()
    if not prompt:
        raise ValueError("O prompt ficou vazio depois das opcoes.")
    if len(prompt) > 900:
        raise ValueError("Prompt muito grande. Use ate 900 caracteres.")
    if prompt_imagem_bloqueado(prompt):
        raise ValueError("Nao posso gerar esse tipo de imagem.")
    model, resolved_alias = resolver_modelo_imagem(model_alias)

    return ImageRequest(
        prompt=prompt,
        negative_prompt=negative,
        width=width,
        height=height,
        steps=steps,
        guidance_scale=guidance,
        seed=seed,
        model=model,
        model_alias=resolved_alias,
    )


async def gerar_imagem_huggingface(request):
    token = hf_image_token()
    if not token:
        raise RuntimeError("Token da Hugging Face nao configurado. Coloque `HUGGINGFACE_TOKEN=...` no `.env`.")

    payload = {
        "inputs": request.prompt,
        "parameters": {
            "negative_prompt": request.negative_prompt,
            "num_inference_steps": request.steps,
            "guidance_scale": request.guidance_scale,
            "width": request.width,
            "height": request.height,
        },
        "options": {
            "wait_for_model": True,
            "use_cache": False,
        },
    }
    if request.seed is not None:
        payload["parameters"]["seed"] = request.seed

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "image/png",
        "Content-Type": "application/json",
        "User-Agent": "Eclipse-Legends-Discord-Bot/1.0",
    }

    timeout = aiohttp.ClientTimeout(total=HF_IMAGE_TIMEOUT)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(hf_image_endpoint(request.model, request.model_alias), headers=headers, json=payload) as response:
            content_type = response.headers.get("content-type", "")
            data = await response.read()
            if response.status >= 400:
                detalhe = data.decode("utf-8", errors="ignore")[:700] if data else "sem detalhes"
                if response.status in (401, 403):
                    raise RuntimeError("Token da Hugging Face invalido ou sem permissao de Inference Providers.")
                if response.status == 503:
                    raise RuntimeError("Modelo esta carregando ou indisponivel agora. Tente de novo em alguns segundos.")
                if (
                    request.model_alias in ("flux_uncensored", "uncensored")
                    and (response.status == 404 or "not supported by provider" in detalhe.lower())
                ):
                    raise RuntimeError(
                        "Flux Uncensored nao esta disponivel no serverless da Hugging Face para essa conta. "
                        "Configure `HF_IMAGE_ENDPOINT_FLUX_UNCENSORED` com um endpoint dedicado ou troque `HF_IMAGE_MODEL_FLUX_UNCENSORED`."
                    )
                if response.status == 410:
                    raise RuntimeError(
                        "Esse modelo foi depreciado/removido pelo provider da Hugging Face. "
                        "Troque o modelo no `.env` ou use `!imagemmodelos` para ver os modelos atuais."
                    )
                raise RuntimeError(f"Hugging Face retornou HTTP {response.status}: {detalhe}")
            if "image" not in content_type and not data.startswith(b"\x89PNG") and not data.startswith(b"\xff\xd8"):
                detalhe = data.decode("utf-8", errors="ignore")[:700] if data else "resposta vazia"
                raise RuntimeError(f"A resposta nao veio como imagem: {detalhe}")

    imagem = Image.open(BytesIO(data)).convert("RGB")
    buffer = BytesIO()
    imagem.save(buffer, format="PNG", optimize=True)
    buffer.seek(0)
    return buffer


def embed_imagem_gerada(request, author):
    embed = embed_padrao("🎨 Imagem Gerada", None, discord.Color.from_rgb(255, 102, 204))
    embed.description = f"**Prompt:** {request.prompt[:900]}"
    embed.add_field(name="Modo", value=f"`{request.model_alias}`", inline=True)
    embed.add_field(name="Modelo", value=f"`{request.model}`", inline=False)
    embed.add_field(name="Tamanho", value=f"`{request.width}x{request.height}`", inline=True)
    embed.add_field(name="Passos", value=f"`{request.steps}`", inline=True)
    embed.add_field(name="CFG", value=f"`{request.guidance_scale}`", inline=True)
    if request.seed is not None:
        embed.add_field(name="Seed", value=f"`{request.seed}`", inline=True)
    embed.set_footer(text=f"Eclipse Legends Image | Pedido por {getattr(author, 'display_name', author)}")
    embed.set_image(url="attachment://eclipse_imagem.png")
    return embed
