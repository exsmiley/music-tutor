"""Audio stem -> note events via Spotify basic-pitch."""

from dataclasses import dataclass
from pathlib import Path


@dataclass
class NoteEvent:
    start: float      # seconds
    end: float        # seconds
    midi: int
    amplitude: float  # 0..1


def stem_to_notes(
    wav: Path,
    onset_threshold: float = 0.5,
    frame_threshold: float = 0.3,
    min_note_len_ms: float = 60.0,
    min_amplitude: float = 0.0,
) -> list[NoteEvent]:
    # Imported lazily: basic_pitch pulls in its ML runtime on import.
    from basic_pitch.inference import predict

    _, _, note_events = predict(
        str(wav),
        onset_threshold=onset_threshold,
        frame_threshold=frame_threshold,
        minimum_note_length=min_note_len_ms,
    )
    events = [
        NoteEvent(start=float(s), end=float(e), midi=int(p), amplitude=float(a))
        for s, e, p, a, _bends in note_events
        if a >= min_amplitude
    ]
    events.sort(key=lambda n: (n.start, n.midi))
    return events
