"""Monophonic pitch tracking for single-voice stems (bass, vocals) via SwiftF0.

basic-pitch over-detects and octave-errors badly on one-note-at-a-time stems.
A dedicated f0 tracker estimates a single pitch per frame and cannot invent a
second simultaneous note, so octave errors and doubled notes largely vanish
(measured on real material: bass octave-jumps dropped ~18% -> ~3%).

SwiftF0's model floor is ~47 Hz, below the lowest bass notes (E1 = 41 Hz), so
the bass stem is analysed an octave up and the detected pitches shifted back
down — this both stays inside the model's range and recovers the low notes.
"""

from pathlib import Path

from .to_notes import NoteEvent

# kind: (fmin, fmax, octave_shift_semitones, confidence_threshold)
# For bass, shift the audio +12 semitones into the model's range, then subtract
# 12 from the detected MIDI. Vocals sit comfortably above the floor already.
SETTINGS = {
    "bass": (70.0, 800.0, 12, 0.90),
    "vocals": (80.0, 1200.0, 0, 0.90),
}

_TRACKERS: dict[tuple, object] = {}


def track_mono(wav: Path, kind: str) -> list[NoteEvent]:
    """Return note events for a monophonic stem using SwiftF0."""
    import librosa
    from swift_f0 import SwiftF0, segment_notes

    fmin, fmax, shift, conf = SETTINGS[kind]
    y, sr = librosa.load(str(wav), sr=16000, mono=True)
    if shift:
        y = librosa.effects.pitch_shift(y, sr=sr, n_steps=shift)

    key = (fmin, fmax, conf)
    tracker = _TRACKERS.get(key)
    if tracker is None:
        tracker = SwiftF0(fmin=fmin, fmax=fmax, confidence_threshold=conf)
        _TRACKERS[key] = tracker

    result = tracker.detect_from_array(y, sr)
    notes = segment_notes(result, min_note_duration=0.06)

    ts = result.timestamps
    conf_arr = result.confidence
    events: list[NoteEvent] = []
    for n in notes:
        # Mean per-frame confidence over the note's span -> amplitude (0..1).
        mask = (ts >= n.start) & (ts <= n.end)
        amp = float(conf_arr[mask].mean()) if mask.any() else conf
        events.append(
            NoteEvent(
                start=float(n.start),
                end=float(n.end),
                midi=int(n.pitch_midi) - shift,
                amplitude=amp,
            )
        )
    events.sort(key=lambda e: (e.start, e.midi))
    return events
