import { useLocation, useNavigate } from 'react-router-dom'
import { Home, Store, Sparkles, ShoppingBag, Flame } from 'lucide-react'

const tabs = [
  { path: '/', label: '오늘', icon: Home },
  { path: '/cvs', label: '편의점', icon: Store },
  { path: '/oliveyoung', label: '올영', icon: Sparkles },
  { path: '/daiso', label: '다이소', icon: ShoppingBag },
  { path: '/hotdeals', label: '핫딜', icon: Flame },
]

export default function TabBar() {
  const location = useLocation()
  const navigate = useNavigate()

  return (
    <nav className="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-100 safe-bottom z-50">
      <div className="max-w-lg mx-auto flex">
        {tabs.map(({ path, label, icon: Icon }) => {
          const active = location.pathname === path
          return (
            <button
              key={path}
              onClick={() => navigate(path)}
              className={`flex-1 flex flex-col items-center py-2 pt-3 transition-colors ${
                active ? 'text-geoji-600' : 'text-gray-400'
              }`}
            >
              <Icon size={20} strokeWidth={active ? 2.5 : 1.5} />
              <span className={`text-[10px] mt-1 ${active ? 'font-semibold' : ''}`}>
                {label}
              </span>
            </button>
          )
        })}
      </div>
    </nav>
  )
}
