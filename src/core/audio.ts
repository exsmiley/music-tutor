let ctx: AudioContext | null = null

function getContext(): AudioContext {
  if (!ctx) ctx = new AudioContext()
  if (ctx.state === 'suspended') ctx.resume()
  return ctx
}

export function playNote(midi: number, duration = 1.5): void {
  const ac = getContext()
  const freq = 440 * Math.pow(2, (midi - 69) / 12)

  const osc = ac.createOscillator()
  const gain = ac.createGain()
  osc.connect(gain)
  gain.connect(ac.destination)

  osc.type = 'sine'
  osc.frequency.value = freq

  const now = ac.currentTime
  gain.gain.setValueAtTime(0.5, now)
  gain.gain.exponentialRampToValueAtTime(0.001, now + duration)

  osc.start(now)
  osc.stop(now + duration)
}
