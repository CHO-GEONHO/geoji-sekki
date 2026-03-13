import { useState } from 'react'
import { Search } from 'lucide-react'
import { useCvsProducts, useCvsCompare } from '../hooks/useApi'
import { useAppStore } from '../stores/appStore'
import ProductCard from '../components/ProductCard'
import FilterBar from '../components/FilterBar'
import { SkeletonList } from '../components/Skeleton'
import EmptyState from '../components/EmptyState'

const STORES = ['gs25', 'cu', 'seven', 'emart24']
const EVENTS = ['1+1', '2+1', '3+1', 'discount']
const CATEGORIES = ['음료', '과자', '간편식사', '아이스크림', '생활용품', '유제품']

const STORE_LABELS = { gs25: 'GS25', cu: 'CU', seven: '세븐', emart24: '이마트24' }

export default function CvsPage() {
  const { cvsStore, cvsCategory, cvsEventType, setCvsStore, setCvsCategory, setCvsEventType } = useAppStore()
  const [compareQuery, setCompareQuery] = useState('')
  const [showCompare, setShowCompare] = useState(false)
  const [page, setPage] = useState(1)

  const { data, isLoading } = useCvsProducts({
    store: cvsStore, category: cvsCategory, event_type: cvsEventType, page,
  })
  const { data: compareData, isLoading: compareLoading } = useCvsCompare(
    showCompare ? compareQuery : null
  )

  return (
    <div>
      {/* 편의점 탭 */}
      <div className="flex gap-2 mb-3 overflow-x-auto">
        <button
          onClick={() => { setCvsStore(null); setPage(1) }}
          className={`filter-chip whitespace-nowrap ${!cvsStore ? 'filter-chip-active' : 'filter-chip-inactive'}`}
        >
          전체
        </button>
        {STORES.map(s => (
          <button
            key={s}
            onClick={() => { setCvsStore(cvsStore === s ? null : s); setPage(1) }}
            className={`filter-chip whitespace-nowrap ${cvsStore === s ? 'filter-chip-active' : 'filter-chip-inactive'}`}
          >
            {STORE_LABELS[s]}
          </button>
        ))}
      </div>

      {/* 행사 타입 필터 */}
      <FilterBar
        filters={EVENTS}
        active={cvsEventType}
        onSelect={(v) => { setCvsEventType(v); setPage(1) }}
      />

      {/* 카테고리 필터 */}
      <div className="mt-2">
        <FilterBar
          filters={CATEGORIES}
          active={cvsCategory}
          onSelect={(v) => { setCvsCategory(v); setPage(1) }}
        />
      </div>

      {/* 비교 검색 */}
      <div className="mt-3 mb-4">
        <div className="flex gap-2">
          <div className="flex-1 relative">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              type="text"
              value={compareQuery}
              onChange={(e) => setCompareQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && setShowCompare(true)}
              placeholder="상품명으로 편의점 비교"
              className="w-full pl-9 pr-3 py-2 rounded-xl border border-gray-200 text-sm focus:outline-none focus:border-geoji-400"
            />
          </div>
          <button
            onClick={() => setShowCompare(true)}
            className="px-4 py-2 bg-geoji-500 text-white rounded-xl text-sm font-medium"
          >
            비교
          </button>
        </div>

        {/* 비교 결과 */}
        {showCompare && compareData && compareData.stores?.length > 0 && (
          <div className="mt-3 card">
            <h3 className="font-bold text-sm mb-2">
              🔍 "{compareData.product_name}" 비교 결과
            </h3>
            <div className="space-y-2">
              {compareData.stores.map((s, i) => (
                <div key={i} className="flex items-center justify-between">
                  <span className={`text-sm ${i === 0 ? 'font-bold text-geoji-600' : 'text-gray-600'}`}>
                    {STORE_LABELS[s.store] || s.store}
                    {i === 0 && ' 👑'}
                  </span>
                  <div className="text-right">
                    <span className="text-sm font-medium">
                      {s.unit_price?.toLocaleString() || s.price?.toLocaleString()}원
                    </span>
                    <span className="text-xs text-gray-400 ml-1">({s.event_type})</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
        {showCompare && compareData && compareData.stores?.length === 0 && (
          <p className="mt-2 text-sm text-gray-400">검색 결과 없음</p>
        )}
      </div>

      {/* 상품 리스트 */}
      {isLoading && <SkeletonList count={8} type="product" />}

      {data?.items?.map(product => (
        <ProductCard key={product.id} product={product} type="cvs" />
      ))}

      {data && data.items?.length === 0 && (
        <EmptyState message="이번 주 행사 상품이 없어요" emoji="🏪" />
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
