import { useCallback, useEffect, useRef, useState } from 'react'
import type { AlphaTabApi } from '@coderline/alphatab'
import { stemsToAlphaTex, type StemJson } from './alphatex'
import { fileUrl, getStem, type JobMeta } from './api'

// alphaTab is loaded as a classic script in index.html (its Vite plugin is
// incompatible with rolldown); the npm package supplies types only.
declare global {
  interface Window {
    alphaTab: typeof import('@coderline/alphatab')
  }
}

const SPEEDS = [0.5, 0.65, 0.8, 1]
const TICKS_PER_SIXTEENTH = 240 // alphaTab uses 960 ticks per quarter note

interface TrackState {
  mute: boolean
  solo: boolean
}

export default function Player({ job }: { job: JobMeta }) {
  const [stems, setStems] = useState<StemJson[] | null>(null)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [trackState, setTrackState] = useState<Record<string, TrackState>>({})
  const [playing, setPlaying] = useState(false)
  const [speed, setSpeed] = useState(1)
  const [audioMode, setAudioMode] = useState<'synth' | 'original'>('synth')
  const [error, setError] = useState<string | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const audioRef = useRef<HTMLAudioElement>(null)
  const apiRef = useRef<AlphaTabApi | null>(null)
  const rafRef = useRef(0)

  useEffect(() => {
    let cancelled = false
    const names = job.summary?.stems ?? []
    Promise.all(names.map(s => getStem(job.id, s).catch(() => null))).then(results => {
      if (cancelled) return
      const loaded = results.filter((s): s is StemJson => s !== null)
      setStems(loaded)
      setSelected(new Set(loaded.slice(0, 1).map(s => s.stem)))
      if (loaded.length === 0) setError('No stem data found for this job.')
    })
    return () => {
      cancelled = true
    }
  }, [job.id, job.summary?.stems])

  useEffect(() => {
    if (!containerRef.current || !stems || stems.length === 0) return
    const api = new window.alphaTab.AlphaTabApi(containerRef.current, {
      core: { fontDirectory: '/alphatab/font/' },
      player: {
        playerMode: window.alphaTab.PlayerMode.EnabledSynthesizer,
        soundFont: '/alphatab/soundfont/sonivox.sf2',
        scrollElement: 'html',
      },
      display: { scale: 0.9 },
    })
    api.playerStateChanged.on(e => setPlaying(e.state === 1))
    apiRef.current = api
    return () => {
      cancelAnimationFrame(rafRef.current)
      api.destroy()
      apiRef.current = null
    }
  }, [stems])

  const chosen = (stems ?? []).filter(s => selected.has(s.stem))

  // Re-render the score whenever stem selection changes.
  useEffect(() => {
    const api = apiRef.current
    if (!api || chosen.length === 0) return
    try {
      api.tex(stemsToAlphaTex(chosen, job.title), chosen.map((_, i) => i))
      setError(null)
    } catch (e) {
      setError(`Failed to build tab: ${String(e)}`)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stems, selected, job.title])

  // Apply mute/solo to the rendered tracks.
  useEffect(() => {
    const api = apiRef.current
    if (!api?.score) return
    chosen.forEach((stem, i) => {
      const track = api.score!.tracks[i]
      if (!track) return
      const state = trackState[stem.stem]
      api.changeTrackMute([track], state?.mute ?? false)
      api.changeTrackSolo([track], state?.solo ?? false)
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [trackState, stems, selected])

  // Original-audio mode: drive the tab cursor from the <audio> element using
  // the beat grid (tempo + first-beat offset stored in the stem JSON).
  const syncCursor = useCallback(() => {
    const api = apiRef.current
    const audio = audioRef.current
    const ref = stems?.[0]
    if (!api || !audio || !ref?.tempo) return
    const sixteenths = ((audio.currentTime - (ref.beat0 ?? 0)) * ref.tempo * 4) / 60
    api.tickPosition = Math.max(0, Math.round(sixteenths * TICKS_PER_SIXTEENTH))
    if (!audio.paused) rafRef.current = requestAnimationFrame(syncCursor)
  }, [stems])

  const playPause = () => {
    const api = apiRef.current
    const audio = audioRef.current
    if (audioMode === 'original' && audio) {
      api?.stop()
      if (audio.paused) {
        audio.playbackRate = speed
        void audio.play()
        rafRef.current = requestAnimationFrame(syncCursor)
      } else {
        audio.pause()
      }
    } else {
      api?.playPause()
    }
  }

  const stop = () => {
    apiRef.current?.stop()
    const audio = audioRef.current
    if (audio) {
      audio.pause()
      audio.currentTime = 0
    }
    cancelAnimationFrame(rafRef.current)
  }

  const changeSpeed = (value: number) => {
    setSpeed(value)
    if (apiRef.current) apiRef.current.playbackSpeed = value
    if (audioRef.current) audioRef.current.playbackRate = value
  }

  const switchMode = (mode: 'synth' | 'original') => {
    stop()
    setAudioMode(mode)
  }

  const toggleStem = (stem: string) => {
    setSelected(prev => {
      const next = new Set(prev)
      if (next.has(stem)) next.delete(stem)
      else next.add(stem)
      return next.size > 0 ? next : prev
    })
  }

  const toggleTrack = (stem: string, key: keyof TrackState) => {
    setTrackState(prev => {
      const current = prev[stem] ?? { mute: false, solo: false }
      return { ...prev, [stem]: { ...current, [key]: !current[key] } }
    })
  }

  if (stems === null) return <p className="text-slate-400">Loading stems…</p>

  return (
    <div>
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-3 mb-4">
          {error}
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2 mb-3">
        {stems.map(s => {
          const isOn = selected.has(s.stem)
          const state = trackState[s.stem]
          return (
            <span key={s.stem} className="inline-flex rounded-lg border border-slate-200 overflow-hidden">
              <button
                onClick={() => toggleStem(s.stem)}
                className={`px-3 py-1.5 text-sm font-medium transition-colors ${
                  isOn ? 'bg-indigo-600 text-white' : 'bg-white text-slate-600 hover:bg-slate-50'
                }`}
              >
                {s.stem}
              </button>
              {isOn && (
                <>
                  <button
                    onClick={() => toggleTrack(s.stem, 'mute')}
                    title="Mute (synth playback)"
                    className={`px-2 text-xs border-l border-slate-200 ${
                      state?.mute ? 'bg-amber-100 text-amber-700' : 'bg-white text-slate-400 hover:bg-slate-50'
                    }`}
                  >
                    M
                  </button>
                  <button
                    onClick={() => toggleTrack(s.stem, 'solo')}
                    title="Solo (synth playback)"
                    className={`px-2 text-xs border-l border-slate-200 ${
                      state?.solo ? 'bg-emerald-100 text-emerald-700' : 'bg-white text-slate-400 hover:bg-slate-50'
                    }`}
                  >
                    S
                  </button>
                </>
              )}
            </span>
          )
        })}
      </div>

      <div className="flex flex-wrap items-center gap-2 mb-4">
        <button
          onClick={playPause}
          className="bg-indigo-600 text-white text-sm font-medium px-4 py-1.5 rounded-lg hover:bg-indigo-700 transition-colors"
        >
          {playing || (audioMode === 'original' && !audioRef.current?.paused) ? '⏸ Pause' : '▶ Play'}
        </button>
        <button
          onClick={stop}
          className="bg-white border border-slate-200 text-slate-600 text-sm font-medium px-3 py-1.5 rounded-lg hover:border-indigo-300 transition-colors"
        >
          ⏹ Stop
        </button>

        <select
          value={speed}
          onChange={e => changeSpeed(Number(e.target.value))}
          className="text-sm border border-slate-200 rounded-lg px-2 py-1.5 text-slate-600 bg-white"
        >
          {SPEEDS.map(s => (
            <option key={s} value={s}>
              {s === 1 ? 'Full speed' : `${Math.round(s * 100)}% speed`}
            </option>
          ))}
        </select>

        <span className="inline-flex rounded-lg border border-slate-200 overflow-hidden text-sm">
          {(['synth', 'original'] as const).map(mode => (
            <button
              key={mode}
              onClick={() => switchMode(mode)}
              className={`px-3 py-1.5 font-medium transition-colors ${
                audioMode === mode ? 'bg-slate-700 text-white' : 'bg-white text-slate-600 hover:bg-slate-50'
              }`}
            >
              {mode === 'synth' ? '🎹 Synth' : '🎧 Original audio'}
            </button>
          ))}
        </span>

        <a
          href={fileUrl(job.id, 'song.mid')}
          download
          className="ml-auto text-sm text-indigo-600 hover:text-indigo-800 underline"
        >
          Download MIDI
        </a>
      </div>

      {audioMode === 'original' && (
        <p className="text-xs text-slate-400 mb-3">
          Playing the original recording; the cursor follows the beat grid. Mute/solo only
          affect synth mode.
        </p>
      )}

      <audio ref={audioRef} src={fileUrl(job.id, 'source.mp3')} preload="auto" />

      <div className="bg-white rounded-xl border border-slate-200 p-4 overflow-x-auto">
        <div ref={containerRef} />
      </div>
    </div>
  )
}
