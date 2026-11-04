import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowUpRight, Clock3, Search, X } from 'lucide-react';
import { api } from '../api/client.js';

export default function ChatSearch({ open, onClose }) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [active, setActive] = useState(0);
  const input = useRef(null);
  const navigate = useNavigate();

  useEffect(() => {
    if (!open) return undefined;
    setQuery(''); setResults([]); setError(''); setActive(0);
    const id = requestAnimationFrame(() => input.current?.focus());
    return () => cancelAnimationFrame(id);
  }, [open]);

  useEffect(() => {
    if (!open || !query.trim()) { setResults([]); setBusy(false); return undefined; }
    const controller = new AbortController();
    const timer = setTimeout(async () => {
      setBusy(true); setError('');
      try { setResults(await api.searchSessions(query.trim(), controller.signal)); setActive(0); }
      catch (err) { if (err.name !== 'AbortError') setError(err.message); }
      finally { if (!controller.signal.aborted) setBusy(false); }
    }, 180);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [open, query]);

  useEffect(() => {
    if (!open) return undefined;
    const key = (event) => {
      if (event.key === 'Escape') { event.preventDefault(); onClose(); }
      if (event.key === 'ArrowDown') { event.preventDefault(); setActive((v) => Math.min(v + 1, results.length - 1)); }
      if (event.key === 'ArrowUp') { event.preventDefault(); setActive((v) => Math.max(v - 1, 0)); }
      if (event.key === 'Enter' && results[active]) { event.preventDefault(); navigate(`/chat/${results[active].session_id}`); onClose(); }
    };
    window.addEventListener('keydown', key);
    return () => window.removeEventListener('keydown', key);
  }, [open, results, active, navigate, onClose]);

  if (!open) return null;
  return (
    <div className="chat-search__backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <section className="chat-search" role="dialog" aria-modal="true" aria-label="Search conversations">
        <div className="chat-search__input-wrap">
          <Search size={19} aria-hidden="true" />
          <input ref={input} value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search chats and messages..." aria-label="Search chats and messages" />
          <button className="icon-btn" type="button" aria-label="Close search" onClick={onClose}><X size={17}/></button>
        </div>
        <div className="chat-search__results" role="listbox" aria-label="Search results">
          {!query.trim() ? <p className="chat-search__hint">Search conversation titles and message contents.</p> : null}
          {busy ? <p className="chat-search__hint">Searching conversations…</p> : null}
          {error ? <p className="field-error">{error}</p> : null}
          {!busy && query.trim() && !error && results.length === 0 ? <p className="chat-search__hint">No matching conversations found.</p> : null}
          {results.map((result, index) => (
            <button key={result.session_id} type="button" role="option" aria-selected={active === index} className="chat-search__result" onMouseEnter={() => setActive(index)} onClick={() => { navigate(`/chat/${result.session_id}`); onClose(); }}>
              <span className="chat-search__result-icon"><Clock3 size={16}/></span>
              <span className="chat-search__result-copy"><strong>{result.title}</strong><span>{result.excerpt}</span></span>
              <ArrowUpRight size={15} aria-hidden="true"/>
            </button>
          ))}
        </div>
        <footer className="chat-search__footer"><span>↑↓ Navigate</span><span>Enter Open</span><span>Esc Close</span></footer>
      </section>
    </div>
  );
}
