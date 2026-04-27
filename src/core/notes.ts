export const NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'] as const
export type NoteName = typeof NOTE_NAMES[number]
export type Difficulty = 'beginner' | 'intermediate' | 'advanced'

const NATURAL_INDICES = [0, 2, 4, 5, 7, 9, 11] // C D E F G A B

export function midiToNoteName(midi: number): NoteName {
  return NOTE_NAMES[((midi % 12) + 12) % 12]
}

export function getNotePool(difficulty: Difficulty): number[] {
  switch (difficulty) {
    case 'beginner':
      return NATURAL_INDICES.map(i => 60 + i)
    case 'intermediate':
      return Array.from({ length: 12 }, (_, i) => 60 + i)
    case 'advanced':
      return Array.from({ length: 36 }, (_, i) => 48 + i) // C3–B5
  }
}

export function getAnswerChoices(difficulty: Difficulty): NoteName[] {
  if (difficulty === 'beginner') return NATURAL_INDICES.map(i => NOTE_NAMES[i])
  return [...NOTE_NAMES]
}

export function noteNameToMidi(name: NoteName, octave = 4): number {
  return NOTE_NAMES.indexOf(name) + (octave + 1) * 12
}

const ENHARMONIC: Partial<Record<NoteName, string>> = {
  'C#': 'C#/D♭',
  'D#': 'D#/E♭',
  'F#': 'F#/G♭',
  'G#': 'G#/A♭',
  'A#': 'A#/B♭',
}

export function noteDisplayName(name: NoteName): string {
  return ENHARMONIC[name] ?? name
}

export function randomFrom<T>(arr: T[]): T {
  return arr[Math.floor(Math.random() * arr.length)]
}
