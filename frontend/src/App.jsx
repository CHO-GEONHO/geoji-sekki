import { lazy, Suspense, useState, useEffect } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import TabBar from './components/TabBar'
import LoadingSpinner from './components/LoadingSpinner'
import { getDailyPhrase, getMsUntilKstMidnight } from './utils/phrases'

const TodayFeed = lazy(() => import('./pages/TodayFeed'))
const CvsPage = lazy(() => import('./pages/CvsPage'))
const OliveyoungPage = lazy(() => import('./pages/OliveyoungPage'))
const DaisoPage = lazy(() => import('./pages/DaisoPage'))
const HotdealsPage = lazy(() => import('./pages/HotdealsPage'))

export default function App() {
  const [headerPhrase, setHeaderPhrase] = useState(() => getDailyPhrase(1))

  useEffect(() => {
    const timer = setTimeout(() => setHeaderPhrase(getDailyPhrase(1)), getMsUntilKstMidnight())
    return () => clearTimeout(timer)
  }, [headerPhrase])

  return (
    <div className="min-h-screen bg-gray-50 pb-20">
      {/* Header */}
      <header className="sticky top-0 z-50 bg-white border-b border-gray-100 px-4 py-2">
        <div className="max-w-lg mx-auto flex items-center gap-2.5">
          <img
            src="/icons/icon-192.png"
            alt="거지세끼"
            className="w-9 h-9 rounded-xl object-cover flex-shrink-0"
          />
          <div className="min-w-0">
            <h1 className="text-[17px] font-black text-gray-900 leading-none tracking-tight">거지세끼</h1>
            <p className="text-[11px] text-gray-400 font-medium mt-0.5 truncate">{headerPhrase}</p>
          </div>
        </div>
      </header>

      {/* Content */}
      <main className="max-w-lg mx-auto px-4 pt-4">
        <Suspense fallback={<LoadingSpinner />}>
          <Routes>
            <Route path="/" element={<TodayFeed />} />
            <Route path="/cvs" element={<CvsPage />} />
            <Route path="/oliveyoung" element={<OliveyoungPage />} />
            <Route path="/daiso" element={<DaisoPage />} />
            <Route path="/hotdeals" element={<HotdealsPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Suspense>
      </main>

      {/* Bottom Tab Bar */}
      <TabBar />
    </div>
  )
}
