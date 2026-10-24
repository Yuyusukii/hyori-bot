# Estrutura do Eclipse Legends

O `bot.py` agora e apenas a entrada do bot. A logica principal fica em `eclipse_legends/`.

## Arquivos principais

- `bot.py`: inicia o bot.
- `eclipse_legends/app.py`: carrega os modulos e executa o bot.
- `eclipse_legends/core.py`: imports, configuracoes, constantes e dados base.
- `eclipse_legends/database.py`: conexao SQLite, tabelas e migracoes.
- `eclipse_legends/rpg.py`: helpers do RPG.
- `eclipse_legends/gacha.py`: helpers, catalogo e view da colecao gacha.
- `eclipse_legends/social.py`: Social/Aura e card visual do perfil.
- `eclipse_legends/music.py`: YouTube, fila, call e painel de musica.
- `eclipse_legends/image_generation.py`: geracao de imagem via Hugging Face/Stable Diffusion.
- `eclipse_legends/local_server.py`: pagina de status local, ativa somente durante a execucao do bot.
- `eclipse_legends/events.py`: eventos do Discord.

## Comandos

Os comandos ficam em `eclipse_legends/commands/`:

- `help_rpg.py`: ajuda, cadastro, comandos iniciais e musica.
- `economy.py`: inventario, loja e mercado.
- `adventure.py`: exploracao e combate.
- `quests.py`: quests e historia.
- `guilds.py`: PvP, guildas, boss, evolucao e rankings RPG.
- `social.py`: perfil social, reputacao, titulos e rankings sociais.
- `gacha_admin.py`: gacha e comandos administrativos.
- `images.py`: comandos `!imagem` e `!imageminfo`.
- `utility.py`: utilidades e tratamento de erros.

## Variaveis no `.env`

Configuracoes pessoais podem ficar em `.env.local`; quando a mesma chave existir nos dois
arquivos, o valor de `.env.local` prevalece. Variaveis definidas pelo Windows continuam tendo
prioridade sobre ambos.

- `DISCORD_TOKEN`: token do bot.
- `HUGGINGFACE_TOKEN` ou `HF_TOKEN`: token da Hugging Face com permissao de Inference Providers.
- `HF_IMAGE_MODEL`: modelo padrao de Stable Diffusion. Padrao: `stabilityai/stable-diffusion-3-medium-diffusers`.
- `HF_IMAGE_MODEL_FLUX`: modelo usado quando o comando recebe `--modelo flux`. Padrao: `black-forest-labs/FLUX.1-schnell`.
- `HF_IMAGE_MODEL_FLUX_UNCENSORED`: modelo usado quando o comando recebe `--modelo flux_uncensored`.
- `HF_IMAGE_ENDPOINT`: endpoint opcional caso voce use um Inference Endpoint dedicado.
- `HF_IMAGE_ENDPOINT_FLUX_UNCENSORED`: endpoint dedicado opcional para Flux Uncensored.
- `LOCAL_SERVER_ENABLED`: ativa ou desativa o servidor local. Padrao: `true`.
- `LOCAL_SERVER_HOST`: endereco local. Padrao seguro: `127.0.0.1`.
- `LOCAL_SERVER_PORT`: porta da pagina e do endpoint `/health`. Padrao: `8080`.

Ao iniciar pelo `bot.bat`, a pagina fica disponivel em `http://127.0.0.1:8080/`.
Como ela roda no mesmo processo do bot, tambem e encerrada quando a janela do bot fecha.

Para adicionar uma nova funcao grande, prefira criar helpers no modulo do sistema e deixar o comando no arquivo correspondente dentro de `commands/`.
