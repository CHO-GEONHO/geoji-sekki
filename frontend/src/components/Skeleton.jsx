export function FeedCardSkeleton() {
  return (
    <div className="card mb-3">
      <div className="skeleton h-5 w-3/4 mb-2" />
      <div className="skeleton h-4 w-full mb-1" />
      <div className="skeleton h-4 w-2/3 mb-3" />
      <div className="flex gap-2">
        <div className="skeleton h-5 w-14 rounded-full" />
        <div className="skeleton h-5 w-10 rounded-full" />
      </div>
    </div>
  )
}

export function ProductCardSkeleton() {
  return (
    <div className="card mb-2 flex gap-3">
      <div className="skeleton w-16 h-16 rounded-lg flex-shrink-0" />
      <div className="flex-1">
        <div className="skeleton h-4 w-3/4 mb-2" />
        <div className="skeleton h-5 w-1/3 mb-2" />
        <div className="flex gap-2">
          <div className="skeleton h-5 w-10 rounded-full" />
          <div className="skeleton h-5 w-12 rounded-full" />
        </div>
      </div>
    </div>
  )
}

export function SkeletonList({ count = 5, type = 'feed' }) {
  const Component = type === 'feed' ? FeedCardSkeleton : ProductCardSkeleton
  return (
    <>
      {Array.from({ length: count }, (_, i) => (
        <Component key={i} />
      ))}
    </>
  )
}
