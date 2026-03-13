const STORE_CONFIG = {
  gs25: { label: 'GS25', color: 'bg-sky-100 text-sky-700' },
  cu: { label: 'CU', color: 'bg-purple-100 text-purple-700' },
  seven: { label: '세븐', color: 'bg-emerald-100 text-emerald-700' },
  emart24: { label: '이마트24', color: 'bg-yellow-100 text-yellow-700' },
}

export default function StoreTag({ store }) {
  const config = STORE_CONFIG[store] || { label: store, color: 'badge-store' }

  return (
    <span className={`badge ${config.color}`}>{config.label}</span>
  )
}
