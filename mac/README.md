# Mac setup

`config.rag_adapted.mac.json` is `config.rag_adapted.json` adjusted for a MacBook:

- `llama_server_path` is `/opt/homebrew/bin/llama-server` (install with `brew install llama.cpp`; check the path with `which llama-server`).
- `host` is `0.0.0.0` so a phone on the same Wi-Fi can open the app. There is no login, so use it only on a trusted network. Use `127.0.0.1` to keep it on this computer only.

How to use:

1. Copy the file to the project root as `config.rag_adapted.json` (replace the original).
2. Make sure `app/config.py` and `app/main.py` contain the host check for `0.0.0.0` and the CORS middleware (both are already in this repository).
3. Run: `.venv/bin/python run.py --config config.rag_adapted.json`

The model and the BGE cache come from `AITU_Runtime_Current.zip`. On a Mac only `models/aitu-contextual-q4_k_m.gguf` is needed from that archive; the `vendor/` folder (Windows `.exe` and DLL files) is not used.
