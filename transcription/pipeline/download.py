"""Fetch audio for the pipeline: YouTube URL via yt-dlp, or a local file."""

from pathlib import Path
import subprocess
import sys


def fetch_audio(source: str, workdir: Path) -> Path:
    """Return a path to a wav file for `source` (URL or local path)."""
    src = Path(source)
    if src.exists():
        return _to_wav(src, workdir)

    if not source.startswith(("http://", "https://")):
        raise FileNotFoundError(f"Not a URL and file does not exist: {source}")

    out_template = str(workdir / "input.%(ext)s")
    subprocess.run(
        [
            sys.executable, "-m", "yt_dlp",
            "--no-playlist",
            "-f", "bestaudio",
            "--extract-audio",
            "--audio-format", "wav",
            "-o", out_template,
            source,
        ],
        check=True,
    )
    wav = workdir / "input.wav"
    if not wav.exists():
        raise RuntimeError("yt-dlp finished but input.wav was not produced")
    return wav


def _to_wav(src: Path, workdir: Path) -> Path:
    if src.suffix.lower() == ".wav":
        return src
    out = workdir / (src.stem + ".wav")
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(src), "-ac", "2", str(out)],
        check=True,
        capture_output=True,
    )
    return out
