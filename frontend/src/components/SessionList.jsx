import { useEffect, useRef, useState } from 'react';
import { NavLink, useMatch, useNavigate } from 'react-router-dom';
import { Pencil, Plus, Search, Trash2 } from 'lucide-react';
import ChatSearch from './ChatSearch.jsx';
import { useSessions } from '../state/sessions.jsx';

function RenameField({ session, onDone }) {
  const { rename } = useSessions();
  const [value, setValue] = useState(session.title);
  const [error, setError] = useState(null);
  const settled = useRef(false);
  const inputRef = useRef(null);

  useEffect(() => {
    inputRef.current?.focus();
    inputRef.current?.select();
  }, []);

  const commit = async () => {
    if (settled.current) return;
    const title = value.trim();
    if (!title || title === session.title) {
      settled.current = true;
      onDone();
      return;
    }
    try {
      await rename(session.id, title);
      settled.current = true;
      onDone();
    } catch (err) {
      setError(err.message);
      inputRef.current?.focus();
    }
  };

  return (
    <div className="session__edit">
      <label className="sr-only" htmlFor={`rename-${session.id}`}>Chat title</label>
      <input
        id={`rename-${session.id}`}
        ref={inputRef}
        className="input input--sm"
        value={value}
        maxLength={120}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? `rename-err-${session.id}` : undefined}
        onChange={(event) => setValue(event.target.value)}
        onBlur={commit}
        onKeyDown={(event) => {
          if (event.key === 'Enter') {
            event.preventDefault();
            commit();
          } else if (event.key === 'Escape') {
            event.preventDefault();
            event.stopPropagation();
            settled.current = true;
            onDone();
          }
        }}
      />
      {error ? <p id={`rename-err-${session.id}`} className="field-error">{error}</p> : null}
    </div>
  );
}

function DeleteConfirm({ session, onDone }) {
  const { remove } = useSessions();
  const sessionId = useMatch('/chat/:sessionId')?.params.sessionId;
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const cancelRef = useRef(null);

  useEffect(() => {
    cancelRef.current?.focus();
  }, []);

  const confirm = async () => {
    setBusy(true);
    try {
      await remove(session.id);
      if (sessionId === session.id) navigate('/chat');
      onDone();
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  };

  return (
    <div className="session__confirm" role="group" aria-label={`Confirm deleting ${session.title}`}>
      <p>Delete this chat and its messages?</p>
      <div className="session__confirm-actions">
        <button type="button" className="btn btn--danger btn--sm" disabled={busy} onClick={confirm}>Delete</button>
        <button type="button" ref={cancelRef} className="btn btn--sm" disabled={busy} onClick={onDone}>Cancel</button>
      </div>
      {error ? <p className="field-error">{error}</p> : null}
    </div>
  );
}

function SessionItem({ session, onNavigate }) {
  const [mode, setMode] = useState('view');
  if (mode === 'rename') return <li className="session"><RenameField session={session} onDone={() => setMode('view')} /></li>;
  if (mode === 'delete') return <li className="session"><DeleteConfirm session={session} onDone={() => setMode('view')} /></li>;
  return (
    <li className="session">
      <NavLink to={`/chat/${session.id}`} className="session__link" title={session.title} onClick={onNavigate}>
        <span className="session__title">{session.title}</span>
      </NavLink>
      <span className="session__actions">
        <button type="button" className="icon-btn" aria-label={`Rename ${session.title}`} onClick={() => setMode('rename')}>
          <Pencil size={16} strokeWidth={1.5} aria-hidden="true" />
        </button>
        <button type="button" className="icon-btn" aria-label={`Delete ${session.title}`} onClick={() => setMode('delete')}>
          <Trash2 size={16} strokeWidth={1.5} aria-hidden="true" />
        </button>
      </span>
    </li>
  );
}

export default function SessionList({ onNavigate }) {
  const { sessions, status, error, refresh } = useSessions();
  const [searchOpen, setSearchOpen] = useState(false);
  useEffect(() => {
    const handler = (event) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') { event.preventDefault(); setSearchOpen(true); }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);
  return (
    <section className="sessions" aria-labelledby="sessions-title">
      <div className="sessions__head">
        <h2 id="sessions-title">Chats</h2>
        <div className="sessions__head-actions">
        <button type="button" className="icon-btn" aria-label="Search chats" title="Search chats (Ctrl K)" onClick={() => setSearchOpen(true)}><Search size={16} strokeWidth={1.5} aria-hidden="true" /></button>
        <NavLink to="/chat" end className="icon-btn" aria-label="New chat" onClick={onNavigate}>
          <Plus size={16} strokeWidth={1.5} aria-hidden="true" />
        </NavLink>
        </div>
      </div>
      {status === 'loading' ? (
        <ul className="sessions__list" aria-hidden="true">
          {[70, 85, 55, 78].map((w, i) => (
            <li key={i} className="session"><span className="skeleton" data-w={w} /></li>
          ))}
        </ul>
      ) : null}
      {status === 'error' ? (
        <div className="sessions__error">
          <p className="field-error">{error}</p>
          <button type="button" className="link-button" onClick={refresh}>Reload chats</button>
        </div>
      ) : null}
      {status === 'ready' && sessions.length === 0 ? (
        <p className="sessions__empty">No chats yet. Ask a question to start one.</p>
      ) : null}
      {status === 'ready' && sessions.length > 0 ? (
        <ul className="sessions__list">
          {sessions.map((session) => (
            <SessionItem key={session.id} session={session} onNavigate={onNavigate} />
          ))}
        </ul>
      ) : null}
      <ChatSearch open={searchOpen} onClose={() => setSearchOpen(false)} />
    </section>
  );
}
