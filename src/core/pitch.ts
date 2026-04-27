import { NOTE_NAMES, type NoteName } from './notes'

// Autocorrelation-based pitch detection (YIN-inspired).
// Returns the dominant frequency in Hz, or null if no clear pitch found.
export function detectPitch(buffer: Float32Array, sampleRate: number): number | null {
  const bufLen = buffer.length
  const minFreq = 60   // Hz — below low E on guitar
  const maxFreq = 1400 // Hz — above high E, 24th fret

  const maxLag = Math.floor(sampleRate / minFreq)
  const minLag = Math.floor(sampleRate / maxFreq)

  // Compute autocorrelation
  const corr = new Float32Array(maxLag)
  for (let lag = minLag; lag < maxLag; lag++) {
    let sum = 0
    for (let i = 0; i < bufLen - lag; i++) {
      sum += buffer[i] * buffer[i + lag]
    }
    corr[lag] = sum
  }

  // Find the first prominent peak after the initial drop
  let peakLag = -1
  let peakVal = -Infinity
  let dropped = false

  for (let lag = minLag + 1; lag < maxLag - 1; lag++) {
    if (!dropped && corr[lag] < corr[lag - 1]) dropped = true
    if (dropped && corr[lag] > corr[lag - 1] && corr[lag] > corr[lag + 1]) {
      if (corr[lag] > peakVal) {
        peakVal = corr[lag]
        peakLag = lag
      }
      break // take first prominent peak
    }
  }

  if (peakLag === -1) return null

  // Require a meaningful correlation strength relative to zero-lag
  const rms = corr[0] > 0 ? peakVal / corr[0] : 0
  if (rms < 0.2) return null

  // Parabolic interpolation for sub-sample accuracy
  const prev = corr[peakLag - 1]
  const curr = corr[peakLag]
  const next = corr[peakLag + 1]
  const refinedLag = peakLag + (next - prev) / (2 * (2 * curr - prev - next))

  return sampleRate / refinedLag
}

export interface PitchResult {
  frequency: number
  note: NoteName
  octave: number
  cents: number   // deviation from nearest semitone, -50 to +50
  midi: number
}

// Convert a frequency to its nearest note + cents deviation.
export function frequencyToNote(frequency: number): PitchResult {
  const midi = Math.round(69 + 12 * Math.log2(frequency / 440))
  const exactMidi = 69 + 12 * Math.log2(frequency / 440)
  const cents = Math.round((exactMidi - midi) * 100)
  const note = NOTE_NAMES[((midi % 12) + 12) % 12]
  const octave = Math.floor(midi / 12) - 1
  return { frequency, note, octave, cents, midi }
}
