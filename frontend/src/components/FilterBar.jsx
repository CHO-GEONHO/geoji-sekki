export default function FilterBar({ filters, active, onSelect, label = '필터' }) {
  return (
    <div className="flex gap-2 overflow-x-auto pb-2 scrollbar-hide">
      <button
        onClick={() => onSelect(null)}
        className={`filter-chip whitespace-nowrap ${
          !active ? 'filter-chip-active' : 'filter-chip-inactive'
        }`}
      >
        전체
      </button>
      {filters.map((f) => (
        <button
          key={f}
          onClick={() => onSelect(f === active ? null : f)}
          className={`filter-chip whitespace-nowrap ${
            active === f ? 'filter-chip-active' : 'filter-chip-inactive'
          }`}
        >
          {f}
        </button>
      ))}
    </div>
  )
}
