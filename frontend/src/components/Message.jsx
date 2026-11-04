import { Link } from 'react-router-dom';
import { RotateCw, ThumbsDown, ThumbsUp } from 'lucide-react';
import { useState } from 'react';
import AnswerText from './AnswerText.jsx';

export const NOT_FOUND_TEXT = 'Nothing in the selected documents answers this.';

function Stage({ stage }) {
  const text = { searching: 'Searching documents', reranking: 'Reranking', writing: 'Writing answer' }[stage] || 'Starting';
  return <p className="stage">{text}</p>;
}

export default function Message({
  message, focused, activeId, onFocus, onCite, onHover, onRetry, onOpenScope, onRephrase, onFeedback,
}) {
  const [feedback, setFeedback] = useState(message.feedback || null);
  const [feedbackBusy, setFeedbackBusy] = useState(false);
  if (message.role === 'user') {
    return (
      <article className="turn turn--user" aria-label="Question">
        <span className="turn__who" aria-hidden="true">You</span>
        <p className="turn__q">{message.content}</p>
      </article>
    );
  }

  const notFound = Boolean(message.meta?.not_found);
  const count = message.citations.length;
  const busy = message.status === 'streaming';

  return (
    <article
      className="turn turn--answer"
      aria-label="Answer"
      aria-busy={busy}
      data-focused={focused || undefined}
      onFocus={onFocus}
      onClick={onFocus}
    >
      <span className="turn__who" aria-hidden="true">Answer</span>
      <div className="turn__body">
        {busy ? <Stage stage={message.stage} /> : null}
        {busy && !message.content ? (
          <div className="skeleton-block" aria-hidden="true">
            <span className="skeleton" data-w="92" />
            <span className="skeleton" data-w="78" />
            <span className="skeleton" data-w="40" />
          </div>
        ) : null}

        {notFound ? (
          <div className="notfound">
            <p className="notfound__title">{NOT_FOUND_TEXT}</p>
            <ul>
              <li><button type="button" className="link-button" onClick={onOpenScope}>Include more documents</button> in the scope.</li>
              <li><button type="button" className="link-button" onClick={() => onRephrase(message)}>Rephrase</button> the question with terms the documents use.</li>
            </ul>
          </div>
        ) : message.content ? (
          <AnswerText text={message.content} citations={message.citations} activeId={activeId} onSelect={onCite} onHover={onHover} />
        ) : null}

        {message.status === 'stopped' ? (
          <p className="turn__note">{message.content ? 'Stopped. The answer above is incomplete.' : 'Stopped before an answer was written.'}</p>
        ) : null}
        {message.status === 'error' ? (
          <div className="turn__error" role="alert">
            <p>{message.error}</p>
            <button type="button" className="btn btn--sm" onClick={() => onRetry(message)}>
              <RotateCw size={16} strokeWidth={1.5} aria-hidden="true" />
              Retry
            </button>
          </div>
        ) : null}

        {!busy ? (
          <footer className="turn__meta">
            {message.meta?.cached ? <span className="tag">cached</span> : null}
            {message.id ? <span className="turn__feedback" aria-label="Rate this answer">
              <button type="button" className="icon-btn" aria-label="Helpful answer" aria-pressed={feedback === 'helpful'} disabled={feedbackBusy} onClick={async () => { setFeedbackBusy(true); try { const ok = await onFeedback?.(message.id, 'helpful'); if (ok !== false) setFeedback('helpful'); } catch {} finally { setFeedbackBusy(false); } }}><ThumbsUp size={15}/></button>
              <button type="button" className="icon-btn" aria-label="Not helpful answer" aria-pressed={feedback === 'not_helpful'} disabled={feedbackBusy} onClick={async () => { setFeedbackBusy(true); try { const ok = await onFeedback?.(message.id, 'not_helpful'); if (ok !== false) setFeedback('not_helpful'); } catch {} finally { setFeedbackBusy(false); } }}><ThumbsDown size={15}/></button>
            </span> : null}
            {count > 0 || message.meta ? (
              <button type="button" className="link-button" onClick={(event) => { event.stopPropagation(); onCite(null); }}>
                {count > 0 ? `View sources (${count})` : 'View trace'}
              </button>
            ) : null}
          </footer>
        ) : null}
      </div>
    </article>
  );
}

export function EmptyChat({ docsStatus, readyCount, totalCount, onAsk, onLoadSamples, sampling }) {
  if (docsStatus === 'loading') {
    return (
      <div className="chat-empty" aria-hidden="true">
        <span className="skeleton" data-w="50" />
        <span className="skeleton" data-w="80" />
      </div>
    );
  }
  if (totalCount === 0) {
    return (
      <div className="chat-empty">
        <h2>Add documents to start</h2>
        <p>Chat answers only from your own files. Upload some on the <Link to="/documents">Documents page</Link>, or try the bundled examples.</p>
        <button type="button" className="btn" disabled={sampling} onClick={onLoadSamples}>
          {sampling ? 'Loading samples' : 'Load sample documents'}
        </button>
      </div>
    );
  }
  if (readyCount === 0) {
    return (
      <div className="chat-empty">
        <h2>Documents are still indexing</h2>
        <p>You can ask once at least one document shows Ready on the <Link to="/documents">Documents page</Link>.</p>
      </div>
    );
  }
  return (
    <div className="chat-empty">
      <h2>Ask across {readyCount} {readyCount === 1 ? 'document' : 'documents'}</h2>
      <p>
        Answers cite the passage they came from and appear with their sources beside them.
        Narrow the search with Scope under the input; with nothing checked, every ready document is searched.
      </p>
      <ul className="examples">
        {onAsk.questions.map((q) => (
          <li key={q}>
            <button type="button" className="example-btn" onClick={() => onAsk.ask(q)}>{q}</button>
          </li>
        ))}
      </ul>
    </div>
  );
}
