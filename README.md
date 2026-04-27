# Music Tutor

A browser-based ear training app to help guitarists develop musical intuition — pitch identification, intervals, chord quality, rhythm, and sight reading.

## Setup

```bash
npm install
npm run dev
```

Then open `http://localhost:5173`.

## Modules

| Module | Status |
|--------|--------|
| Pitch Identification | ✅ Available |
| Tuner | ✅ Available |
| Intervals | Coming soon |
| Chord Quality | Coming soon |
| Rhythm | Coming soon |
| Sight Reading | Coming soon |

## Stack

- React 18 + TypeScript + Vite
- Tailwind CSS v4
- React Router v6
- Web Audio API (synthesized tones via `OscillatorNode`; microphone pitch detection via `AnalyserNode` + autocorrelation)
