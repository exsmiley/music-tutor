"""Beat-track the mix and snap note times to a 16th-note grid.

The grid lets renderers (alphaTex, notation) express rhythm; raw seconds are
kept alongside so audio-synced playback stays exact.
"""

from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass
class BeatGrid:
    tempo: float            # BPM
    beat_times: np.ndarray  # seconds of each detected beat

    def to_sixteenths(self, t: float) -> float:
        """Continuous position of time `t` in 16ths from the first beat."""
        beats = self.beat_times
        if len(beats) < 2:
            return t * self.tempo / 60.0 * 4.0
        idx = np.interp(t, beats, np.arange(len(beats)))
        # np.interp clamps outside the range; extrapolate with the tempo.
        spb = 60.0 / self.tempo
        if t < beats[0]:
            idx = (t - beats[0]) / spb
        elif t > beats[-1]:
            idx = len(beats) - 1 + (t - beats[-1]) / spb
        return float(idx * 4.0)


def track_beats(wav: Path) -> BeatGrid:
    import librosa

    y, sr = librosa.load(str(wav), sr=22050, mono=True)
    tempo, beat_times = librosa.beat.beat_track(y=y, sr=sr, units="time")
    tempo = float(np.atleast_1d(tempo)[0])
    if tempo <= 0:
        tempo = 120.0
    return BeatGrid(tempo=tempo, beat_times=np.asarray(beat_times))


def annotate(note: dict, grid: BeatGrid) -> dict:
    """Add q16 (onset) and d16 (duration) grid fields to a serialized note."""
    q_on = round(grid.to_sixteenths(note["start"]))
    q_off = round(grid.to_sixteenths(note["end"]))
    note["q16"] = max(0, q_on)
    note["d16"] = max(1, q_off - q_on)
    return note
