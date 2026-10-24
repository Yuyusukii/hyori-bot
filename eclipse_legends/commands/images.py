# Comandos de geracao de imagem.
from ..core import *
from ..image_generation import *


@commands.cooldown(1, 60, commands.BucketType.user)
@bot.command(name="imagem", aliases=["img", "gerarimagem", "gerarimg", "sd"])
async def imagem(ctx, *, prompt: str = None):
    try:
        request = parse_image_request(prompt)
    except ValueError as exc:
        await ctx.send(f"❌ {exc}")
        return

    aviso = await ctx.send(f"🎨 Gerando imagem com `{request.model_alias}`... isso pode levar alguns segundos.")
    try:
        buffer = await gerar_imagem_huggingface(request)
    except Exception as exc:
        await aviso.edit(content=f"❌ Nao consegui gerar a imagem: `{exc}`")
        return

    arquivo = discord.File(buffer, filename="eclipse_imagem.png")
    embed = embed_imagem_gerada(request, ctx.author)
    await aviso.edit(content=None, embed=embed, attachments=[arquivo])


@commands.cooldown(1, 60, commands.BucketType.user)
@bot.command(name="flux", aliases=["fluximg", "fluximagem"])
async def flux_imagem(ctx, *, prompt: str = None):
    if not prompt:
        await ctx.send("Use: `!flux seu prompt aqui`.")
        return
    await imagem.callback(ctx, prompt=f"--modelo flux {prompt}")


@commands.cooldown(1, 60, commands.BucketType.user)
@bot.command(name="fluxuncensored", aliases=["fluxun", "fluxnsfw"])
async def flux_uncensored_imagem(ctx, *, prompt: str = None):
    if not prompt:
        await ctx.send("Use: `!fluxuncensored seu prompt aqui`.")
        return
    await imagem.callback(ctx, prompt=f"--modelo flux_uncensored {prompt}")


@bot.command(name="imageminfo", aliases=["imginfo", "sdinfo"])
async def imagem_info(ctx):
    token_ok = "configurado" if hf_image_token() else "faltando"
    modelos = hf_image_models()
    embed = embed_padrao(
        "🎨 Geracao de Imagem",
        "Use Hugging Face para gerar imagens por prompt com Stable Diffusion ou Flux.",
        discord.Color.from_rgb(255, 102, 204),
    )
    embed.add_field(name="Comando", value="`!imagem seu prompt aqui`", inline=False)
    embed.add_field(
        name="Opcoes",
        value=(
            "`--wide` paisagem\n"
            "`--vertical` retrato\n"
            "`--modelo stable` Stable Diffusion\n"
            "`--modelo flux` Flux Schnell\n"
            "`--modelo flux_uncensored` Flux Uncensored (endpoint dedicado se necessario)\n"
            "`!flux prompt` atalho para Flux Schnell\n"
            "`--seed 12345`\n"
            "`--steps 30`\n"
            "`--cfg 7.5`\n"
            "`--neg \"texto negativo\"`"
        ),
        inline=False,
    )
    embed.add_field(name="Stable Diffusion", value=f"`{modelos['stable']}`", inline=False)
    embed.add_field(name="Flux Schnell", value=f"`{modelos['flux']}`", inline=False)
    embed.add_field(name="Flux Uncensored", value=f"`{modelos['flux_uncensored']}`", inline=False)
    embed.add_field(name="Token HF", value=f"`{token_ok}`", inline=True)
    await ctx.send(embed=embed)


@bot.command(name="imagemmodelos", aliases=["imgmodelos", "modelosimagem"])
async def imagem_modelos(ctx):
    modelos = hf_image_models()
    embed = embed_padrao(
        "🎨 Modelos de Imagem",
        "Escolha com `--modelo stable`, `--modelo flux` ou `--modelo flux_uncensored`.",
        discord.Color.from_rgb(255, 102, 204),
    )
    embed.add_field(name="Stable Diffusion", value=f"`{modelos['stable']}`", inline=False)
    embed.add_field(name="Flux Schnell", value=f"`{modelos['flux']}`", inline=False)
    embed.add_field(name="Flux Uncensored", value=f"`{modelos['flux_uncensored']}`", inline=False)
    embed.add_field(
        name="Exemplos",
        value=(
            "`!imagem castelo magico --modelo stable --wide`\n"
            "`!imagem guerreira cyberpunk --modelo flux --vertical`\n"
            "`!flux dragao celestial, cinematic lighting`\n"
            "`!fluxuncensored prompt`"
        ),
        inline=False,
    )
    await ctx.send(embed=embed)
