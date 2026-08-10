import { Link } from 'react-router-dom'

const MODULES = [
  {
    title: 'Pitch Identification',
    description: 'Train your ear to identify individual notes by sound.',
    href: '/pitch',
    active: true,
    icon: '🎵',
  },
  {
    title: 'Tuner',
    description: 'Detect the pitch of your instrument or voice in real time.',
    href: '/tuner',
    active: true,
    icon: '🎙',
  },
  {
    title: 'Tab Player',
    description: 'AI-transcribed tabs per instrument — play along with any song.',
    href: '/tabs',
    active: true,
    icon: '🎼',
  },
  {
    title: 'Intervals',
    description: 'Recognize the distance between two notes.',
    href: '/intervals',
    active: false,
    icon: '↔️',
  },
  {
    title: 'Chord Quality',
    description: 'Identify major, minor, diminished, and augmented chords.',
    href: '/chords',
    active: false,
    icon: '🎸',
  },
  {
    title: 'Rhythm',
    description: 'Clap along to rhythmic patterns and improve your timing.',
    href: '/rhythm',
    active: false,
    icon: '🥁',
  },
  {
    title: 'Sight Reading',
    description: 'Read sheet music and identify notes on the staff.',
    href: '/sight-reading',
    active: false,
    icon: '📄',
  },
]

export default function Home() {
  return (
    <div>
      <h1 className="text-3xl font-bold text-slate-900 mb-2">Ear Training</h1>
      <p className="text-slate-500 mb-8">Build your musical intuition one module at a time.</p>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {MODULES.map(mod => (
          <div
            key={mod.href}
            className={`bg-white rounded-xl border border-slate-200 p-5 flex flex-col gap-3 ${
              mod.active ? 'shadow-sm hover:shadow-md transition-shadow' : 'opacity-60'
            }`}
          >
            <span className="text-3xl">{mod.icon}</span>
            <div>
              <h2 className="font-semibold text-slate-900 text-lg">{mod.title}</h2>
              <p className="text-sm text-slate-500 mt-1">{mod.description}</p>
            </div>
            {mod.active ? (
              <Link
                to={mod.href}
                className="mt-auto inline-flex items-center justify-center bg-indigo-600 text-white text-sm font-medium px-4 py-2 rounded-lg hover:bg-indigo-700 transition-colors"
              >
                Start
              </Link>
            ) : (
              <span className="mt-auto inline-flex items-center justify-center bg-slate-100 text-slate-400 text-sm font-medium px-4 py-2 rounded-lg cursor-default">
                Coming soon
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
