// Convert transcription stem JSON (from transcription/transcribe.py) into
// alphaTex for AlphaTab rendering + playback.
//
// Notes carry a 16th-note grid position (q16) and duration (d16) produced by
// beat tracking. Rhythm here is quantized; raw seconds remain in the JSON if
// exact audio sync is ever needed.

export interface StemNote {
  start: number
  end: number
  midi: number
  string: number // 0 = lowest-pitched string
  fret: number
  q16?: number
  d16?: number
  bend?: number // semitones of upward bend
  slide?: boolean // slides into the next note
}

export interface StemJson {
  stem: string
  tempo?: number
  beat0?: number // seconds of the first detected beat in the original audio
  notes: StemNote[]
}

const GUITAR_TUNING_TEX = 'e4 b3 g3 d3 a2 e2'
const BASS_TUNING_TEX = 'g2 d2 a1 e1'
const SIXTEENTHS_PER_BAR = 16

const STEM_LABELS: Record<string, string> = {
  guitar: 'Guitar',
  'guitar-L': 'Guitar (left)',
  'guitar-R': 'Guitar (right)',
  'guitar-lead': 'Guitar (lead)',
  'guitar-rhythm': 'Guitar (rhythm)',
  bass: 'Bass',
  vocals: 'Vocals (as guitar)',
  other: 'Other (as guitar)',
  piano: 'Piano (as guitar)',
  mix: 'Full mix (as guitar)',
}

// General MIDI programs, 0-indexed.
const STEM_PROGRAMS: Record<string, number> = { bass: 33 }
const DEFAULT_PROGRAM = 25

export function stemsToAlphaTex(stems: StemJson[], title: string): string {
  const tempo = Math.round(stems.find(s => s.tempo)?.tempo ?? 120)
  const header = `\\title "${title}"\n\\tempo ${tempo}\n.\n`
  return header + stems.map(trackToTex).join('\n')
}

function trackToTex(stem: StemJson): string {
  const isBass = stem.stem === 'bass'
  const nStrings = isBass ? 4 : 6
  // \tuning must not be the last metadata line: a following "(" chord would be
  // parsed as further tuning values and crash the alphaTex parser.
  const lines = [
    `\\track "${STEM_LABELS[stem.stem] ?? stem.stem}"`,
    `\\tuning ${isBass ? BASS_TUNING_TEX : GUITAR_TUNING_TEX}`,
    `\\instrument ${STEM_PROGRAMS[stem.stem] ?? DEFAULT_PROGRAM}`,
  ]

  // Group notes by grid onset; one string per note within a group.
  const groups = new Map<number, StemNote[]>()
  for (const n of stem.notes) {
    const q = n.q16 ?? 0
    const group = groups.get(q) ?? []
    if (!group.some(g => g.string === n.string)) group.push(n)
    groups.set(q, group)
  }
  // Quantization can merge notes the solver placed ~150ms apart into one
  // column; keep each column fretting-hand-reachable (≤5-fret span, open
  // strings exempt) by dropping the outliers furthest from the median.
  for (const [q, group] of groups) {
    const fretted = () => group.filter(n => n.fret > 0).map(n => n.fret)
    while (fretted().length > 1 && Math.max(...fretted()) - Math.min(...fretted()) > 5) {
      const frets = fretted().sort((a, b) => a - b)
      const median = frets[Math.floor(frets.length / 2)]
      let worst = 0
      for (let i = 1; i < group.length; i++) {
        const dist = (n: StemNote) => (n.fret > 0 ? Math.abs(n.fret - median) : 0)
        if (dist(group[i]) > dist(group[worst])) worst = i
      }
      group.splice(worst, 1)
    }
    groups.set(q, group)
  }
  const onsets = [...groups.keys()].sort((a, b) => a - b)

  const tokens: string[] = []
  let cursor = 0
  const advance = (
    sixteenths: number,
    token: (denominator: number) => string,
    // Continuation fills chunks after the first: rests for gaps, ties ('-')
    // for held notes. Defaults to rests.
    continuation: (denominator: number) => string = d => `r.${d}`,
  ) => {
    // Emit in power-of-2 chunks that never cross a bar line.
    let remaining = sixteenths
    let first = true
    while (remaining > 0) {
      const toBar = SIXTEENTHS_PER_BAR - (cursor % (SIXTEENTHS_PER_BAR))
      let chunk = Math.min(remaining, toBar)
      chunk = 2 ** Math.floor(Math.log2(chunk))
      const denominator = SIXTEENTHS_PER_BAR / chunk
      tokens.push(first ? token(denominator) : continuation(denominator))
      first = false
      cursor += chunk
      remaining -= chunk
      if (cursor % SIXTEENTHS_PER_BAR === 0) tokens.push('|')
    }
  }

  for (let i = 0; i < onsets.length; i++) {
    const q = onsets[i]
    if (q > cursor) advance(q - cursor, d => `r.${d}`)
    const group = groups.get(q)!
    const next = i + 1 < onsets.length ? onsets[i + 1] : q + SIXTEENTHS_PER_BAR
    const held = Math.max(...group.map(n => n.d16 ?? 1))
    const dur = Math.max(1, Math.min(held, next - q, SIXTEENTHS_PER_BAR))
    // A shift slide is only valid tab if the next column continues on the
    // same string; otherwise drop the marker and show plain notes.
    const nextGroup = i + 1 < onsets.length ? groups.get(onsets[i + 1])! : []
    const effects = (n: StemNote): string => {
      if (n.bend) return `{b (0 ${Math.round(n.bend * 2)})}` // 4 = whole step
      if (n.slide && nextGroup.some(m => m.string === n.string)) return '{ss}'
      return ''
    }

    // Tie held notes across chunk/bar boundaries. Ties must use the explicit
    // -.string.duration form: a bare -.N is parsed as "tie on string N".
    advance(
      dur,
      denominator => {
        const beats = group
          .map(n => `${n.fret}.${nStrings - n.string}${effects(n)}`)
          .join(' ')
        return group.length > 1 ? `(${beats}).${denominator}` : `${beats}.${denominator}`
      },
      denominator => {
        const ties = group.map(n => `-.${nStrings - n.string}`).join(' ')
        return group.length > 1 ? `(${ties}).${denominator}` : `${ties}.${denominator}`
      },
    )
  }

  // Strip a trailing bar line so the track doesn't end with an empty measure.
  if (tokens[tokens.length - 1] === '|') tokens.pop()
  lines.push(tokens.join(' '))
  return lines.join('\n')
}
