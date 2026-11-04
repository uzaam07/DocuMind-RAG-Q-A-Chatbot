import { useState } from 'react';
import CitationMarker from './CitationMarker.jsx';

const SOURCES = [
  { id: 1, filename: 'employee-handbook.pdf', page_or_section: 'Page 4', score: 0.91, snippet: 'Full-time employees accrue 20 days of paid annual leave per calendar year, prorated from the start date.' },
  { id: 2, filename: 'employee-handbook.pdf', page_or_section: 'Section: Carry-over', score: 0.84, snippet: 'Up to 5 unused days carry over into the next year and expire on 31 March.' },
];

/** A static, clearly labelled sample so a first-time visitor sees the product's shape. */
export default function ExampleExchange() {
  const [activeId, setActiveId] = useState(null);
  const marker = (index) => (
    <CitationMarker citation={SOURCES[index]} active={activeId === SOURCES[index].id} onSelect={setActiveId} onHover={setActiveId} />
  );
  return (
    <figure className="example">
      <figcaption>Example exchange, not your data</figcaption>
      <p className="example__q">How much annual leave do new full-time employees get?</p>
      <p className="example__a">
        Full-time employees accrue 20 days of paid annual leave per year, prorated from the start date {marker(0)}.
        Up to 5 unused days carry over and expire on 31 March {marker(1)}.
      </p>
      <ul className="example__sources">
        {SOURCES.map((source) => (
          <li key={source.id} data-active={activeId === source.id || undefined}>
            <span className="cite-index" aria-hidden="true">{source.id}</span>
            <span className="example__file">{source.filename}</span>
            <span className="example__loc">{source.page_or_section}</span>
            <span className="num">{source.score.toFixed(2)}</span>
          </li>
        ))}
      </ul>
    </figure>
  );
}
