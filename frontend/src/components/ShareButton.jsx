import { Share2 } from 'lucide-react'

export default function ShareButton({ title, text, url }) {
  const handleShare = async () => {
    const shareData = {
      title: title || '거지세끼',
      text: text || '',
      url: url || window.location.href,
    }

    if (navigator.share) {
      try {
        await navigator.share(shareData)
      } catch {
        // 사용자가 공유 취소
      }
    } else {
      // Fallback: 클립보드 복사
      try {
        await navigator.clipboard.writeText(`${shareData.title}\n${shareData.text}\n${shareData.url}`)
        alert('클립보드에 복사됨!')
      } catch {
        // noop
      }
    }
  }

  return (
    <button
      onClick={handleShare}
      className="p-1.5 rounded-full text-gray-400 hover:text-geoji-600 hover:bg-geoji-50 transition-colors flex-shrink-0"
      aria-label="공유"
    >
      <Share2 size={16} />
    </button>
  )
}
