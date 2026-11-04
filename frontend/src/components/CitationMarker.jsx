import { lowerFirst } from '../lib/format.js';

export default function CitationMarker({ citation, active, onSelect, onHover }) {
  const label = `Source ${citation.id}: ${citation.filename}, ${lowerFirst(citation.page_or_section)}`;
  return (
    <button
      type="button"
      className="cite"
      data-active={active || undefined}
      aria-label={label}
      onClick={() => onSelect(citation.id)}
      onPointerEnter={() => onHover(citation.id)}
      onPointerLeave={() => onHover(null)}
      onFocus={() => onHover(citation.id)}
      onBlur={() => onHover(null)}
    >
      {citation.id}
    </button>
  );
}
