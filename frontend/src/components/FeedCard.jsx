import ShareButton from './ShareButton'

const SOURCE_CONFIG = {
  cvs:        { label: '편의점', color: 'bg-blue-500',   text: 'text-white' },
  hotdeal:    { label: '핫딜',   color: 'bg-red-500',    text: 'text-white' },
  oliveyoung: { label: '올영',   color: 'bg-violet-500', text: 'text-white' },
  daiso:      { label: '다이소', color: 'bg-yellow-400', text: 'text-gray-900' },
}

const STORE_LABELS = {
  gs25: 'GS25', cu: 'CU', seven: '7-ELEVEn', emart24: '이마트24',
}

export default function FeedCard({ item }) {
  const { title, body, source, store, category, keyword, image_url, url } = item
  const cfg = SOURCE_CONFIG[source] || { label: source, color: 'bg-gray-400', text: 'text-white' }

  const handleClick = () => {
    if (url) window.open(url, '_blank', 'noopener,noreferrer')
  }

  return (
    <div
      className={`bg-white rounded-2xl border border-gray-100 shadow-sm mb-3 overflow-hidden active:scale-[0.98] transition-transform ${url ? 'cursor-pointer' : ''}`}
      onClick={url ? handleClick : undefined}
    >
      <div className="flex gap-3 p-4">
        {/* 왼쪽: 텍스트 */}
        <div className="flex-1 min-w-0">
          {/* 키워드 태그 */}
          {keyword && (
            <span className={`inline-block ${cfg.color} ${cfg.text} text-xs font-bold px-2 py-0.5 rounded-full mb-2`}>
              {keyword}
            </span>
          )}

          {/* 제목 */}
          <h3 className="font-bold text-[15px] leading-snug text-gray-900 mb-1.5">
            {title}
          </h3>

          {/* 본문 */}
          <p className="text-[13px] text-gray-400 leading-relaxed whitespace-pre-line">
            {body}
          </p>

          {/* 하단 배지 */}
          <div className="flex items-center gap-1.5 mt-2.5">
            <span className={`text-[11px] font-semibold px-2 py-0.5 rounded-full ${cfg.color} ${cfg.text}`}>
              {cfg.label}
            </span>
            {store && STORE_LABELS[store] && (
              <span className="text-[11px] text-gray-500 bg-gray-100 px-2 py-0.5 rounded-full font-medium">
                {STORE_LABELS[store]}
              </span>
            )}
            {category && (
              <span className="text-[11px] text-gray-400 bg-gray-50 px-2 py-0.5 rounded-full">
                {category}
              </span>
            )}
          </div>
        </div>

        {/* 오른쪽: 이미지 + 공유 */}
        <div className="flex flex-col items-end gap-2 flex-shrink-0">
          <ShareButton title={title} text={`${title}\n${body}`} />
          {image_url && (
            <img
              src={image_url}
              alt={title}
              loading="lazy"
              referrerPolicy="no-referrer"
              className="w-[72px] h-[72px] rounded-xl object-cover bg-gray-100 mt-1"
              onError={(e) => { e.target.style.display = 'none' }}
            />
          )}
        </div>
      </div>
    </div>
  )
}
