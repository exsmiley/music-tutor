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

export const STEM_LABELS: Record<string, string> = {
  guitar: 'Guitar',
  'guitar-L': 'Guitar (left)',
  'guitar-R': 'Guitar (right)',
  'guitar-lead': 'Lead Guitar',
  'guitar-rhythm': 'Rhythm Guitar',
  'guitar-1': 'Guitar 1',
  'guitar-2': 'Guitar 2',
  bass: 'Bass',
  vocals: 'Vocals',
  other: 'Other',
  piano: 'Piano',
  mix: 'Full mix',
}

// Short names render in the score's left margin on every system.
const STEM_SHORT: Record<string, string> = {
  guitar: 'Gtr',
  'guitar-L': 'Gtr L',
  'guitar-R': 'Gtr R',
  'guitar-lead': 'Lead',
  'guitar-rhythm': 'Rhy',
  'guitar-1': 'Gtr 1',
  'guitar-2': 'Gtr 2',
  bass: 'Bass',
  vocals: 'Voc',
  other: 'Other',
  piano: 'Pno',
  mix: 'Mix',
}

export const stemLabel = (stem: string): string => STEM_LABELS[stem] ?? stem

// Instrument family for a stem name, used for icons/colors/tuning. Guitar
// variants (guitar-1, guitar-lead, guitar-L, …) all share the guitar family.
export type Family = 'guitar' | 'bass' | 'vocals' | 'piano' | 'other' | 'mix'
export const stemFamily = (stem: string): Family => {
  if (stem.startsWith('guitar')) return 'guitar'
  if (stem.startsWith('bass')) return 'bass'
  if (stem.startsWith('vocals')) return 'vocals'
  if (stem.startsWith('piano')) return 'piano'
  if (stem.startsWith('mix')) return 'mix'
  return 'other'
}

// Per-family display metadata. `dot` and `chip` are Tailwind classes so each
// instrument is identifiable at a glance by colour, not just by reading text.
export interface FamilyStyle {
  icon: string
  dot: string // solid colour swatch
  chip: string // tinted background + text for the viewed-track header
}
export const FAMILY_STYLE: Record<Family, FamilyStyle> = {
  guitar: { icon: '🎸', dot: 'bg-amber-500', chip: 'bg-amber-50 text-amber-800 border-amber-200' },
  bass: { icon: '🎵', dot: 'bg-violet-500', chip: 'bg-violet-50 text-violet-800 border-violet-200' },
  vocals: { icon: '🎤', dot: 'bg-rose-500', chip: 'bg-rose-50 text-rose-800 border-rose-200' },
  piano: { icon: '🎹', dot: 'bg-sky-500', chip: 'bg-sky-50 text-sky-800 border-sky-200' },
  other: { icon: '🎶', dot: 'bg-slate-400', chip: 'bg-slate-100 text-slate-700 border-slate-200' },
  mix: { icon: '🎚️', dot: 'bg-emerald-500', chip: 'bg-emerald-50 text-emerald-800 border-emerald-200' },
}
export const stemStyle = (stem: string): FamilyStyle => FAMILY_STYLE[stemFamily(stem)]

// Human-readable tuning for the viewed-track header.
export const stemTuning = (stem: string): string =>
  stemFamily(stem) === 'bass' ? 'Standard bass · E A D G' : 'Standard · E A D G B E'

// Vocals are pitch-detected and laid out as a guitar tab; there is no
// "correct" fingering, so the player says so when a vocal part is viewed.
export const stemHint = (stem: string): string | null =>
  stemFamily(stem) === 'vocals'
    ? 'Sung melody shown as a guitar tab — the pitches are real, the fingering is only one way to play them.'
    : null

// General MIDI programs, 0-indexed. Distinct voices per family so parts can be
// told apart by ear in synth mode (previously everything but bass shared one).
const STEM_PROGRAMS: Record<string, number> = { bass: 33 }
const FAMILY_PROGRAM: Record<Family, number> = {
  guitar: 27, // clean electric guitar
  bass: 33, // finger electric bass
  vocals: 54, // "Voice Oohs" — clearly not a guitar
  piano: 0, // acoustic grand
  other: 25, // steel guitar
  mix: 25,
}
const program = (stem: string): number => STEM_PROGRAMS[stem] ?? FAMILY_PROGRAM[stemFamily(stem)]

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
    `\\track "${stemLabel(stem.stem)}" "${STEM_SHORT[stem.stem] ?? stem.stem}"`,
    ...(isBass ? ['\\clef f4'] : []),
    `\\tuning ${isBass ? BASS_TUNING_TEX : GUITAR_TUNING_TEX}`,
    `\\instrument ${program(stem.stem)}`,
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
