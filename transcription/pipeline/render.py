"""Render solved tab notes as ASCII tab and JSON."""

import json
from pathlib import Path

from .tab_solver import TabNote, CHORD_WINDOW

# General MIDI programs (0-indexed): steel guitar for anything tabbed as
# guitar, fingered electric bass for the bass stem.
MIDI_PROGRAMS = {"bass": 33}
DEFAULT_PROGRAM = 25


def to_midi(stem_notes: dict[str, list[TabNote]], path: Path, drums=None) -> None:
    """Write one MIDI file with an instrument track per stem (+ optional drums)."""
    import pretty_midi

    pm = pretty_midi.PrettyMIDI()
    if drums:
        from .drums import GM_DRUMS

        kit = pretty_midi.Instrument(program=0, is_drum=True, name="drums")
        for e in drums:
            kit.notes.append(
                pretty_midi.Note(
                    velocity=100, pitch=GM_DRUMS[e.kind], start=e.time, end=e.time + 0.1
                )
            )
        pm.instruments.append(kit)
    for stem, notes in stem_notes.items():
        inst = pretty_midi.Instrument(
            program=MIDI_PROGRAMS.get(stem, DEFAULT_PROGRAM), name=stem
        )
        for n in notes:
            inst.notes.append(
                pretty_midi.Note(
                    velocity=90,
                    pitch=n.midi,
                    start=n.start,
                    end=max(n.end, n.start + 0.05),
                )
            )
        pm.instruments.append(inst)
    pm.write(str(path))


STRING_LABELS = {
    6: ["e", "B", "G", "D", "A", "E"],  # high -> low for display
    4: ["G", "D", "A", "E"],
}
COLUMNS_PER_LINE = 36


def to_json(notes: list[TabNote], stem: str, path: Path, grid=None) -> None:
    serialized = []
    for n in notes:
        note = {
            "start": round(n.start, 3),
            "end": round(n.end, 3),
            "midi": n.midi,
            "string": n.string,
            "fret": n.fret,
            "amp": round(n.amplitude, 3),
        }
        if n.bend:
            note["bend"] = n.bend
        if n.slide:
            note["slide"] = True
        serialized.append(note)
    payload = {"stem": stem, "notes": serialized}
    if grid is not None:
        from .quantize import annotate

        payload["tempo"] = round(grid.tempo, 2)
        # Time of the first detected beat: lets the UI map audio seconds to
        # grid positions when syncing the cursor to the original recording.
        payload["beat0"] = round(float(grid.beat_times[0]), 3) if len(grid.beat_times) else 0.0
        payload["notes"] = [annotate(n, grid) for n in serialized]
    path.write_text(json.dumps(payload, indent=2))


def to_ascii(notes: list[TabNote], n_strings: int) -> str:
    if not notes:
        return "(no notes detected)\n"

    # One column per onset group (chords share a column).
    columns: list[list[TabNote]] = []
    for n in notes:
        if columns and n.start - columns[-1][0].start <= CHORD_WINDOW:
            columns[-1].append(n)
        else:
            columns.append([n])

    labels = STRING_LABELS[n_strings]
    lines = []
    for block_start in range(0, len(columns), COLUMNS_PER_LINE):
        block = columns[block_start:block_start + COLUMNS_PER_LINE]
        t = block[0][0].start
        rows = [f"{label}|" for label in labels]
        for col in block:
            width = max(len(str(n.fret)) for n in col)
            by_string = {n.string: n.fret for n in col}
            for display_row in range(n_strings):
                string = n_strings - 1 - display_row  # display top row = highest string
                fret = by_string.get(string)
                cell = str(fret).rjust(width, "-") if fret is not None else "-" * width
                rows[display_row] += cell + "--"
        lines.append(f"[{int(t) // 60}:{int(t) % 60:02d}]")
        lines.extend(row + "|" for row in rows)
        lines.append("")
    return "\n".join(lines)
