import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Home from './pages/Home'
import PitchIdentification from './modules/PitchIdentification'

export default function App() {
  return (
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/pitch" element={<PitchIdentification />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  )
}
