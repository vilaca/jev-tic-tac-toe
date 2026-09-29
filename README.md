# Tic-tac-toe against Jev

A terminal tic-tac-toe game: you are X, [Jev](https://docs.typesafe.ai) is O.

Jev (from TypeSafe) is a **decision model**, not a chatbot and not a game engine. On each of its turns it gets the board plus every row, column and diagonal, and one `choice` question whose options are only the empty squares, so it can never make an illegal move. After each move the game prints Jev's top probabilities. It will sometimes miss a win or a block.

## Requirements

- Python 3. The game uses only the standard library. The tests need Python 3.11 or later.
- A Jev server: the hosted Jev, or a local Jev-compatible server such as OpenJev.

## Jev server

### Hosted

Set one of these keys:

- **TypeSafe direct**: `TYPESAFE_API_KEY`, from https://console.typesafe.ai/keys. New signups were reported paused in Sept 2026.
- **OpenRouter**: `OPENROUTER_API_KEY`, from https://openrouter.ai/keys. The game uses the model `typesafe/jev-1.13`.

### Local (OpenJev on MLX)

Jev's weights are not public, but [razorback16/openjev](https://github.com/razorback16/openjev) serves the same API. Its probabilities are not calibrated the way Jev's are. Besides the clone, the MLX backend needs:

- an Apple silicon Mac with about 16 GB of free memory
- Python 3.10 or later
- about 16 GB of free disk space, and internet access on the first start, to download the 4-bit weights (`mlx-community/diffusiongemma-26B-A4B-it-4bit`) from Hugging Face

On an NVIDIA GPU, OpenJev runs through vLLM instead. That needs a GPU with at least 24 GB of memory, Docker with GPU support (`--gpus all`) for the prebuilt `razorback16/openjev` image, which runs on CUDA 13, and about 18 GB of disk for the weights. See its README.

Install it once, from this folder. The `pip install` brings in the rest: `mlx-vlm`, FastAPI, uvicorn and transformers.

```sh
git clone https://github.com/razorback16/openjev
python3 -m venv .venv
.venv/bin/pip install -e './openjev[mlx]'
```

Then start the server. The first start downloads the weights into `~/.cache/huggingface`.

```sh
cd openjev && OPENJEV_BACKEND=mlx ../.venv/bin/python -m openjev   # serves 127.0.0.1:8080
```

Start it from inside `openjev/`. From this folder, Python picks up the cloned folder instead of the package and fails with `cannot import name '__version__'`.

### Which server the game uses

The first match wins:

1. `JEV_URL`: any Jev-compatible server, e.g. `http://127.0.0.1:8080/v1/systemone`. `JEV_MODEL` sets the model name (default `jev-latest`).
2. `TYPESAFE_API_KEY`
3. `OPENROUTER_API_KEY`
4. Nothing set: OpenJev on `127.0.0.1:8080`.

`JEV_TIMEOUT` sets how many seconds to wait for Jev's move (default 30).

## Play

```sh
python3 tictactoe.py
```

Pick a square by its number, or `q` to quit. Who goes first alternates between games. The score (your wins, Jev's wins, draws) is shown above the board and saved to `tictactoe-score.json` after each game, so it carries over between runs. Delete that file to reset it.

## Tests

The tests mock the Jev calls, so they need no server and never touch your score file:

```sh
python3 -m unittest test_tictactoe
```

## License

MIT, see [LICENSE](LICENSE).
