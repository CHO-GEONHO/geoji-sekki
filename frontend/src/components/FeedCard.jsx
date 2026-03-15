import ShareButton from './ShareButton'

const SOURCE_CONFIG = {
  cvs:        { label: '편의점', color: 'bg-blue-500',   text: 'text-white',      accent: 'border-blue-200 bg-blue-50' },
  hotdeal:    { label: '핫딜',   color: 'bg-red-500',    text: 'text-white',      accent: 'border-red-200 bg-red-50' },
  oliveyoung: { label: '올영',   color: 'bg-violet-500', text: 'text-white',      accent: 'border-violet-200 bg-violet-50' },
  daiso:      { label: '다이소', color: 'bg-yellow-400', text: 'text-gray-900',   accent: 'border-yellow-200 bg-yellow-50' },
}

const STORE_LABELS = {
  gs25: 'GS25', cu: 'CU', seven: '7-ELEVEn', emart24: '이마트24',
}

export default function FeedCard({ item }) {
  const { title, body, source, store, category, keyword, image_url, url } = item
  const cfg = SOURCE_CONFIG[source] || { label: source, color: 'bg-gray-400', text: 'text-white', accent: 'border-gray-200 bg-gray-50' }

  const handleClick = () => {
    if (url) window.open(url, '_blank', 'noopener,noreferrer')
  }

  return (
    <div
      className={`bg-white rounded-2xl border border-gray-100 shadow-sm mb-3 overflow-hidden active:scale-[0.98] transition-transform ${url ? 'cursor-pointer' : ''}`}
      onClick={url ? handleClick : undefined}
    >
      {/* 키워드 배너 (있는 경우만) */}
      {keyword && (
        <div className={`px-4 py-2 border-b ${cfg.accent} flex items-center justify-between`}>
          <span className="text-[12px] font-black tracking-wide text-gray-800">
            💬 {keyword}
          </span>
          <ShareButton title={title} text={`${keyword}\n${title}\n${body}`} />
        </div>
      )}

      <div className="flex gap-3 p-4">
        {/* 왼쪽: 텍스트 */}
        <div className="flex-1 min-w-0">
          {/* 제목 */}
          <h3 className="font-bold text-[15px] leading-snug text-gray-900 mb-1.5">
            {title}
          </h3>

          {/* 본문 */}
          <p className="text-[13px] text-gray-400 leading-relaxed whitespace-pre-line">
            {body}
          </p>

          {/* 하단 배지 */}
          <div className="flex items-center gap-1.5 mt-3">
            <span className={`text-[11px] font-bold px-2.5 py-1 rounded-full ${cfg.color} ${cfg.text}`}>
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
            {url && (
              <span className="text-[11px] text-gray-300 ml-auto">→ 보러가기</span>
            )}
          </div>
        </div>

        {/* 오른쪽: 이미지 */}
        {image_url && (
          <div className="flex-shrink-0">
            {!keyword && (
              <div className="mb-2 flex justify-end">
                <ShareButton title={title} text={`${title}\n${body}`} />
              </div>
            )}
            <img
              src={image_url}
              alt={title}
              loading="lazy"
              referrerPolicy="no-referrer"
              className="w-[80px] h-[80px] rounded-xl object-cover bg-gray-100"
              onError={(e) => { e.target.style.display = 'none' }}
            />
          </div>
        )}
        {!image_url && !keyword && (
          <div className="flex-shrink-0">
            <ShareButton title={title} text={`${title}\n${body}`} />
          </div>
        )}
      </div>
    </div>
  )
}
