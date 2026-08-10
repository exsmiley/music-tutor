import { useCallback, useEffect, useState } from 'react'
import Player from './Player'
import { createJob, deleteJob, getJob, listJobs, type JobMeta } from './api'

const INSTRUMENT_CHOICES = ['guitar', 'bass', 'vocals', 'other', 'piano']

type View = { kind: 'library' } | { kind: 'new' } | { kind: 'job'; id: string }

export default function TabPlayer() {
  const [view, setView] = useState<View>({ kind: 'library' })

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <h1 className="text-3xl font-bold text-slate-900">Tab Player</h1>
        {view.kind !== 'library' && (
          <button
            onClick={() => setView({ kind: 'library' })}
            className="text-sm text-slate-500 hover:text-slate-700"
          >
            ← Back to library
          </button>
        )}
      </div>
      <p className="text-slate-500 mb-6">
        AI-transcribed tabs, per instrument. Paste a song, pick stems, play along.
      </p>

      {view.kind === 'library' && (
        <Library
          onNew={() => setView({ kind: 'new' })}
          onOpen={id => setView({ kind: 'job', id })}
        />
      )}
      {view.kind === 'new' && <NewJob onCreated={id => setView({ kind: 'job', id })} />}
      {view.kind === 'job' && <Job id={view.id} />}
    </div>
  )
}

function Library({ onNew, onOpen }: { onNew: () => void; onOpen: (id: string) => void }) {
  const [jobs, setJobs] = useState<JobMeta[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(() => {
    listJobs()
      .then(setJobs)
      .catch(() =>
        setError(
          'Transcription service is not reachable. Start it with: ' +
            'cd transcription && .venv/bin/uvicorn server:app --port 8000',
        ),
      )
  }, [])

  useEffect(() => {
    refresh()
    const timer = setInterval(refresh, 5000)
    return () => clearInterval(timer)
  }, [refresh])

  if (error) {
    return (
      <div className="bg-amber-50 border border-amber-200 text-amber-800 rounded-lg px-4 py-3">
        {error}
      </div>
    )
  }
  if (jobs === null) return <p className="text-slate-400">Loading…</p>

  return (
    <div>
      <button
        onClick={onNew}
        className="mb-4 bg-indigo-600 text-white text-sm font-medium px-4 py-2 rounded-lg hover:bg-indigo-700 transition-colors"
      >
        + New transcription
      </button>

      {jobs.length === 0 ? (
        <p className="text-slate-400">No songs yet — transcribe your first one.</p>
      ) : (
        <ul className="space-y-2">
          {jobs.map(job => (
            <li
              key={job.id}
              className="bg-white rounded-xl border border-slate-200 px-4 py-3 flex items-center gap-3"
            >
              <div className="min-w-0 flex-1">
                <p className="font-medium text-slate-900 truncate">{job.title}</p>
                <p className="text-xs text-slate-400">
                  {job.status === 'done' && job.summary
                    ? `${job.summary.stems.join(', ')}${job.summary.drums ? ' + drums' : ''} · ${Math.round(job.summary.tempo)} BPM`
                    : job.status === 'error'
                      ? `failed: ${job.error ?? 'unknown error'}`
                      : `${job.status}${job.progress ? ` — ${job.progress}` : ''}`}
                </p>
              </div>
              {job.status === 'done' ? (
                <button
                  onClick={() => onOpen(job.id)}
                  className="bg-indigo-600 text-white text-sm font-medium px-3 py-1.5 rounded-lg hover:bg-indigo-700"
                >
                  Open
                </button>
              ) : job.status === 'error' ? (
                <button
                  onClick={() => deleteJob(job.id).then(refresh)}
                  className="text-sm text-red-500 hover:text-red-700"
                >
                  Remove
                </button>
              ) : (
                <span className="text-sm text-slate-400 animate-pulse">working…</span>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function NewJob({ onCreated }: { onCreated: (id: string) => void }) {
  const [url, setUrl] = useState('')
  const [autodetect, setAutodetect] = useState(true)
  const [instruments, setInstruments] = useState<Set<string>>(new Set(['guitar', 'bass']))
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const submit = () => {
    if (!url.trim()) return
    setSubmitting(true)
    setError(null)
    createJob(url.trim(), autodetect ? null : [...instruments])
      .then(job => onCreated(job.id))
      .catch(e => setError(String(e)))
      .finally(() => setSubmitting(false))
  }

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5 max-w-xl">
      <label className="block text-sm font-medium text-slate-700 mb-1">
        YouTube URL or direct audio link
      </label>
      <input
        value={url}
        onChange={e => setUrl(e.target.value)}
        onKeyDown={e => e.key === 'Enter' && submit()}
        placeholder="https://www.youtube.com/watch?v=…"
        className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm mb-4 focus:outline-none focus:ring-2 focus:ring-indigo-500"
      />

      <label className="flex items-center gap-2 text-sm text-slate-700 mb-2">
        <input
          type="checkbox"
          checked={autodetect}
          onChange={e => setAutodetect(e.target.checked)}
        />
        Autodetect instruments
      </label>

      {!autodetect && (
        <div className="flex flex-wrap gap-2 mb-4">
          {INSTRUMENT_CHOICES.map(inst => (
            <button
              key={inst}
              onClick={() =>
                setInstruments(prev => {
                  const next = new Set(prev)
                  if (next.has(inst)) next.delete(inst)
                  else next.add(inst)
                  return next
                })
              }
              className={`px-3 py-1.5 rounded-lg text-sm font-medium border transition-colors ${
                instruments.has(inst)
                  ? 'bg-indigo-600 border-indigo-600 text-white'
                  : 'bg-white border-slate-200 text-slate-600 hover:border-indigo-300'
              }`}
            >
              {inst}
            </button>
          ))}
        </div>
      )}

      <p className="text-xs text-slate-400 mb-4">
        Drums are detected automatically for MIDI playback but don't get a tab. Vocals are
        transcribed as a guitar tab. Transcription takes a few minutes.
      </p>

      {error && <p className="text-sm text-red-600 mb-3">{error}</p>}

      <button
        onClick={submit}
        disabled={submitting || !url.trim() || (!autodetect && instruments.size === 0)}
        className="bg-indigo-600 text-white text-sm font-medium px-4 py-2 rounded-lg hover:bg-indigo-700 transition-colors disabled:opacity-50"
      >
        {submitting ? 'Submitting…' : 'Transcribe'}
      </button>
    </div>
  )
}

const STAGES = ['downloading audio', 'tracking beats', 'separating stems', 'transcribing', 'detecting drums']

function Job({ id }: { id: string }) {
  const [job, setJob] = useState<JobMeta | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let timer: ReturnType<typeof setInterval> | undefined
    const poll = () =>
      getJob(id)
        .then(j => {
          setJob(j)
          if ((j.status === 'done' || j.status === 'error') && timer) clearInterval(timer)
        })
        .catch(e => setError(String(e)))
    poll()
    timer = setInterval(poll, 3000)
    return () => {
      if (timer) clearInterval(timer)
    }
  }, [id])

  if (error) return <p className="text-red-600">{error}</p>
  if (!job) return <p className="text-slate-400">Loading…</p>

  if (job.status === 'error') {
    return (
      <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-3">
        Transcription failed: {job.error ?? 'unknown error'}
      </div>
    )
  }

  if (job.status !== 'done') {
    const stageIndex = STAGES.findIndex(s => job.progress.startsWith(s.split(' ')[0]))
    return (
      <div className="bg-white rounded-xl border border-slate-200 p-5 max-w-xl">
        <p className="font-medium text-slate-900 mb-1">{job.title}</p>
        <p className="text-sm text-slate-500 mb-4">
          {job.status === 'queued' ? 'Waiting in queue…' : job.progress || 'Working…'}
        </p>
        <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
          <div
            className="h-full bg-indigo-500 rounded-full transition-all duration-1000 animate-pulse"
            style={{ width: `${Math.max(8, ((stageIndex + 1) / STAGES.length) * 100)}%` }}
          />
        </div>
        <p className="text-xs text-slate-400 mt-3">
          Stem separation is the slow step — a full song takes a few minutes on CPU.
        </p>
      </div>
    )
  }

  return (
    <div>
      <p className="font-medium text-slate-900 mb-3">{job.title}</p>
      <Player job={job} />
    </div>
  )
}
