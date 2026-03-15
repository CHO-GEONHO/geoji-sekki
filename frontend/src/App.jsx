import { lazy, Suspense } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import TabBar from './components/TabBar'
import LoadingSpinner from './components/LoadingSpinner'

const TodayFeed = lazy(() => import('./pages/TodayFeed'))
const CvsPage = lazy(() => import('./pages/CvsPage'))
const OliveyoungPage = lazy(() => import('./pages/OliveyoungPage'))
const DaisoPage = lazy(() => import('./pages/DaisoPage'))
const HotdealsPage = lazy(() => import('./pages/HotdealsPage'))

export default function App() {
  return (
    <div className="min-h-screen bg-gray-50 pb-20">
      {/* Header */}
      <header className="sticky top-0 z-50 bg-white border-b border-gray-100 px-4 pt-3 pb-2">
        <div className="max-w-lg mx-auto flex items-center justify-between">
          <div>
            <h1 className="text-xl font-black text-gray-900 leading-none tracking-tight">
              거지세끼 <span className="text-lg">🍚</span>
            </h1>
            <p className="text-[11px] text-gray-400 font-medium mt-0.5 tracking-wide">싸게 사고, 잘 살자</p>
          </div>
          <div className="text-right">
            <span className="inline-block bg-geoji-50 text-geoji-600 text-[10px] font-bold px-2 py-1 rounded-full border border-geoji-200">
              절약이 철학이다
            </span>
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
