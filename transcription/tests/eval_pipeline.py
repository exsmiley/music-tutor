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


def tone_glide(m0: float, m1: float, dur: float, amp: float = 0.5) -> np.ndarray:
    """Tone gliding from midi m0 to m1 (for bend/slide synthesis)."""
    t = np.arange(int(SR * dur)) / SR
    midi = m0 + (m1 - m0) * (t / dur)
    freq = 440 * 2 ** ((midi - 69) / 12)
    phase = 2 * np.pi * np.cumsum(freq) / SR
    env = np.minimum(1, 10 * t) * np.exp(-1.5 * t)
    return amp * env * np.sin(phase)


def evaluate_techniques(tmp_path: Path) -> None:
    from pipeline import techniques

    clip = np.zeros(int(SR * 6))
    # bend: hold E4, bend up a whole step, hold F#4
    seg = np.concatenate([tone_glide(64, 64, 0.3), tone_glide(64, 66, 0.4), tone_glide(66, 66, 0.5)])
    clip[int(SR * 1) : int(SR * 1) + len(seg)] += seg
    # slide: G3 up to D4
    seg = np.concatenate([tone_glide(55, 55, 0.2), tone_glide(55, 62, 0.5), tone_glide(62, 62, 0.6)])
    clip[int(SR * 3) : int(SR * 3) + len(seg)] += seg

    wav = tmp_path / "techniques.wav"
    sf.write(wav, np.stack([clip] * 2, 1), SR)
    events = techniques.annotate(stem_to_notes(wav))
    bends = [e for e in events if e.bend > 0]
    slides = [e for e in events if e.slide]
    # detection may center the bent note on 64 or 65; either counts
    bend_ok = any(e.midi in (64, 65) and 1.0 <= e.bend <= 2.0 for e in bends)
    slide_ok = any(e.slide and e.midi == 55 for e in events)
    print(f"  bend     detected={bend_ok} ({[(e.midi, e.bend) for e in bends]})")
    print(f"  slide    detected={slide_ok} ({[(e.midi) for e in slides]})")


def evaluate_multitrack() -> None:
    from pipeline.multitrack import note_similarity, split_voices
    from pipeline.to_notes import NoteEvent

    def mk(seq, dur=0.2):
        return [NoteEvent(t, t + dur, m, 0.7) for t, m in seq]

    same = mk([(i * 0.5, 60 + i) for i in range(20)])
    sim_same, _ = note_similarity(same, list(same))
    different = mk([(i * 0.5, 48 + (i % 5)) for i in range(20)])
    sim_diff, _ = note_similarity(same, different)
    print(f"  similarity identical={sim_same:.2f} (want 1.0), different={sim_diff:.2f} (want <0.5)")

    # rhythm: E2/B2/E3 chords on beats; lead: melody around E4-A4 offbeat
    rhythm = []
    for i in range(30):
        t = i * 0.5
        rhythm += [(t, 40), (t, 47), (t, 52)]
    lead = [(i * 0.5 + 0.25, 64 + (i % 6)) for i in range(30)]
    parts = split_voices(sorted(mk(rhythm) + mk(lead), key=lambda n: (n.start, n.midi)))
    names = [name for name, _ in parts]
    sizes = {name: len(ev) for name, ev in parts}
    print(f"  voice split -> {names} sizes={sizes} (want lead+rhythm)")

    single = split_voices(mk([(i * 0.25, 55 + (i % 8)) for i in range(100)]))
    print(f"  single line stays whole -> {[n for n, _ in single]} (want ['guitar'])")


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
        print("technique detection:")
        evaluate_techniques(tmp_path)
    print("multitrack splitting:")
    evaluate_multitrack()


if __name__ == "__main__":
    main()
