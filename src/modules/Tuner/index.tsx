import { useState, useEffect, useRef, useCallback } from 'react'
import { detectPitch, frequencyToNote, type PitchResult } from '../../core/pitch'
import { noteDisplayName } from '../../core/notes'

const BUFFER_SIZE = 2048

// Cents deviation thresholds for color feedback
function tuningColor(cents: number): string {
  const abs = Math.abs(cents)
  if (abs <= 5)  return 'text-emerald-500'
  if (abs <= 15) return 'text-yellow-500'
  return 'text-red-500'
}

function tuningLabel(cents: number): string {
  if (Math.abs(cents) <= 5) return 'In tune'
  return cents < 0 ? 'Flat' : 'Sharp'
}

export default function Tuner() {
  const [active, setActive] = useState(false)
  const [result, setResult] = useState<PitchResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  const ctxRef  = useRef<AudioContext | null>(null)
  const srcRef  = useRef<MediaStreamAudioSourceNode | null>(null)
  const animRef = useRef<number>(0)
  const streamRef = useRef<MediaStream | null>(null)
  const analyserRef = useRef<AnalyserNode | null>(null)

  const stop = useCallback(() => {
    cancelAnimationFrame(animRef.current)
    srcRef.current?.disconnect()
    ctxRef.current?.close()
    streamRef.current?.getTracks().forEach(t => t.stop())
    ctxRef.current = null
    srcRef.current = null
    analyserRef.current = null
    streamRef.current = null
    setActive(false)
    setResult(null)
  }, [])

  const start = useCallback(async () => {
    setError(null)
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false })
      streamRef.current = stream

      const ac = new AudioContext()
      ctxRef.current = ac

      const analyser = ac.createAnalyser()
      analyser.fftSize = BUFFER_SIZE
      analyserRef.current = analyser

      const src = ac.createMediaStreamSource(stream)
      srcRef.current = src
      src.connect(analyser)

      const buffer = new Float32Array(BUFFER_SIZE)

      const tick = () => {
        analyser.getFloatTimeDomainData(buffer)
        const freq = detectPitch(buffer, ac.sampleRate)
        setResult(freq !== null ? frequencyToNote(freq) : null)
        animRef.current = requestAnimationFrame(tick)
      }

      setActive(true)
      animRef.current = requestAnimationFrame(tick)
    } catch {
      setError('Microphone access denied. Please allow microphone permissions and try again.')
    }
  }, [])

  // Clean up on unmount
  useEffect(() => () => stop(), [stop])

  const cents = result?.cents ?? 0
  const needlePercent = Math.max(0, Math.min(100, 50 + cents))

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-900 mb-1">Tuner</h1>
        <p className="text-slate-500 text-sm">Play or sing a note — the tuner will identify it in real time.</p>
      </div>

      {error && (
        <div className="mb-6 rounded-lg px-4 py-3 text-sm bg-red-50 text-red-700 border border-red-200">
          {error}
        </div>
      )}

      {/* Start / Stop */}
      <button
        onClick={active ? stop : start}
        className={`flex items-center gap-2 font-medium px-6 py-3 rounded-xl transition-colors cursor-pointer mb-10 ${
          active
            ? 'bg-red-100 hover:bg-red-200 text-red-700'
            : 'bg-indigo-600 hover:bg-indigo-700 text-white'
        }`}
      >
        <span>{active ? '⏹' : '🎙'}</span>
        {active ? 'Stop' : 'Start Tuner'}
      </button>

      {active && (
        <div className="max-w-sm">
          {result ? (
            <>
              {/* Note display */}
              <div className="text-center mb-6">
                <div className="text-7xl font-bold text-slate-900 leading-none mb-1">
                  {noteDisplayName(result.note)}
                </div>
                <div className="text-lg text-slate-400">{result.octave}</div>
                <div className={`text-base font-semibold mt-2 ${tuningColor(cents)}`}>
                  {tuningLabel(cents)}
                  {Math.abs(cents) > 5 && (
                    <span className="font-normal text-sm ml-1">
                      ({cents > 0 ? '+' : ''}{cents}¢)
                    </span>
                  )}
                </div>
              </div>

              {/* Cents needle */}
              <div className="relative">
                {/* Track */}
                <div className="h-3 bg-slate-100 rounded-full overflow-hidden">
                  <div
                    className="h-full w-1.5 bg-slate-800 rounded-full absolute top-0 transition-all duration-75"
                    style={{ left: `calc(${needlePercent}% - 3px)` }}
                  />
                </div>
                {/* Center marker */}
                <div className="absolute top-0 left-1/2 -translate-x-px h-3 w-0.5 bg-emerald-400 pointer-events-none" />
                {/* Labels */}
                <div className="flex justify-between text-xs text-slate-400 mt-1.5">
                  <span>−50¢</span>
                  <span className="text-emerald-500">♩</span>
                  <span>+50¢</span>
                </div>
              </div>

              {/* Frequency */}
              <div className="text-center text-xs text-slate-400 mt-4">
                {result.frequency.toFixed(1)} Hz
              </div>
            </>
          ) : (
            <div className="text-center text-slate-400 py-12">
              <div className="text-4xl mb-3">🎙</div>
              <p className="text-sm">Listening for a note...</p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
