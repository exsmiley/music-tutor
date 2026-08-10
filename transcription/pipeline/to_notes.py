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
    return clean_events(events)


CO_ONSET = 0.08       # notes starting within 80ms count as simultaneous
# Harmonic ghost intervals above/below a stronger co-onset note, with the
# amplitude ratio below which the weaker note is considered a ghost. The +19
# (octave+fifth, 3rd harmonic) ratio is stricter so real power chords —
# played at similar volume — survive.
GHOST_INTERVALS = {12: 0.8, 24: 0.8, 19: 0.6}
BLEED_AMP_RATIO = 0.25  # notes this much quieter than concurrent notes = bleed
STUTTER_GAP = 0.06    # same-pitch retrigger gaps shorter than this get merged


def clean_events(events: list[NoteEvent]) -> list[NoteEvent]:
    """Remove common basic-pitch artifacts.

    - octave ghosts: a quieter note starting simultaneously 1-2 octaves from a
      stronger one is almost always a detected harmonic, not a played note
    - bleed: notes far quieter than everything sounding around them
    - stutters: the same pitch re-triggered after a tiny gap is one note
    """
    # Octave ghosts.
    ghosts: set[int] = set()
    for i, a in enumerate(events):
        for j in range(i + 1, len(events)):
            b = events[j]
            if b.start - a.start > CO_ONSET:
                break
            ratio = GHOST_INTERVALS.get(abs(a.midi - b.midi))
            if ratio is not None:
                weak_i, weak = (i, a) if a.amplitude < b.amplitude else (j, b)
                strong = b if weak is a else a
                if weak.amplitude < strong.amplitude * ratio:
                    ghosts.add(weak_i)
    events = [e for i, e in enumerate(events) if i not in ghosts]

    # Bleed: quiet notes overlapped by much louder ones.
    kept: list[NoteEvent] = []
    for i, e in enumerate(events):
        loudest = max(
            (o.amplitude for o in events if o is not e and o.start < e.end and e.start < o.end),
            default=0.0,
        )
        if loudest == 0.0 or e.amplitude >= loudest * BLEED_AMP_RATIO:
            kept.append(e)
    events = kept

    # Stutters: merge same-pitch notes separated by a tiny gap.
    merged: list[NoteEvent] = []
    last_by_pitch: dict[int, NoteEvent] = {}
    for e in events:
        prev = last_by_pitch.get(e.midi)
        if prev is not None and e.start - prev.end < STUTTER_GAP:
            prev.end = max(prev.end, e.end)
            prev.amplitude = max(prev.amplitude, e.amplitude)
            continue
        merged.append(e)
        last_by_pitch[e.midi] = e
    merged.sort(key=lambda n: (n.start, n.midi))
    return merged
