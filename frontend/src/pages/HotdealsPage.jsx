import { useState } from 'react'
import { ExternalLink, ThumbsUp, MessageCircle } from 'lucide-react'
import { useHotdeals } from '../hooks/useApi'
import { useAppStore } from '../stores/appStore'
import FilterBar from '../components/FilterBar'
import { SkeletonList } from '../components/Skeleton'
import EmptyState from '../components/EmptyState'
import ShareButton from '../components/ShareButton'

const CATEGORIES = ['전자제품', '식품', '패션', '뷰티', '생활용품', '여행', '도서/문화']

export default function HotdealsPage() {
  const { hotdealSort, hotdealCategory, setHotdealSort, setHotdealCategory } = useAppStore()
  const [page, setPage] = useState(1)

  const { data, isLoading } = useHotdeals({
    sort: hotdealSort, category: hotdealCategory, page,
  })

  return (
    <div>
      {/* 정렬 */}
      <div className="flex gap-2 mb-3">
        <button
          onClick={() => { setHotdealSort('votes'); setPage(1) }}
          className={`filter-chip ${hotdealSort === 'votes' ? 'filter-chip-active' : 'filter-chip-inactive'}`}
        >
          🔥 추천순
        </button>
        <button
          onClick={() => { setHotdealSort('latest'); setPage(1) }}
          className={`filter-chip ${hotdealSort === 'latest' ? 'filter-chip-active' : 'filter-chip-inactive'}`}
        >
          🕐 최신순
        </button>
      </div>

      {/* 카테고리 */}
      <FilterBar
        filters={CATEGORIES}
        active={hotdealCategory}
        onSelect={(v) => { setHotdealCategory(v); setPage(1) }}
      />

      {/* 핫딜 리스트 */}
      <div className="mt-3">
        {isLoading && <SkeletonList count={8} type="product" />}

        {data?.items?.map(deal => (
          <HotdealCard key={deal.id} deal={deal} />
        ))}

        {data && data.items?.length === 0 && (
          <EmptyState message="핫딜이 없어요" emoji="🔥" />
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

function HotdealCard({ deal }) {
  return (
    <div className="card mb-2 active:scale-[0.98] transition-transform">
      <div className="flex gap-3">
        {deal.image_url && (
          <img
            src={deal.image_url}
            alt=""
            loading="lazy"
            className="w-16 h-16 rounded-lg object-cover flex-shrink-0 bg-gray-100"
            onError={(e) => { e.target.style.display = 'none' }}
          />
        )}
        <div className="flex-1 min-w-0">
          <h4 className="font-semibold text-sm leading-snug line-clamp-2">{deal.title}</h4>

          {deal.summary && (
            <p className="text-xs text-gray-500 mt-1">💬 {deal.summary}</p>
          )}

          <div className="flex items-center gap-3 mt-2 text-xs text-gray-400">
            <span className="flex items-center gap-1">
              <ThumbsUp size={12} /> {deal.vote_count}
            </span>
            <span className="flex items-center gap-1">
              <MessageCircle size={12} /> {deal.comment_count}
            </span>
            {deal.price_value && (
              <span className="font-bold text-geoji-600">
                {deal.price_value.toLocaleString()}원
              </span>
            )}
            {deal.category && (
              <span className="badge bg-gray-100 text-gray-500">{deal.category}</span>
            )}
          </div>
        </div>

        <div className="flex flex-col items-center gap-1 flex-shrink-0">
          <a
            href={`/api/go/${deal.id}`}
            target="_blank"
            rel="noopener noreferrer"
            className="p-1.5 rounded-full text-gray-400 hover:text-geoji-600 hover:bg-geoji-50"
          >
            <ExternalLink size={16} />
          </a>
          <ShareButton title={deal.title} text={deal.summary || deal.title} url={deal.url} />
        </div>
      </div>
    </div>
  )
}
