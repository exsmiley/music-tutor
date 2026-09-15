"""Pipeline orchestration, shared by the CLI (transcribe.py) and API (server.py)."""

import shutil
import subprocess
from pathlib import Path
from typing import Callable

from .download import fetch_audio
from .separate import separate, detect_present, STEMS, PRESENCE_RATIO
from . import multitrack, techniques
from .to_notes import stem_to_notes
from .mono_pitch import track_mono
from .tab_solver import solve, GUITAR_TUNING, BASS_TUNING
from .render import to_ascii, to_json, to_midi
from .quantize import track_beats

TRANSCRIBABLE = [s for s in STEMS if s != "drums"]

# Per-stem basic-pitch settings: (onset_threshold, frame_threshold, min_amplitude).
# Vocals and bass carry bleed from other instruments, so they filter harder.
STEM_SETTINGS: dict[str, tuple[float, float, float]] = {
    "guitar": (0.5, 0.3, 0.20),
    "bass": (0.5, 0.3, 0.20),
    "vocals": (0.6, 0.35, 0.20),
    "other": (0.55, 0.3, 0.20),
    "piano": (0.5, 0.3, 0.15),
    "mix": (0.5, 0.3, 0.15),
}


def run_pipeline(
    source: str,
    out: Path,
    instruments: list[str] | None = None,
    device: str = "cpu",
    no_separate: bool = False,
    with_drums: bool = True,
    progress: Callable[[str], None] = print,
) -> dict:
    """Run the full pipeline; returns a summary dict (stems, tempo, files)."""
    out.mkdir(parents=True, exist_ok=True)
    workdir = out / "work"
    workdir.mkdir(exist_ok=True)

    progress("downloading audio")
    wav = fetch_audio(source, workdir)

    progress("tracking beats")
    grid = track_beats(wav)

    # Keep a compressed copy of the source for the play-along UI.
    source_mp3 = out / "source.mp3"
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(wav), "-codec:a", "libmp3lame", "-b:a", "128k",
         str(source_mp3)],
        check=True, capture_output=True,
    )

    energy: dict[str, float] = {}
    if no_separate:
        stems = {"mix": wav}
        wanted = ["mix"]
    else:
        progress("separating stems (slowest step)")
        stems = separate(wav, workdir, device=device)
        energy = detect_present(stems)
        if instruments:
            unknown = set(instruments) - set(TRANSCRIBABLE)
            if unknown:
                raise ValueError(f"unknown instruments: {sorted(unknown)}")
            wanted = list(instruments)
        else:
            wanted = [s for s in TRANSCRIBABLE if energy[s] >= PRESENCE_RATIO]

    solved: dict[str, list] = {}
    for stem in wanted:
        progress(f"transcribing {stem}")
        onset, frame, min_amp = STEM_SETTINGS.get(stem, STEM_SETTINGS["mix"])

        # A guitar stem may hold two players (Demucs separates by instrument
        # class); multitrack tries stereo and rhythm/lead splits.
        if stem == "guitar" and not no_separate:
            parts = multitrack.guitar_parts(
                stems[stem], workdir, onset, frame, min_amp, progress
            )
        elif stem in ("bass", "vocals") and not no_separate:
            # Single-voice stems: a dedicated monophonic tracker (SwiftF0) is
            # far cleaner here than basic-pitch — it can't invent a second
            # note, so octave errors and over-detection largely vanish.
            events = track_mono(stems[stem], kind=stem)
            parts = [(stem, events)]
        else:
            events = stem_to_notes(
                stems[stem], onset_threshold=onset, frame_threshold=frame, min_amplitude=min_amp
            )
            parts = [(stem, events)]

        for part_name, events in parts:
            if stem == "vocals":
                # Vocals glide constantly (vibrato, portamento); annotating
                # that would drown the tab. Strip the raw bend data.
                for e in events:
                    e.bend = 0.0
            else:
                # Bend/slide notation for instrument stems. Bass keeps slides
                # but not bends — bass bends are rare and noise dominates.
                events = techniques.annotate(events, allow_bends=(stem != "bass"))
            tuning = BASS_TUNING if stem == "bass" else GUITAR_TUNING
            style = "bass" if stem == "bass" else ("melody" if stem == "vocals" else "guitar")
            notes = solve(events, tuning, style=style)
            solved[part_name] = notes

            to_json(notes, part_name, out / f"{part_name}.json", grid=grid)
            (out / f"{part_name}.tab.txt").write_text(to_ascii(notes, len(tuning)))
            to_midi({part_name: notes}, out / f"{part_name}.mid")

    drum_events = []
    if with_drums and not no_separate and energy.get("drums", 0) >= PRESENCE_RATIO:
        progress("detecting drums")
        from .drums import stem_to_drums, drums_to_json
        import json as _json

        drum_events = stem_to_drums(stems["drums"])
        (out / "drums.json").write_text(_json.dumps(drums_to_json(drum_events), indent=2))

    if solved:
        to_midi(solved, out / "song.mid", drums=drum_events)

    shutil.rmtree(workdir, ignore_errors=True)
    return {
        "stems": list(solved.keys()),
        "drums": len(drum_events) > 0,
        "tempo": round(grid.tempo, 2),
        "energy": {k: round(v, 3) for k, v in energy.items()},
    }
