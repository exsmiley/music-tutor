"""Ground-truth evaluation of transcription + tab solving.

Synthesizes a melody and bass line with known notes, runs them through
basic-pitch and the tab solver, and reports note-level precision/recall/F1.

Run:  .venv/bin/python tests/eval_pipeline.py
"""

import sys
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.to_notes import stem_to_notes  # noqa: E402
from pipeline.tab_solver import solve, GUITAR_TUNING, BASS_TUNING  # noqa: E402

SR = 44100
ONSET_TOLERANCE = 0.1  # seconds


def pluck(midi: float, dur: float, amp: float = 0.5) -> np.ndarray:
    f = 440 * 2 ** ((midi - 69) / 12)
    t = np.arange(int(SR * dur)) / SR
    env = np.exp(-3 * t)
    sig = sum((0.5**k) * np.sin(2 * np.pi * f * (k + 1) * t) for k in range(3))
    return amp * env * sig


def render(notes: list[tuple[float, int, float]], total: float) -> np.ndarray:
    out = np.zeros(int(SR * total))
    for start, midi, dur in notes:
        s = pluck(midi, dur)
        i = int(SR * start)
        out[i : i + len(s)] += s
    peak = np.abs(out).max()
    return out / (peak * 1.1) if peak > 0 else out


def score(truth: list[tuple[float, int, float]], found, octave_tolerant: bool) -> tuple[int, int, int]:
    """Greedy onset+pitch matching; returns (hits, misses, extras)."""
    unmatched = list(truth)
    hits = 0
    for note in found:
        for i, (t_start, t_midi, _) in enumerate(unmatched):
            pitch_ok = (
                note.midi % 12 == t_midi % 12 if octave_tolerant else note.midi == t_midi
            )
            if pitch_ok and abs(note.start - t_start) <= ONSET_TOLERANCE:
                unmatched.pop(i)
                hits += 1
                break
    return hits, len(unmatched), len(found) - hits


def evaluate(name: str, truth, wav_path: Path, tuning, style: str) -> None:
    events = stem_to_notes(wav_path)
    notes = solve(events, tuning, style=style)

    for label, octave_tolerant in [("exact pitch", False), ("pitch-class (octave-tolerant)", True)]:
        hits, misses, extras = score(truth, notes, octave_tolerant)
        precision = hits / (hits + extras) if hits + extras else 0.0
        recall = hits / (hits + misses) if hits + misses else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        print(
            f"  {name:8s} {label:30s} P={precision:.2f} R={recall:.2f} F1={f1:.2f} "
            f"(hits={hits} missed={misses} extra={extras})"
        )

    # Tab playability: fret span per beam-searched hand position.
    frets = [n.fret for n in notes if n.fret > 0]
    if frets:
        print(f"  {name:8s} fret range used: {min(frets)}-{max(frets)}")


def main() -> None:
    # C major melody phrase, quarter notes at 120 BPM.
    melody = [(i * 0.5, m, 0.4) for i, m in enumerate([60, 62, 64, 65, 67, 69, 67, 64, 62, 60])]
    # Simple root-note bassline.
    bass = [(i * 1.0, m, 0.8) for i, m in enumerate([36, 43, 45, 40, 36])]

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        melody_wav = tmp_path / "melody.wav"
        bass_wav = tmp_path / "bass.wav"
        sf.write(melody_wav, np.stack([render(melody, 6)] * 2, 1), SR)
        sf.write(bass_wav, np.stack([render(bass, 6)] * 2, 1), SR)

        print("note-level accuracy against synthesized ground truth:")
        evaluate("melody", melody, melody_wav, GUITAR_TUNING, "melody")
        evaluate("bass", bass, bass_wav, BASS_TUNING, "bass")


if __name__ == "__main__":
    main()
