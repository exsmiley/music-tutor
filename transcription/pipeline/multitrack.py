"""Split one guitar stem into multiple parts (two players, or rhythm/lead).

Demucs separates by instrument class, so two guitars share one stem. Two
strategies, tried in order:

1. Stereo split: rock mixes often pan guitar 1 left and guitar 2 right.
   Transcribe each channel separately; if the note streams differ enough,
   emit guitar-L / guitar-R parts. Near-identical channels (double-tracked
   or centered) merge back into one part.
2. Voice split: within a merged part, separate chord clusters (rhythm) from
   a melodic line (lead) by register continuity. Only applied when both
   resulting parts are substantial and live in different registers.
"""

from pathlib import Path
from typing import Callable

import numpy as np
import soundfile as sf

from .to_notes import NoteEvent, stem_to_notes, CO_ONSET

SIMILAR_ONSET = 0.05      # notes matching across channels: same pitch within 50ms
MERGE_SIMILARITY = 0.95   # >= this, the two channels are the same performance

VOICE_MIN_SHARE = 0.15    # each voice must hold at least this share of notes
VOICE_MIN_NOTES = 20
VOICE_REGISTER_GAP = 5.0  # semitones between voice centers required to split
EMA_ALPHA = 0.2


def note_similarity(
    a: list[NoteEvent], b: list[NoteEvent]
) -> tuple[float, list[NoteEvent]]:
    """F1-style overlap of two note streams; also returns b's unmatched notes."""
    if not a and not b:
        return 1.0, []
    unmatched = list(b)
    hits = 0
    for note in a:
        for i, other in enumerate(unmatched):
            if other.midi == note.midi and abs(other.start - note.start) <= SIMILAR_ONSET:
                unmatched.pop(i)
                hits += 1
                break
    return 2 * hits / (len(a) + len(b)), unmatched


def guitar_parts(
    wav: Path,
    workdir: Path,
    onset: float,
    frame: float,
    min_amp: float,
    progress: Callable[[str], None],
) -> list[tuple[str, list[NoteEvent]]]:
    """Return [(part_name, events)] for a guitar stem."""
    data, sr = sf.read(wav, always_2d=True)

    if data.shape[1] >= 2 and not np.allclose(data[:, 0], data[:, 1], atol=1e-4):
        progress("transcribing guitar (left/right channels)")
        sides = {}
        for name, channel in (("L", data[:, 0]), ("R", data[:, 1])):
            side_wav = workdir / f"guitar_{name}.wav"
            sf.write(side_wav, channel, sr)
            sides[name] = stem_to_notes(
                side_wav, onset_threshold=onset, frame_threshold=frame, min_amplitude=min_amp
            )
        similarity, r_extras = note_similarity(sides["L"], sides["R"])
        progress(f"guitar channel similarity: {similarity:.2f}")
        if similarity < MERGE_SIMILARITY:
            return [("guitar-L", sides["L"]), ("guitar-R", sides["R"])]
        # Same performance on both sides: one part, keeping R-only stragglers.
        merged = sorted(sides["L"] + r_extras, key=lambda n: (n.start, n.midi))
    else:
        merged = stem_to_notes(
            wav, onset_threshold=onset, frame_threshold=frame, min_amplitude=min_amp
        )

    return split_voices(merged)


def split_voices(events: list[NoteEvent]) -> list[tuple[str, list[NoteEvent]]]:
    """Split one guitar part into rhythm (chords) and lead (melody) voices."""
    if len(events) < 2 * VOICE_MIN_NOTES:
        return [("guitar", events)]

    # Cluster co-onset notes.
    clusters: list[list[NoteEvent]] = []
    for e in events:
        if clusters and e.start - clusters[-1][0].start <= CO_ONSET:
            clusters[-1].append(e)
        else:
            clusters.append([e])

    pitches = sorted(e.midi for e in events)
    lead_center = float(pitches[int(len(pitches) * 0.75)])
    rhythm_center = float(pitches[int(len(pitches) * 0.25)])

    lead: list[NoteEvent] = []
    rhythm: list[NoteEvent] = []
    for cluster in clusters:
        mean_pitch = sum(n.midi for n in cluster) / len(cluster)
        if len(cluster) >= 3:  # a chord is rhythm playing
            rhythm.extend(cluster)
            rhythm_center += EMA_ALPHA * (mean_pitch - rhythm_center)
        elif abs(mean_pitch - lead_center) < abs(mean_pitch - rhythm_center):
            lead.extend(cluster)
            lead_center += EMA_ALPHA * (mean_pitch - lead_center)
        else:
            rhythm.extend(cluster)
            rhythm_center += EMA_ALPHA * (mean_pitch - rhythm_center)

    share = min(len(lead), len(rhythm)) / len(events)
    registers_apart = (
        abs(np.mean([n.midi for n in lead]) - np.mean([n.midi for n in rhythm]))
        >= VOICE_REGISTER_GAP
        if lead and rhythm
        else False
    )
    if share < VOICE_MIN_SHARE or min(len(lead), len(rhythm)) < VOICE_MIN_NOTES or not registers_apart:
        return [("guitar", events)]
    return [("guitar-lead", lead), ("guitar-rhythm", rhythm)]
