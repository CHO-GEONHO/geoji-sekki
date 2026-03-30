import { useState } from 'react'
import { useCoupang } from '../hooks/useApi'
import { useAppStore } from '../stores/appStore'
import ProductCard from '../components/ProductCard'
import FilterBar from '../components/FilterBar'
import { SkeletonList } from '../components/Skeleton'
import EmptyState from '../components/EmptyState'

const CATEGORIES = ['전자제품', '식품', '패션', '뷰티', '생활용품', '유아동', '건강']

export default function CoupangPage() {
  const { coupangCategory, coupangSort, setCoupangCategory, setCoupangSort } = useAppStore()
  const [page, setPage] = useState(1)

  const { data, isLoading } = useCoupang({
    category: coupangCategory, sort: coupangSort, page,
  })

  return (
    <div>
      {/* 정렬 */}
      <div className="flex gap-2 mb-3">
        <button
          onClick={() => { setCoupangSort('discount'); setPage(1) }}
          className={`filter-chip ${coupangSort === 'discount' ? 'filter-chip-active' : 'filter-chip-inactive'}`}
        >
          💰 할인율순
        </button>
        <button
          onClick={() => { setCoupangSort('price'); setPage(1) }}
          className={`filter-chip ${coupangSort === 'price' ? 'filter-chip-active' : 'filter-chip-inactive'}`}
        >
          💵 가격순
        </button>
        <button
          onClick={() => { setCoupangSort('latest'); setPage(1) }}
          className={`filter-chip ${coupangSort === 'latest' ? 'filter-chip-active' : 'filter-chip-inactive'}`}
        >
          🕐 최신순
        </button>
      </div>

      {/* 카테고리 */}
      <FilterBar
        filters={CATEGORIES}
        active={coupangCategory}
        onSelect={(v) => { setCoupangCategory(v); setPage(1) }}
      />

      {/* 상품 리스트 */}
      <div className="mt-3">
        {isLoading && <SkeletonList count={8} type="product" />}

        {data?.items?.map(product => (
          <ProductCard key={product.id} product={product} type="coupang" />
        ))}

        {data && data.items?.length === 0 && (
          <EmptyState message="골드박스 상품이 없어요" emoji="🛒" />
        )}
      </div>

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
