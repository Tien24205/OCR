import { NavLink, Navigate, Route, Routes } from 'react-router-dom'
import { HealthBanner } from './components/HealthBanner'
import { CapturePage } from './pages/CapturePage'
import { ContactsPage } from './pages/ContactsPage'
import { ReviewPage } from './pages/ReviewPage'

export default function App() {
  return (
    <>
      <header className="topbar">
        <h1>Danh thiếp → Hồ sơ đối tác</h1>
        <nav>
          <NavLink to="/capture">Quét thẻ</NavLink>
          <NavLink to="/contacts">Hồ sơ</NavLink>
        </nav>
      </header>

      <main>
        <HealthBanner />
        <Routes>
          <Route path="/" element={<Navigate to="/capture" replace />} />
          <Route path="/capture" element={<CapturePage />} />
          <Route path="/scans/:scanId/review" element={<ReviewPage />} />
          <Route path="/contacts" element={<ContactsPage />} />
          <Route path="*" element={<p>Không tìm thấy trang.</p>} />
        </Routes>
      </main>
    </>
  )
}
