# genesis — terminal client (Linux · macOS · Windows)

Needs only **Python 3.8+**. No packages to install.

## Install

**Linux / macOS**

```sh
sh install.sh http://127.0.0.1:8000
GENESIS_URL=http://127.0.0.1:8000 genesis status
```

**Windows (PowerShell)**

```powershell
powershell -ExecutionPolicy Bypass -File install.ps1 -Server http://127.0.0.1:8000
$env:GENESIS_URL='http://127.0.0.1:8000'; py $HOME\.genesis\genesis status
```

Point `GENESIS_URL` at the hosted server to use Genesis online,
or run your own engine (see below) and keep the default.

## Use

```sh
genesis new "Build me a website for my clothing business"
genesis questions <id>        # stack choices (db, cache, payments)
genesis build <id> --db sqlite
genesis download <id>         # runnable zip + SETUP.md
genesis chat <id> "add a contact page"
genesis status                # models, agents, tools backing you

# aggressive mode: one command, no stops, recommended answers
genesis auto "Build me a playable snake game with a high-score board"

# bring existing code: upload first, describe the change, build
genesis upload ./mysite.zip
genesis policy <id> off       # back to ask-everything (default is autopilot on)
```

## Full authority on your machine

The CLI above drives a server. To own the whole engine locally:

1. Download the engine pack: `<server>/api/download/engine`
2. Unzip it anywhere, then: `pip install fastapi uvicorn`
3. `GENESIS_HOME=<that folder> genesis serve`

The engine builds, runs, tests and verifies on your machine —
same pipeline as the website, nothing simulated.
