import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Home from './pages/Home'
import PitchIdentification from './modules/PitchIdentification'
import Tuner from './modules/Tuner'
import TabPlayer from './modules/TabPlayer'

export default function App() {
  return (
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/pitch" element={<PitchIdentification />} />
          <Route path="/tuner" element={<Tuner />} />
          <Route path="/tabs" element={<TabPlayer />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  )
}
