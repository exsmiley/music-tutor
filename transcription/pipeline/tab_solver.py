"""Assign note events to (string, fret) positions.

Notes are grouped into chords by onset time, then a beam-search Viterbi picks
the assignment sequence that minimizes fretting-hand movement, chord fret span,
and high-fret usage. Notes outside the instrument's range are transposed by
octaves into range (needed for vocal stems routed to guitar tab).
"""

from dataclasses import dataclass
from itertools import product

from .to_notes import NoteEvent

# Tunings low string -> high string; rendering flips to high-first.
GUITAR_TUNING = [40, 45, 50, 55, 59, 64]  # E2 A2 D3 G3 B3 E4
BASS_TUNING = [28, 33, 38, 43]            # E1 A1 D2 G2
MAX_FRET = 19
CHORD_WINDOW = 0.05   # onsets within 50ms are one chord
BEAM_WIDTH = 24
MAX_CHORD_NOTES = 6


@dataclass
class TabNote:
    start: float
    end: float
    midi: int
    string: int  # 0 = lowest-pitched string
    fret: int


# Cost weights per playing style: (span, high_fret, movement, position).
# Bass lines move stepwise, so hand movement is penalized much harder there.
# The position weight pulls lines toward the open/low end of the neck.
STYLES = {
    "guitar": (1.5, 0.3, 1.0, 0.15),
    "bass": (2.0, 0.8, 3.0, 0.30),
    "melody": (1.5, 0.4, 2.0, 0.20),
}


def solve(
    events: list[NoteEvent],
    tuning: list[int] = GUITAR_TUNING,
    style: str = "guitar",
) -> list[TabNote]:
    if not events:
        return []
    chords = _group_chords(events)
    return _viterbi(chords, tuning, STYLES.get(style, STYLES["guitar"]))


def smooth_register(
    events: list[NoteEvent],
    tuning: list[int] = GUITAR_TUNING,
    phrase_gap: float = 1.0,
) -> list[NoteEvent]:
    """Octave-shift whole phrases (not single notes) into the instrument range.

    Meant for melodic sources like vocals: per-note octave folding makes the
    line leap between registers; shifting a phrase as a unit keeps its shape.
    A phrase is a run of notes with silences shorter than `phrase_gap`.
    """
    if not events:
        return []
    # A comfortable center for melodies: around the middle of the neck.
    center = (tuning[0] + tuning[-1] + MAX_FRET) / 2

    phrases: list[list[NoteEvent]] = [[events[0]]]
    for prev, ev in zip(events, events[1:]):
        if ev.start - prev.end > phrase_gap:
            phrases.append([])
        phrases[-1].append(ev)

    out: list[NoteEvent] = []
    for phrase in phrases:
        median = sorted(n.midi for n in phrase)[len(phrase) // 2]
        shift = 12 * round((center - median) / 12)
        for n in phrase:
            midi = _fit_to_range(n.midi + shift, tuning)
            out.append(NoteEvent(n.start, n.end, midi, n.amplitude))
    return out


def _fit_to_range(midi: int, tuning: list[int]) -> int:
    lo, hi = tuning[0], tuning[-1] + MAX_FRET
    while midi < lo:
        midi += 12
    while midi > hi:
        midi -= 12
    return midi


def _group_chords(events: list[NoteEvent]) -> list[list[NoteEvent]]:
    chords: list[list[NoteEvent]] = []
    for ev in events:
        if chords and ev.start - chords[-1][0].start <= CHORD_WINDOW:
            chords[-1].append(ev)
        else:
            chords.append([ev])
    # Keep the loudest notes if a "chord" has more notes than strings.
    for i, chord in enumerate(chords):
        if len(chord) > MAX_CHORD_NOTES:
            chord.sort(key=lambda n: -n.amplitude)
            chords[i] = sorted(chord[:MAX_CHORD_NOTES], key=lambda n: n.midi)
    return chords


def _positions(midi: int, tuning: list[int]) -> list[tuple[int, int]]:
    """All (string, fret) that produce `midi`."""
    out = []
    for s, open_midi in enumerate(tuning):
        fret = midi - open_midi
        if 0 <= fret <= MAX_FRET:
            out.append((s, fret))
    return out


def _chord_assignments(chord: list[NoteEvent], tuning: list[int]) -> list[list[tuple[int, int]]]:
    """Joint (string, fret) assignments for a chord; strings must be distinct."""
    per_note = []
    for ev in chord:
        midi = _fit_to_range(ev.midi, tuning)
        per_note.append(_positions(midi, tuning))

    assignments = []
    for combo in product(*per_note):
        strings = [s for s, _ in combo]
        if len(set(strings)) != len(strings):
            continue
        fretted = [f for _, f in combo if f > 0]
        if fretted and max(fretted) - min(fretted) > 4:  # unreachable span
            continue
        assignments.append(list(combo))
    if not assignments:  # fall back: drop notes until something is playable
        return _chord_assignments(chord[:-1], tuning) if len(chord) > 1 else []
    return assignments


def _hand_pos(assignment: list[tuple[int, int]]) -> float:
    fretted = [f for _, f in assignment if f > 0]
    return sum(fretted) / len(fretted) if fretted else 0.0


def _cost(
    assignment: list[tuple[int, int]],
    prev_pos: float | None,
    weights: tuple[float, float, float, float],
) -> float:
    w_span, w_high, w_move, w_pos = weights
    fretted = [f for _, f in assignment if f > 0]
    span = (max(fretted) - min(fretted)) if len(fretted) > 1 else 0
    high = sum(max(0, f - 12) for _, f in assignment)
    move = abs(_hand_pos(assignment) - prev_pos) if prev_pos is not None and fretted else 0.0
    position = _hand_pos(assignment)  # open strings cost nothing
    return span * w_span + high * w_high + move * w_move + position * w_pos


def _viterbi(
    chords: list[list[NoteEvent]],
    tuning: list[int],
    weights: tuple[float, float, float, float],
) -> list[TabNote]:
    # beam entries: (total_cost, hand_pos, path)  path = list of assignments
    beam: list[tuple[float, float | None, list]] = [(0.0, None, [])]
    solved_chords: list[list[NoteEvent]] = []
    for chord in chords:
        options = _chord_assignments(chord, tuning)
        if not options:
            continue
        solved_chords.append(chord)
        candidates = []
        for total, pos, path in beam:
            for assignment in options:
                c = total + _cost(assignment, pos, weights)
                new_pos = _hand_pos(assignment) or pos
                candidates.append((c, new_pos, path + [assignment]))
        candidates.sort(key=lambda x: x[0])
        beam = candidates[:BEAM_WIDTH]

    if not beam:
        return []
    _, _, best_path = beam[0]
    notes = []
    for chord, assignment in zip(solved_chords, best_path):
        for ev, (string, fret) in zip(chord, assignment):
            notes.append(TabNote(ev.start, ev.end, tuning[string] + fret, string, fret))
    notes.sort(key=lambda n: (n.start, n.string))
    return notes
