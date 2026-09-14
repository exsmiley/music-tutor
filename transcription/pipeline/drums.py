"""Light drum transcription: onset detection + band-energy classification.

Not a tab — produces kick/snare/hihat events for MIDI playback (channel 10).
Good enough to play along with; a real drum model can replace this later.
"""

from dataclasses import dataclass
from pathlib import Path

import numpy as np

# General MIDI percussion notes.
GM_DRUMS = {"kick": 36, "snare": 38, "hihat": 42}


@dataclass
class DrumEvent:
    time: float
    kind: str  # kick | snare | hihat


def stem_to_drums(wav: Path) -> list[DrumEvent]:
    import librosa

    y, sr = librosa.load(str(wav), sr=22050, mono=True)
    onset_frames = librosa.onset.onset_detect(y=y, sr=sr, backtrack=False, units="frames")
    if len(onset_frames) == 0:
        return []

    S = np.abs(librosa.stft(y))
    freqs = librosa.fft_frequencies(sr=sr)
    low = freqs < 150
    mid = (freqs >= 150) & (freqs < 4000)
    high = freqs >= 5000

    events = []
    for frame in onset_frames:
        col = S[:, min(frame, S.shape[1] - 1)]
        total = float(col.sum()) or 1.0
        e_low, e_mid, e_high = (float(col[m].sum()) / total for m in (low, mid, high))
        if e_low > 0.4:
            kind = "kick"
        elif e_high > 0.35:
            kind = "hihat"
        else:
            kind = "snare"
        events.append(DrumEvent(time=float(librosa.frames_to_time(frame, sr=sr)), kind=kind))
    return events


def drums_to_json(events: list[DrumEvent]) -> dict:
    return {
        "stem": "drums",
        "events": [{"time": round(e.time, 3), "kind": e.kind} for e in events],
    }
