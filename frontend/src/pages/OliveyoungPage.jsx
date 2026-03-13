import { useState } from 'react'
import { useOliveyoung, useOyCalendar } from '../hooks/useApi'
import { useAppStore } from '../stores/appStore'
import ProductCard from '../components/ProductCard'
import FilterBar from '../components/FilterBar'
import { SkeletonList } from '../components/Skeleton'
import EmptyState from '../components/EmptyState'

const CATEGORIES = ['스킨케어', '메이크업', '헤어', '바디', '건강', '향수', '남성']
const SORTS = [
  { value: 'discount', label: '할인율순' },
  { value: 'price', label: '가격순' },
  { value: 'latest', label: '최신순' },
]

export default function OliveyoungPage() {
  const { oyCategory, oySort, setOyCategory, setOySort } = useAppStore()
  const [page, setPage] = useState(1)
  const [showCalendar, setShowCalendar] = useState(false)

  const { data, isLoading } = useOliveyoung({ category: oyCategory, sort: oySort, page })
  const { data: calendar } = useOyCalendar()

  return (
    <div>
      {/* 카테고리 필터 */}
      <FilterBar
        filters={CATEGORIES}
        active={oyCategory}
        onSelect={(v) => { setOyCategory(v); setPage(1) }}
      />

      {/* 정렬 + 캘린더 토글 */}
      <div className="flex items-center justify-between mt-3 mb-3">
        <div className="flex gap-1">
          {SORTS.map(s => (
            <button
              key={s.value}
              onClick={() => { setOySort(s.value); setPage(1) }}
              className={`text-xs px-2 py-1 rounded-md ${
                oySort === s.value ? 'bg-geoji-500 text-white' : 'text-gray-500'
              }`}
            >
              {s.label}
            </button>
          ))}
        </div>
        <button
          onClick={() => setShowCalendar(!showCalendar)}
          className="text-xs text-geoji-600 font-medium"
        >
          {showCalendar ? '닫기' : '📅 세일 일정'}
        </button>
      </div>

      {/* 올영 세일 캘린더 */}
      {showCalendar && calendar && (
        <div className="card mb-4">
          <h3 className="font-bold text-sm mb-2">올영 세일 일정</h3>
          <div className="space-y-1.5">
            {calendar.slice(0, 12).map((event, i) => {
              const now = new Date()
              const start = new Date(event.start_date)
              const end = new Date(event.end_date)
              const isActive = now >= start && now <= end
              const isPast = now > end

              return (
                <div
                  key={i}
                  className={`flex items-center justify-between text-xs py-1 ${
                    isPast ? 'text-gray-300' : isActive ? 'text-geoji-600 font-bold' : 'text-gray-600'
                  }`}
                >
                  <span>
                    {isActive && '🔥 '}{event.event_name}
                  </span>
                  <span>
                    {event.start_date} ~ {event.end_date}
                  </span>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* 상품 리스트 */}
      {isLoading && <SkeletonList count={8} type="product" />}

      {data?.items?.map(product => (
        <ProductCard key={product.id} product={product} type="oliveyoung" />
      ))}

      {data && data.items?.length === 0 && (
        <EmptyState message="세일 상품이 없어요" emoji="💄" />
      )}

      {/* 페이지네이션 */}
      {data?.total_pages > 1 && (
        <div className="flex justify-center gap-2 mt-4">
          <button
            onClick={() => setPage(p => Math.max(1, p - 1))}
            disabled={page <= 1}
            className="px-3 py-1.5 rounded-lg border text-sm disabled:opacity-30"
          >
            이전
          </button>
          <span className="px-3 py-1.5 text-sm text-gray-500">
            {page} / {data.total_pages}
          </span>
          <button
            onClick={() => setPage(p => Math.min(data.total_pages, p + 1))}
            disabled={page >= data.total_pages}
            className="px-3 py-1.5 rounded-lg border text-sm disabled:opacity-30"
          >
            다음
          </button>
        </div>
      )}
    </div>
  )
}
