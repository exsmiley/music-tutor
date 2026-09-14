"""Source separation via Demucs htdemucs_6s (vocals/drums/bass/guitar/piano/other)."""

from pathlib import Path
import subprocess
import sys

import numpy as np
import soundfile as sf

MODEL = "htdemucs_6s"
STEMS = ["vocals", "drums", "bass", "guitar", "piano", "other"]

# A stem whose RMS is below this fraction of the loudest stem's RMS is
# considered absent from the mix.
PRESENCE_RATIO = 0.10


def separate(wav: Path, workdir: Path, device: str = "cpu") -> dict[str, Path]:
    """Run Demucs, return {stem_name: wav_path}."""
    out_dir = workdir / "stems"
    subprocess.run(
        [
            sys.executable, "-m", "demucs",
            "-n", MODEL,
            "-d", device,
            "-o", str(out_dir),
            str(wav),
        ],
        check=True,
    )
    stem_dir = out_dir / MODEL / wav.stem
    stems = {name: stem_dir / f"{name}.wav" for name in STEMS}
    missing = [n for n, p in stems.items() if not p.exists()]
    if missing:
        raise RuntimeError(f"Demucs did not produce stems: {missing}")
    return stems


def detect_present(stems: dict[str, Path]) -> dict[str, float]:
    """RMS energy per stem, normalized to the loudest stem (0..1)."""
    rms = {}
    for name, path in stems.items():
        data, _ = sf.read(path, always_2d=True)
        rms[name] = float(np.sqrt(np.mean(np.square(data))))
    loudest = max(rms.values()) or 1.0
    return {name: value / loudest for name, value in rms.items()}
