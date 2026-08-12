# 🎧 VocalRy

**AI stem separation & binaural 8D mixing studio.**

Upload any song, pick which stems you want — vocals, drums, bass, guitar, piano,
or everything — and VocalRy separates them with state-of-the-art neural models.
Optionally render a cinematic binaural 8D mix with real head-related transfer
functions (MIT KEMAR HRTF data) that orbits each stem around your head.

All processing is **local, private, and offline** — your music never leaves your
machine.

---

## Features

- **6-stem AI separation** — vocals, drums, bass, guitar, piano, other (htdemucs_6s)
- **4-stem fast mode** — htdemucs_ft
- **2-stem quick split** — vocals / instrumental (MDX23C)
- **Model auto-selection** — pick stems, the right model is chosen for you
- **Binaural 8D mixing** — per-stem circular paths through KEMAR HRTF filters + room reverb + streaming loudness mastering (-14 LUFS)
- **Sequential job queue** — up to 5 songs queued, processed one after another
- **Drag-and-drop web UI** — presets, live progress, per-stem downloads, zip export

## Quick start (developer)

```bash
pip install -r requirements.txt
uvicorn main:app --port 8000
# open http://127.0.0.1:8000
```

## Run with Docker

```bash
docker build -t vocalry .
docker run -p 8000:8000 -v vocalry-data:/data vocalry
```

## Build the desktop app (macOS / Linux / Windows)

```bash
./build_app.sh        # builds the PyInstaller backend + Tauri app
```

Produces a native app bundle: `src-tauri/target/release/bundle/`

> macOS apps must be built on a Mac (Apple toolchain restriction). CI builds
> it for you automatically on every version tag — see `.github/workflows/build.yml`.

## API

| Method | Path | Description |
|---|---|---|
| `GET`  | `/api/jobs` | list jobs |
| `POST` | `/api/jobs` | upload song + stem selection (multipart: `file`, `stems`, `make_8d`) |
| `GET`  | `/api/jobs/{id}` | job status & progress |
| `GET`  | `/api/jobs/{id}/files/{name}` | download a stem / 8D mix |
| `GET`  | `/api/jobs/{id}/zip` | download all outputs as zip |

## Architecture

```
static/          drag-and-drop web UI
main.py          FastAPI server (API, downloads)
worker.py        async job queue, model auto-select, in-process separation
renderer/        binaural 8D renderer + KEMAR HRTF dataset
src-tauri/       Rust/Tauri desktop shell (spawns the backend as a sidecar)
backend.spec     PyInstaller recipe for the self-contained backend binary
```

## License

[MIT](LICENSE)
