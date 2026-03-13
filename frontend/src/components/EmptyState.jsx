export default function EmptyState({ message = '데이터가 없어요', emoji = '💸' }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-gray-400">
      <span className="text-5xl mb-4">{emoji}</span>
      <p className="text-sm">{message}</p>
    </div>
  )
}
