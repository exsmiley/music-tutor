"""Detect string bends and slides from basic-pitch output.

basic-pitch reports per-note pitch-bend arrays (units: 1/3-semitone bins) but
splits larger gestures into separate notes: a 2-semitone bend becomes a note
with a rising bend tail plus a second note above it; a slide becomes a run of
short stepping-stone notes ending in a held note. This module reads the bend
data and stitches those splits back into single annotated events.

Harmonics (natural/pinch) are NOT handled — they're indistinguishable from
ordinary notes by pitch alone. See README limitations.
"""

from .to_notes import NoteEvent

BEND_GAP = 0.12        # split-bend halves are near-continuous audio
BEND_MIN = 0.6         # in-note rise below this is vibrato/jitter, not a bend
BEND_TAIL_MIN = 0.4    # a split bend is still rising at the first note's end
BEND_NOTE_MIN_DUR = 0.15  # attack transients on short notes fake a rise
BEND_TARGET_MIN_DUR = 0.1  # the bent-to note is held, not a passing tone
BEND_MAX_STEP = 2      # bends reach at most a whole step to the next note
SLIDE_GAP = 0.45       # detection drops notes mid-glide, so gaps run long
SLIDE_STEP_MAX = 5     # per-note pitch step within a slide run
SLIDE_NOTE_MAX = 0.25  # stepping-stone notes in a slide are short
SLIDE_MIN_SPAN = 3     # total semitones a slide must cover


def annotate(events: list[NoteEvent], allow_bends: bool = True) -> list[NoteEvent]:
    """Merge slide runs and split bends; sets .bend and .slide on events.

    Slides first: their stepping-stone notes carry glide-induced bend data
    that would otherwise be misread as string bends. allow_bends=False (bass)
    keeps slide detection but strips all bend annotations.
    """
    events = _merge_slides(events)
    if allow_bends:
        events = _merge_split_bends(events)
    for e in events:
        if (
            not allow_bends
            or e.slide  # the glide belongs to the slide, not a bend
            or e.bend < BEND_MIN
            or e.end - e.start < BEND_NOTE_MIN_DUR
        ):
            e.bend = 0.0
        else:
            # Round to guitar-notation values (half/full step).
            e.bend = min(2.0, round(e.bend * 2) / 2)
    return events


def _isolated(events: list[NoteEvent], i: int, window: float = 0.05) -> bool:
    """True if events[i] has no co-onset partner (i.e. is not part of a chord)."""
    e = events[i]
    for j in (i - 1, i + 1):
        if 0 <= j < len(events) and abs(events[j].start - e.start) <= window:
            return False
    return True


def _merge_split_bends(events: list[NoteEvent]) -> list[NoteEvent]:
    out: list[NoteEvent] = []
    i = 0
    while i < len(events):
        a = events[i]
        b = events[i + 1] if i + 1 < len(events) else None
        if (
            b is not None
            and _isolated(events, i)
            and _isolated(events, i + 1)
            # The first note must still be rising when it ends — an ordinary
            # ascending melodic step has a flat tail even with pitch jitter.
            and a.bend_tail >= BEND_TAIL_MIN
            and a.end - a.start >= BEND_NOTE_MIN_DUR
            and b.end - b.start >= BEND_TARGET_MIN_DUR
            and 0 < b.midi - a.midi <= BEND_MAX_STEP
            and b.start - a.end < BEND_GAP
            and not a.slide
            and not b.slide
        ):
            a.end = b.end
            a.bend = float(b.midi - a.midi)
            out.append(a)
            i += 2
            continue
        out.append(a)
        i += 1
    return out


def _merge_slides(events: list[NoteEvent]) -> list[NoteEvent]:
    out: list[NoteEvent] = []
    i = 0
    while i < len(events):
        run = [i]
        j = i
        while j + 1 < len(events):
            cur, nxt = events[j], events[j + 1]
            step = nxt.midi - cur.midi
            first_step = events[run[0] + 1].midi - events[run[0]].midi if len(run) > 1 else step
            if (
                _isolated(events, j + 1)
                and 1 <= abs(step) <= SLIDE_STEP_MAX
                and step * first_step > 0  # monotonic
                and nxt.start - cur.end < SLIDE_GAP
                and (cur.end - cur.start) <= SLIDE_NOTE_MAX
            ):
                run.append(j + 1)
                j += 1
            else:
                break
        first, last = events[run[0]], events[run[-1]]
        if len(run) >= 3 and abs(last.midi - first.midi) >= SLIDE_MIN_SPAN:
            first.slide = True
            out.extend([first, last])  # drop the stepping stones between
        else:
            out.extend(events[k] for k in run)
        i = run[-1] + 1
    return out
