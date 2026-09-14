// Client for the transcription service (transcription/server.py), reached
// through the Vite dev proxy at /api.

import type { StemJson } from './alphatex'

export interface JobMeta {
  id: string
  url: string
  title: string
  instruments: string[] | null
  status: 'queued' | 'running' | 'done' | 'error'
  progress: string
  created: number
  error?: string
  summary?: {
    stems: string[]
    drums: boolean
    tempo: number
    energy: Record<string, number>
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, init)
  if (!res.ok) {
    const body = await res.text().catch(() => '')
    throw new Error(`${res.status} ${res.statusText}: ${body.slice(0, 200)}`)
  }
  return res.json() as Promise<T>
}

export const listJobs = () => request<JobMeta[]>('/api/jobs')

export const getJob = (id: string) => request<JobMeta>(`/api/jobs/${id}`)

export const createJob = (url: string, instruments: string[] | null) =>
  request<JobMeta>('/api/jobs', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url, instruments }),
  })

export const deleteJob = (id: string) =>
  request<{ deleted: string }>(`/api/jobs/${id}`, { method: 'DELETE' })

export const fileUrl = (id: string, name: string) => `/api/jobs/${id}/files/${name}`

export const getStem = (id: string, stem: string) =>
  request<StemJson>(fileUrl(id, `${stem}.json`))
