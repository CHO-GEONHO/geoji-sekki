import ShareButton from './ShareButton'
import StoreTag from './StoreTag'

const SOURCE_COLORS = {
  cvs: 'bg-blue-100 text-blue-700',
  hotdeal: 'bg-red-100 text-red-700',
  oliveyoung: 'bg-purple-100 text-purple-700',
  daiso: 'bg-yellow-100 text-yellow-700',
}

const SOURCE_LABELS = {
  cvs: '편의점',
  hotdeal: '핫딜',
  oliveyoung: '올영',
  daiso: '다이소',
}

export default function FeedCard({ item }) {
  const { title, body, source, store, category } = item

  return (
    <div className="card mb-3 active:scale-[0.98] transition-transform">
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <h3 className="font-bold text-base leading-snug mb-1.5">{title}</h3>
          <p className="text-sm text-gray-600 whitespace-pre-line leading-relaxed">
            {body}
          </p>
        </div>
        <ShareButton title={title} text={`${title}\n${body}`} />
      </div>

      <div className="flex items-center gap-2 mt-3">
        <span className={`badge ${SOURCE_COLORS[source] || 'bg-gray-100 text-gray-600'}`}>
          {SOURCE_LABELS[source] || source}
        </span>
        {store && <StoreTag store={store} />}
        {category && (
          <span className="badge bg-gray-50 text-gray-500">{category}</span>
        )}
      </div>
    </div>
  )
}
