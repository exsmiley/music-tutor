# transcription

Song → per-instrument tabs, powering the Tab Player module in the web app.

Pipeline (`pipeline/run.py`): yt-dlp (fetch) → librosa (beat tracking) →
Demucs `htdemucs_6s` (split into vocals / drums / bass / guitar / piano /
other) → basic-pitch (stem → note events, per-stem thresholds + amplitude
filtering) → beam-search tab solver (notes → string/fret, style-weighted per
instrument, phrase-level octave smoothing for vocals) → ASCII tab, JSON
(with 16th-note grid), and MIDI. Drums get onset-detected kick/snare/hihat
events (MIDI playback only, no tab).

Everything becomes a **guitar tab** except bass (bass tab) and drums.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Requires `ffmpeg` on PATH.

## API server (used by the web app)

```bash
.venv/bin/uvicorn server:app --port 8000
```

The Vite dev server proxies `/api` here. Jobs are stored in `data/<id>/` with
`meta.json` for status; one job runs at a time.

## CLI

```bash
.venv/bin/python transcribe.py "https://youtube.com/watch?v=..." --out out/song
.venv/bin/python transcribe.py song.mp3 --instruments guitar,bass,vocals
.venv/bin/python transcribe.py song.mp3 --no-separate   # tab the whole mix
```

## Evaluation

```bash
.venv/bin/python tests/eval_pipeline.py
```

Synthesizes melody/bass with known notes and reports note-level P/R/F1
(baseline: melody F1 ≈ 0.95, bass ≈ 0.83; extras are synth harmonics).

## Known limitations

- Meter is assumed 4/4; beat tracking gives tempo but not time signature.
- Transcription is a draft: expect octave errors and missed ghost notes,
  especially in dense mixes.
- Demucs runs on CPU by default (a few minutes per song); `--device mps`
  may help on Apple Silicon.
- The web app loads alphaTab from `public/alphatab/` (classic script — its
  Vite plugin is incompatible with Vite 7's rolldown). When upgrading the
  `@coderline/alphatab` npm package, re-copy `dist/alphaTab.min.js`,
  `dist/font/`, and `dist/soundfont/sonivox.sf2` into `public/alphatab/`.
