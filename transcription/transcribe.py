"""Offline tab transcription pipeline (CLI).

Usage:
  python transcribe.py <youtube-url-or-audio-file> [options]

Examples:
  python transcribe.py song.mp3 --out out/song
  python transcribe.py https://youtube.com/watch?v=... --instruments guitar,bass,vocals
  python transcribe.py song.mp3 --no-separate        # transcribe the mix directly

Every stem becomes a guitar tab except bass (bass tab) and drums (kick/snare/
hihat events for MIDI playback only). See pipeline/run.py for the stages.
"""

import argparse
from pathlib import Path

from pipeline.run import run_pipeline, TRANSCRIBABLE


def main() -> None:
    ap = argparse.ArgumentParser(description="Audio -> per-instrument tabs")
    ap.add_argument("source", help="YouTube URL or path to an audio file")
    ap.add_argument("--out", default="out", help="output directory")
    ap.add_argument(
        "--instruments",
        help=f"comma-separated subset of {TRANSCRIBABLE} (default: autodetect)",
    )
    ap.add_argument("--device", default="cpu", help="demucs device: cpu or mps")
    ap.add_argument(
        "--no-separate",
        action="store_true",
        help="skip Demucs and transcribe the full mix as one guitar tab",
    )
    args = ap.parse_args()

    instruments = [s.strip() for s in args.instruments.split(",")] if args.instruments else None
    summary = run_pipeline(
        args.source,
        Path(args.out),
        instruments=instruments,
        device=args.device,
        no_separate=args.no_separate,
        progress=lambda msg: print(f"* {msg}"),
    )
    print(f"\ndone: {Path(args.out).resolve()}")
    print(f"  tempo: {summary['tempo']} BPM")
    print(f"  stems: {', '.join(summary['stems'])}" + ("  + drums" if summary["drums"] else ""))


if __name__ == "__main__":
    main()
