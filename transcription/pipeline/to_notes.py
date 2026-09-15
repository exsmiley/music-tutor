"""Audio stem -> note events via Spotify basic-pitch."""

from dataclasses import dataclass
from pathlib import Path


@dataclass
class NoteEvent:
    start: float      # seconds
    end: float        # seconds
    midi: int
    amplitude: float  # 0..1
    bend: float = 0.0  # semitones of upward bend within the note (peak)
    bend_tail: float = 0.0  # rise still present at the note's end
    slide: bool = False  # slides into the next event


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
    events = []
    for s, e, p, a, bends in note_events:
        if a < min_amplitude:
            continue
        # bends are in 1/3-semitone bins relative to an arbitrary baseline;
        # the in-note rise (peak minus start) is what a string bend looks
        # like. Median-of-3 smoothing kills single-frame spikes; the tail
        # rise (end minus start) marks bends that continue past the note,
        # which is what distinguishes a split bend from a melodic step.
        rise = tail = 0.0
        if bends is not None and len(bends) > 2:
            sm = [
                sorted(bends[max(0, k - 1) : k + 2])[len(bends[max(0, k - 1) : k + 2]) // 2]
                for k in range(len(bends))
            ]
            rise = max(0.0, (max(sm) - sm[0]) / 3.0)
            tail = max(0.0, (sm[-1] - sm[0]) / 3.0)
        events.append(
            NoteEvent(
                start=float(s), end=float(e), midi=int(p), amplitude=float(a),
                bend=rise, bend_tail=tail,
            )
        )
    events.sort(key=lambda n: (n.start, n.midi))
    return clean_events(events)


CO_ONSET = 0.08       # notes starting within 80ms count as simultaneous
# Harmonic ghost intervals above/below a stronger co-onset note, with the
# amplitude ratio below which the weaker note is considered a ghost. The +19
# (octave+fifth, 3rd harmonic) ratio is stricter so real power chords —
# played at similar volume — survive.
GHOST_INTERVALS = {12: 0.85, 24: 0.85, 19: 0.6}
BLEED_AMP_RATIO = 0.30  # notes this much quieter than concurrent notes = bleed
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

    events = _despike_octaves(events)

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

    return _merge_stutters(events)


def prefer_monophonic(events: list[NoteEvent], keep: str = "low") -> list[NoteEvent]:
    """Collapse co-onset notes to one, for instruments that play one note at
    a time (bass, a single voice). keep='low' favors the lowest pitch (bass:
    artifacts are harmonics *above* the fundamental); keep='loud' favors the
    strongest (vocals: the lead line over harmony/artifacts)."""
    out: list[NoteEvent] = []
    group: list[NoteEvent] = []

    def flush() -> None:
        if not group:
            return
        best = min(group, key=lambda n: n.midi if keep == "low" else -n.amplitude)
        out.append(best)

    for e in events:
        if group and e.start - group[0].start > CO_ONSET:
            flush()
            group = []
        group.append(e)
    flush()
    return out


def _despike_octaves(events: list[NoteEvent]) -> list[NoteEvent]:
    """Pull single notes detected an octave off their neighbours back in line.

    basic-pitch occasionally places an isolated note a full octave from the
    surrounding melody. Only *isolated* notes (not overlapping either
    neighbour, so not part of a chord/voicing) whose two neighbours agree in
    pitch are corrected — a real octave leap has neighbours that disagree.
    """
    ev = sorted(events, key=lambda n: (n.start, n.midi))
    for i in range(1, len(ev) - 1):
        c, p, q = ev[i], ev[i - 1], ev[i + 1]
        if c.start < p.end - 0.02 or q.start < c.end - 0.02:
            continue  # overlaps a neighbour -> part of a chord, leave it
        if abs(p.midi - q.midi) > 2:
            continue  # neighbours disagree -> a real leap, not a spike
        for shift in (12, -12):
            if abs((c.midi + shift) - p.midi) <= 2 and abs((c.midi + shift) - q.midi) <= 2:
                c.midi += shift
                break
    return ev


def _merge_stutters(events: list[NoteEvent]) -> list[NoteEvent]:
    """Merge same-pitch notes separated by a tiny gap into one note."""
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
