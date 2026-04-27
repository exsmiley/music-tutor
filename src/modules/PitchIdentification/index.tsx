import { useState, useCallback } from 'react'
import { playNote } from '../../core/audio'
import {
  type Difficulty,
  type NoteName,
  getAnswerChoices,
  getNotePool,
  midiToNoteName,
  noteDisplayName,
  noteNameToMidi,
  randomFrom,
} from '../../core/notes'

type Phase = 'start' | 'waiting' | 'answered'

const DIFFICULTIES: { value: Difficulty; label: string; description: string }[] = [
  { value: 'beginner', label: 'Level 1', description: 'The 7 natural notes: C, D, E, F, G, A, B' },
  { value: 'intermediate', label: 'Level 2', description: 'All 12 notes including sharps and flats (C, C#/D♭, D, D#/E♭, ...)' },
  { value: 'advanced', label: 'Level 3', description: 'All 12 notes including sharps and flats across a wider range of octaves' },
]

export default function PitchIdentification() {
  const [difficulty, setDifficulty] = useState<Difficulty>('beginner')
  const [phase, setPhase] = useState<Phase>('start')
  const [currentNote, setCurrentNote] = useState<number | null>(null)
  const [selected, setSelected] = useState<NoteName | null>(null)
  const [guess, setGuess] = useState<NoteName | null>(null)
  const [streak, setStreak] = useState(0)
  const [correct, setCorrect] = useState(0)
  const [total, setTotal] = useState(0)
  const [previewEnabled, setPreviewEnabled] = useState(true)

  const startRound = useCallback((d: Difficulty) => {
    const note = randomFrom(getNotePool(d))
    setCurrentNote(note)
    setSelected(null)
    setGuess(null)
    setPhase('waiting')
    playNote(note)
  }, [])

  const replay = useCallback(() => {
    if (currentNote !== null) playNote(currentNote)
  }, [currentNote])

  const handleSelect = useCallback((name: NoteName) => {
    if (previewEnabled) playNote(noteNameToMidi(name))
    if (phase !== 'waiting') return
    setSelected(name)
  }, [phase, previewEnabled])

  const handleSubmit = useCallback(() => {
    if (phase !== 'waiting' || selected === null || currentNote === null) return
    const answer = midiToNoteName(currentNote)
    const isCorrect = selected === answer
    setGuess(selected)
    setPhase('answered')
    setTotal(t => t + 1)
    if (isCorrect) {
      setCorrect(c => c + 1)
      setStreak(s => s + 1)
    } else {
      setStreak(0)
    }
  }, [phase, selected, currentNote])

  const changeDifficulty = useCallback((d: Difficulty) => {
    setDifficulty(d)
    setPhase('start')
    setCurrentNote(null)
    setSelected(null)
    setGuess(null)
    setStreak(0)
    setCorrect(0)
    setTotal(0)
  }, [])

  const choices = getAnswerChoices(difficulty)
  const correctAnswer = currentNote !== null ? midiToNoteName(currentNote) : null
  const accuracy = total > 0 ? Math.round((correct / total) * 100) : null

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-900 mb-1">Pitch Identification</h1>
        <p className="text-slate-500 text-sm">Listen to the note and identify it.</p>
      </div>

      {/* Difficulty tabs + preview toggle */}
      <div className="mb-8">
        <div className="flex flex-wrap items-center gap-4 mb-2">
          <div className="flex gap-1 bg-slate-100 p-1 rounded-lg">
            {DIFFICULTIES.map(d => (
              <button
                key={d.value}
                onClick={() => changeDifficulty(d.value)}
                className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors cursor-pointer ${
                  difficulty === d.value
                    ? 'bg-white text-slate-900 shadow-sm'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                {d.label}
              </button>
            ))}
          </div>
          <label className="flex items-center gap-2 text-sm text-slate-600 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={previewEnabled}
              onChange={e => setPreviewEnabled(e.target.checked)}
              className="w-4 h-4 accent-indigo-600 cursor-pointer"
            />
            Play note on click
          </label>
        </div>
        <p className="text-sm text-slate-500">
          {DIFFICULTIES.find(d => d.value === difficulty)?.description}
        </p>
      </div>

      {/* Score */}
      {total > 0 && (
        <div className="flex gap-3 mb-8">
          <div className="bg-white border border-slate-200 rounded-lg px-4 py-2 text-center min-w-16">
            <div className="text-2xl font-bold text-indigo-600">{streak}</div>
            <div className="text-xs text-slate-500 mt-0.5">Streak</div>
          </div>
          <div className="bg-white border border-slate-200 rounded-lg px-4 py-2 text-center min-w-16">
            <div className="text-2xl font-bold text-indigo-600">{accuracy}%</div>
            <div className="text-xs text-slate-500 mt-0.5">Accuracy</div>
          </div>
          <div className="bg-white border border-slate-200 rounded-lg px-4 py-2 text-center min-w-16">
            <div className="text-2xl font-bold text-indigo-600">{total}</div>
            <div className="text-xs text-slate-500 mt-0.5">Answered</div>
          </div>
        </div>
      )}

      {/* Play / Replay */}
      <div className="flex gap-3 mb-8">
        <button
          onClick={phase === 'start' ? () => startRound(difficulty) : replay}
          className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white font-medium px-6 py-3 rounded-xl transition-colors cursor-pointer"
        >
          <span>🔊</span>
          {phase === 'start' ? 'Play Note' : 'Replay'}
        </button>
      </div>

      {/* Answer grid */}
      {phase !== 'start' && (
        <div className="grid grid-cols-3 sm:grid-cols-4 gap-2 max-w-xs mb-4">
          {choices.map(name => {
            let cls: string
            if (phase === 'answered') {
              if (name === correctAnswer) {
                cls = 'bg-emerald-50 border-2 border-emerald-500 text-emerald-700 cursor-default'
              } else if (name === guess) {
                cls = 'bg-red-50 border-2 border-red-400 text-red-700 cursor-default'
              } else {
                cls = 'bg-white border border-slate-100 text-slate-300 cursor-default'
              }
            } else if (name === selected) {
              cls = 'bg-indigo-50 border-2 border-indigo-500 text-indigo-700 cursor-pointer'
            } else {
              cls = 'bg-white border border-slate-200 text-slate-800 hover:bg-slate-50 hover:border-slate-300 cursor-pointer'
            }
            return (
              <button
                key={name}
                onClick={() => handleSelect(name)}
                className={`py-3 rounded-lg font-semibold text-sm transition-colors ${cls}`}
              >
                {noteDisplayName(name)}
              </button>
            )
          })}
        </div>
      )}

      {/* Submit / Next / Feedback row */}
      {phase === 'waiting' && (
        <button
          onClick={handleSubmit}
          disabled={selected === null}
          className="px-6 py-2.5 rounded-xl font-medium text-sm transition-colors cursor-pointer
            disabled:bg-slate-100 disabled:text-slate-400 disabled:cursor-not-allowed
            enabled:bg-slate-800 enabled:hover:bg-slate-900 enabled:text-white"
        >
          Submit
        </button>
      )}

      {phase === 'answered' && guess !== null && correctAnswer !== null && (
        <div className="flex items-center gap-4">
          <div
            className={`inline-block rounded-lg px-4 py-2.5 text-sm font-medium border ${
              guess === correctAnswer
                ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                : 'bg-red-50 text-red-700 border-red-200'
            }`}
          >
            {guess === correctAnswer ? '✓ Correct!' : `✗ That was ${noteDisplayName(correctAnswer)}`}
          </div>
          <button
            onClick={() => startRound(difficulty)}
            className="flex items-center gap-2 bg-slate-800 hover:bg-slate-900 text-white font-medium px-6 py-2.5 rounded-xl transition-colors cursor-pointer text-sm"
          >
            Next →
          </button>
        </div>
      )}
    </div>
  )
}
