export default function TableSkeleton({ rows = 5 }) {
  return (
    <div className="doctable-wrap" aria-hidden="true">
      <ul className="table-skeleton">
        {Array.from({ length: rows }, (_, i) => (
          <li key={i}>
            <span className="skeleton" data-w={[55, 70, 45, 62, 50][i % 5]} />
            <span className="skeleton" data-w="30" />
          </li>
        ))}
      </ul>
    </div>
  );
}
