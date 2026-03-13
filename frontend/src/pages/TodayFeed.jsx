import { useState, useMemo } from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { useFeed } from '../hooks/useApi'
import FeedCard from '../components/FeedCard'
import { SkeletonList } from '../components/Skeleton'
import EmptyState from '../components/EmptyState'

function getDateStr(offset = 0) {
  const d = new Date()
  d.setDate(d.getDate() + offset)
  return d.toISOString().split('T')[0]
}

function formatDate(dateStr) {
  const d = new Date(dateStr + 'T00:00:00')
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const diff = Math.round((today - d) / 86400000)

  if (diff === 0) return '오늘'
  if (diff === 1) return '어제'
  if (diff === -1) return '내일'

  const month = d.getMonth() + 1
  const day = d.getDate()
  const weekday = ['일', '월', '화', '수', '목', '금', '토'][d.getDay()]
  return `${month}/${day} (${weekday})`
}

export default function TodayFeed() {
  const [dayOffset, setDayOffset] = useState(0)
  const dateStr = useMemo(() => getDateStr(dayOffset), [dayOffset])
  const { data, isLoading, error } = useFeed(dateStr)

  return (
    <div>
      {/* 날짜 네비게이션 */}
      <div className="flex items-center justify-between mb-4">
        <button
          onClick={() => setDayOffset(d => d - 1)}
          className="p-2 rounded-full hover:bg-gray-100 transition-colors"
        >
          <ChevronLeft size={20} />
        </button>
        <h2 className="text-lg font-bold">{formatDate(dateStr)}</h2>
        <button
          onClick={() => setDayOffset(d => Math.min(d + 1, 0))}
          disabled={dayOffset >= 0}
          className="p-2 rounded-full hover:bg-gray-100 transition-colors disabled:opacity-30"
        >
          <ChevronRight size={20} />
        </button>
      </div>

      {/* 피드 카드 */}
      {isLoading && <SkeletonList count={5} type="feed" />}

      {error && (
        <EmptyState message="피드를 불러올 수 없어요" emoji="😵" />
      )}

      {data?.items?.length > 0 && (
        data.items.map((item, idx) => (
          <FeedCard key={idx} item={item} />
        ))
      )}

      {data && (!data.items || data.items.length === 0) && (
        <EmptyState message={data.message || '아직 피드가 없어요'} emoji="🍚" />
      )}
    </div>
  )
}
