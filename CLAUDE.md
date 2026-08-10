# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

`music-tutor` is a browser-based ear training app built with React + TypeScript + Vite. It has multiple "modules" (pitch identification, intervals, chord quality, etc.) that help guitarists develop musical intuition.

## Commands

```bash
npm run dev       # start dev server at localhost:5173
npm run build     # type-check + production build
npm run lint      # ESLint
npx tsc --noEmit  # type-check only
```

## Architecture

```
src/
  core/
    notes.ts      # music theory primitives: note names, MIDI↔frequency, note pools per difficulty
    audio.ts      # Web Audio API engine — playNote(midi) using OscillatorNode singleton AudioContext
  components/
    Layout.tsx    # top nav + page wrapper shared by all routes
  pages/
    Home.tsx      # module cards grid (active + coming soon)
  modules/
    PitchIdentification/index.tsx   # hear a note, pick from multiple choice
    TabPlayer/                      # AI-transcribed tabs: library, job submission, alphaTab player
transcription/                      # Python pipeline + FastAPI job service (see its README)
```

**Routing**: React Router v6, routes defined in `App.tsx`. Add new modules as routes under `/modules/<name>/`.

**Audio**: All audio goes through `src/core/audio.ts`. The `AudioContext` is a lazy singleton — resumed on first user gesture to comply with browser autoplay policy.

**Music theory core**: `src/core/notes.ts` is the single source of truth for note names, MIDI numbers, and difficulty-based note pools. All modules should import from here rather than define their own constants.

**Styling**: Tailwind CSS v4 via `@tailwindcss/vite`. No config file needed — just use utility classes. The `@import "tailwindcss"` directive is in `src/index.css`.
