import StoreTag from './StoreTag'

const EVENT_BADGES = {
  '1+1': { class: 'badge-1plus1', label: '1+1' },
  '2+1': { class: 'badge-2plus1', label: '2+1' },
  '3+1': { class: 'bg-amber-100 text-amber-700', label: '3+1' },
  'discount': { class: 'badge-discount', label: '할인' },
  'bonus': { class: 'bg-teal-100 text-teal-700', label: '덤증정' },
  'sale': { class: 'badge-discount', label: '세일' },
  'pick_special': { class: 'bg-pink-100 text-pink-700', label: '올영픽' },
  '1+1_oy': { class: 'badge-1plus1', label: '1+1' },
  'limited': { class: 'bg-violet-100 text-violet-700', label: '한정' },
}

export default function ProductCard({ product, type = 'cvs' }) {
  const badge = EVENT_BADGES[product.event_type] || EVENT_BADGES['discount']

  const handleClick = () => {
    if (product.url) window.open(product.url, '_blank', 'noopener,noreferrer')
  }

  return (
    <div
      className={`card mb-2 flex gap-3 active:scale-[0.98] transition-transform ${product.url ? 'cursor-pointer' : ''}`}
      onClick={product.url ? handleClick : undefined}
    >
      {/* 이미지 */}
      {product.image_url && (
        <img
          src={product.image_url}
          alt={product.name}
          loading="lazy"
          referrerPolicy="no-referrer"
          className="w-16 h-16 rounded-lg object-cover flex-shrink-0 bg-gray-100"
          onError={(e) => { e.target.style.display = 'none' }}
        />
      )}

      {/* 정보 */}
      <div className="flex-1 min-w-0">
        <h4 className="font-semibold text-sm truncate">{product.name}</h4>

        <div className="flex items-center gap-2 mt-1">
          {/* 가격 */}
          {type === 'cvs' && (
            <>
              <span className="text-base font-bold text-geoji-600">
                {product.unit_price?.toLocaleString() || product.price?.toLocaleString()}원
              </span>
              {product.unit_price && product.unit_price !== product.price && (
                <span className="text-xs text-gray-400 line-through">
                  {product.price?.toLocaleString()}원
                </span>
              )}
            </>
          )}

          {type === 'oliveyoung' && (
            <>
              <span className="text-base font-bold text-geoji-600">
                {product.sale_price?.toLocaleString()}원
              </span>
              {product.original_price && (
                <span className="text-xs text-gray-400 line-through">
                  {product.original_price?.toLocaleString()}원
                </span>
              )}
              {product.discount_rate && (
                <span className="text-xs font-bold text-red-500">
                  -{product.discount_rate}%
                </span>
              )}
            </>
          )}

          {type === 'daiso' && (
            <>
              <span className="text-base font-bold text-geoji-600">
                {product.price?.toLocaleString()}원
              </span>
              {product.ai_score && (
                <span className="text-xs text-amber-600 font-medium">
                  ★ {product.ai_score.toFixed(1)}
                </span>
              )}
            </>
          )}
        </div>

        {/* 태그 */}
        <div className="flex items-center gap-1.5 mt-1.5">
          <span className={`badge ${badge.class}`}>{badge.label}</span>
          {product.store && <StoreTag store={product.store} />}
          {product.brand && (
            <span className="text-xs text-gray-400">{product.brand}</span>
          )}
        </div>

        {/* 다이소 AI 코멘트 */}
        {type === 'daiso' && product.ai_comment && (
          <p className="text-xs text-gray-500 mt-1">💬 {product.ai_comment}</p>
        )}
      </div>
    </div>
  )
}
