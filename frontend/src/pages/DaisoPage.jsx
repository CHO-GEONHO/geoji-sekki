import { useState } from 'react'
import { useDaiso } from '../hooks/useApi'
import { useAppStore } from '../stores/appStore'
import ProductCard from '../components/ProductCard'
import FilterBar from '../components/FilterBar'
import { SkeletonList } from '../components/Skeleton'
import EmptyState from '../components/EmptyState'

const CATEGORIES = ['생활용품', '주방', '문구', '뷰티', '식품', '전자', '인테리어', '패션잡화']
const PRICES = [1000, 2000, 3000, 5000]
const SORTS = [
  { value: 'score', label: 'AI추천순' },
  { value: 'ranking', label: '베스트순' },
  { value: 'price', label: '가격순' },
]

export default function DaisoPage() {
  const { daisoCategory, daisoPrice, daisoSort, setDaisoCategory, setDaisoPrice, setDaisoSort } = useAppStore()
  const [page, setPage] = useState(1)

  const { data, isLoading } = useDaiso({
    category: daisoCategory, price: daisoPrice, sort: daisoSort, page,
  })

  return (
    <div>
      {/* 카테고리 */}
      <FilterBar
        filters={CATEGORIES}
        active={daisoCategory}
        onSelect={(v) => { setDaisoCategory(v); setPage(1) }}
      />

      {/* 가격대 필터 */}
      <div className="flex gap-2 mt-2 overflow-x-auto">
        <button
          onClick={() => { setDaisoPrice(null); setPage(1) }}
          className={`filter-chip whitespace-nowrap ${!daisoPrice ? 'filter-chip-active' : 'filter-chip-inactive'}`}
        >
          전체
        </button>
        {PRICES.map(p => (
          <button
            key={p}
            onClick={() => { setDaisoPrice(daisoPrice === p ? null : p); setPage(1) }}
            className={`filter-chip whitespace-nowrap ${daisoPrice === p ? 'filter-chip-active' : 'filter-chip-inactive'}`}
          >
            {p.toLocaleString()}원
          </button>
        ))}
      </div>

      {/* 정렬 */}
      <div className="flex gap-1 mt-3 mb-3">
        {SORTS.map(s => (
          <button
            key={s.value}
            onClick={() => { setDaisoSort(s.value); setPage(1) }}
            className={`text-xs px-2 py-1 rounded-md ${
              daisoSort === s.value ? 'bg-geoji-500 text-white' : 'text-gray-500'
            }`}
          >
            {s.label}
          </button>
        ))}
      </div>

      {/* 상품 */}
      {isLoading && <SkeletonList count={8} type="product" />}

      {data?.items?.map(product => (
        <ProductCard key={product.id} product={product} type="daiso" />
      ))}

      {data && data.items?.length === 0 && (
        <EmptyState message="이번 달 상품이 없어요" emoji="🏷️" />
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
