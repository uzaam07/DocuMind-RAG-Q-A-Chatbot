import { useMemo, useState } from 'react';
import { EXCERPT_LIMIT, excerptAround, locateHighlight } from '../lib/citations.js';
import { formatScore } from '../lib/format.js';

function Passage({ text, range }) {
  if (!range || range.start >= range.end) return text;
  return (
    <>
      {text.slice(0, range.start)}
      <mark>{text.slice(range.start, range.end)}</mark>
      {text.slice(range.end)}
    </>
  );
}

export default function EvidenceEntry({ domId, citation, active, reveal, order, onActive }) {
  const [expanded, setExpanded] = useState(false);
  const { snippet, highlight, score } = citation;
  const range = useMemo(() => locateHighlight(snippet, highlight), [snippet, highlight]);
  const view = useMemo(
    () => (expanded ? { text: snippet, offset: 0, before: false, after: false } : excerptAround(snippet, range)),
    [expanded, snippet, range],
  );
  const shifted = range ? { start: range.start - view.offset, end: range.end - view.offset } : null;
  const visibleRange = shifted && shifted.start >= 0 && shifted.end <= view.text.length ? shifted : null;
  const long = snippet.length > EXCERPT_LIMIT;
  const meter = Math.max(0, Math.min(1, Number.isFinite(score) ? score : 0));

  return (
    <li
      id={domId}
      className="entry"
      data-active={active || undefined}
      data-reveal={reveal || undefined}
      style={{ '--order': order }}
      onPointerEnter={() => onActive(citation.id)}
      onPointerLeave={() => onActive(null)}
      onFocus={() => onActive(citation.id)}
      onBlur={() => onActive(null)}
    >
      <div className="entry__head">
        <span className="cite-index" aria-hidden="true">{citation.id}</span>
        <span className="entry__file" title={citation.filename}>{citation.filename}</span>
      </div>
      <p className="entry__loc">{citation.page_or_section}</p>
      <div className="entry__score">
        <span className="entry__label">Relevance</span>
        <span className="num">{formatScore(score)}</span>
        <span className="meter" aria-hidden="true"><span style={{ '--v': meter }} /></span>
      </div>
      <blockquote className="entry__passage">
        {view.before ? <span className="entry__gap">… </span> : null}
        <Passage text={view.text} range={visibleRange} />
        {view.after ? <span className="entry__gap"> …</span> : null}
      </blockquote>
      {long ? (
        <button type="button" className="link-button" aria-expanded={expanded} onClick={() => setExpanded((v) => !v)}>
          {expanded ? 'Show less' : 'Show full passage'}
        </button>
      ) : null}
    </li>
  );
}
