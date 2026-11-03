export function CardSkeletonGrid({ count = 8 }: { count?: number }) {
  return (
    <div className="explore-grid" aria-hidden="true">
      {Array.from({ length: count }, (_, i) => (
        <div key={i} className="card-skeleton">
          <div className="card-skeleton-art" />
          <div className="card-skeleton-line" />
          <div className="card-skeleton-line is-short" />
        </div>
      ))}
    </div>
  );
}
