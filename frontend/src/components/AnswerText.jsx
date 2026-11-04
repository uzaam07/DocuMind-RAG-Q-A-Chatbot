import { Fragment, useMemo } from 'react';
import { parseAnswer } from '../lib/citations.js';
import CitationMarker from './CitationMarker.jsx';

/** Renders answer text; [n] markers become buttons. Never injects HTML. */
export default function AnswerText({ text, citations, activeId, onSelect, onHover }) {
  const paragraphs = useMemo(() => parseAnswer(text), [text]);
  const byId = useMemo(() => new Map(citations.map((c) => [c.id, c])), [citations]);
  return (
    <div className="answer">
      {paragraphs.map((segments, p) => (
        <p key={p}>
          {segments.map((segment, s) => {
            if (segment.type === 'text') return <Fragment key={s}>{segment.value}</Fragment>;
            if (!segment.ids.every((id) => byId.has(id))) return <Fragment key={s}>{segment.raw}</Fragment>;
            return (
              <Fragment key={s}>
                {segment.ids.map((id) => (
                  <CitationMarker
                    key={id}
                    citation={byId.get(id)}
                    active={activeId === id}
                    onSelect={onSelect}
                    onHover={onHover}
                  />
                ))}
              </Fragment>
            );
          })}
        </p>
      ))}
    </div>
  );
}
