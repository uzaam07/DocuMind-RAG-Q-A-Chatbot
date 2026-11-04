import EvidenceEntry from './EvidenceEntry.jsx';
import RetrievalTrace from './RetrievalTrace.jsx';

function Skeleton() {
  return (
    <ul className="entries" aria-hidden="true">
      {[0, 1, 2].map((i) => (
        <li key={i} className="entry entry--skeleton">
          <span className="skeleton" data-w="40" />
          <span className="skeleton" data-w="90" />
          <span className="skeleton" data-w="70" />
        </li>
      ))}
    </ul>
  );
}

/** Sources and retrieval trace for one assistant message. */
export default function EvidencePanel({ message, activeId, onActive, reveal }) {
  if (!message) {
    return (
      <div className="panel-empty">
        <p>Sources for an answer appear here, next to its retrieval trace.</p>
        <p className="muted">Select a citation number in an answer, or ask a question.</p>
      </div>
    );
  }

  const waiting = message.status === 'streaming' && message.citations.length === 0;
  const notFound = message.meta?.not_found;

  return (
    <div className="panel-body">
      {waiting ? <Skeleton /> : null}
      {!waiting && message.citations.length > 0 ? (
        <ol className="entries" aria-label="Retrieved passages">
          {message.citations.map((citation, index) => (
            <EvidenceEntry
              key={citation.id}
              domId={`ev-${message.key}-${citation.id}`}
              citation={citation}
              active={activeId === citation.id}
              reveal={reveal}
              order={index}
              onActive={onActive}
            />
          ))}
        </ol>
      ) : null}
      {!waiting && message.citations.length === 0 ? (
        <p className="panel-note">
          {notFound
            ? 'No retrieved passage was relevant enough to cite. The trace below shows what the search did.'
            : message.status === 'streaming'
              ? 'No passages retrieved yet.'
              : 'This answer has no sources.'}
        </p>
      ) : null}
      {message.meta ? (
        <RetrievalTrace meta={message.meta} />
      ) : message.status === 'streaming' ? (
        <p className="panel-note">The retrieval trace appears when the answer finishes.</p>
      ) : null}
    </div>
  );
}
