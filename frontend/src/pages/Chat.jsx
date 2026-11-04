import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { ArrowDown, Download, PanelRightClose, PanelRightOpen, X } from 'lucide-react';
import Composer from '../components/Composer.jsx';
import EvidencePanel from '../components/EvidencePanel.jsx';
import Message, { EmptyChat } from '../components/Message.jsx';
import ModalDialog from '../components/ModalDialog.jsx';
import ScopePicker from '../components/ScopePicker.jsx';
import { EXAMPLE_QUESTIONS } from '../lib/examples.js';
import { readStore, writeStore } from '../lib/storage.js';
import { api } from '../api/client.js';
import { useConversation } from '../state/useConversation.js';
import { useDocuments } from '../state/useDocuments.js';
import { prefersReducedMotion, useMedia } from '../state/useMedia.js';
import { useScope } from '../state/scope.jsx';
import { useSessions } from '../state/sessions.jsx';
import { useTitle } from '../state/useTitle.js';

const MODE_KEY = 'documind.mode';
const PANEL_KEY = 'documind.panel';
const MODE_VALUES = ['vector', 'hybrid', 'hybrid_rerank'];
const NEAR_BOTTOM_PX = 56;

function initialMode() {
  const saved = readStore('local', MODE_KEY);
  return MODE_VALUES.includes(saved) ? saved : 'hybrid_rerank';
}

function isTyping(target) {
  return target instanceof HTMLElement && (target.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName));
}

export default function Chat() {
  const { sessionId } = useParams();
  const navigate = useNavigate();
  const sessions = useSessions();
  const scope = useScope();
  const { docs, status: docsStatus, loadSamples, upload } = useDocuments();
  const conv = useConversation(sessionId, { onFinished: sessions.refresh });
  const wide = useMedia('(min-width: 1101px)');

  const [draft, setDraft] = useState('');
  const [mode, setMode] = useState(initialMode);
  const [scopeOpen, setScopeOpen] = useState(false);
  const [focusKey, setFocusKey] = useState(null);
  const [activeId, setActiveId] = useState(null);
  const [sheetOpen, setSheetOpen] = useState(false);
  const [panelOpen, setPanelOpen] = useState(() => readStore('local', PANEL_KEY) !== 'closed');
  const [scrollReq, setScrollReq] = useState(null);
  const [showJump, setShowJump] = useState(false);
  const [notice, setNotice] = useState(null);
  const [sampling, setSampling] = useState(false);
  const scroller = useRef(null);
  const composerInput = useRef(null);
  const stick = useRef(true);

  const session = sessions.sessions.find((s) => s.id === sessionId);
  useTitle(session ? session.title : 'Chat');

  const ready = useMemo(() => docs.filter((d) => d.status === 'ready'), [docs]);
  const selected = useMemo(() => new Set(scope.ids), [scope.ids]);
  const scopedIds = useMemo(() => ready.filter((d) => selected.has(d.id)).map((d) => d.id), [ready, selected]);
  const scopeCount = scopedIds.length || ready.length;
  const selectedProcessing = docs.some((doc) => selected.has(doc.id) && doc.status === 'processing');
  const selectedUnavailable = scope.ids.length > 0 && scopedIds.length === 0 && !selectedProcessing;
  const [uploadBusy, setUploadBusy] = useState(false);

  const { messages } = conv;
  const answers = messages.filter((m) => m.role === 'assistant');
  const focused = answers.find((m) => m.key === focusKey) || answers[answers.length - 1] || null;

  /* Keep the transcript anchored to the bottom unless the reader scrolled up. */
  useLayoutEffect(() => {
    const el = scroller.current;
    if (el && stick.current) el.scrollTop = el.scrollHeight;
  }, [messages]);

  useEffect(() => {
    stick.current = true;
    setFocusKey(null);
    setActiveId(null);
    setSheetOpen(false);
    setShowJump(false);
  }, [sessionId]);

  const onScroll = () => {
    const el = scroller.current;
    const near = el.scrollHeight - el.scrollTop - el.clientHeight < NEAR_BOTTOM_PX;
    stick.current = near;
    setShowJump(!near);
  };

  const jumpToLatest = () => {
    const el = scroller.current;
    stick.current = true;
    el.scrollTo({ top: el.scrollHeight, behavior: prefersReducedMotion() ? 'auto' : 'smooth' });
    setShowJump(false);
  };

  useEffect(() => {
    if (!scrollReq) return;
    const frame = requestAnimationFrame(() => {
      document.getElementById(`ev-${scrollReq.key}-${scrollReq.id}`)?.scrollIntoView({
        block: 'nearest',
        behavior: prefersReducedMotion() ? 'auto' : 'smooth',
      });
    });
    return () => cancelAnimationFrame(frame);
  }, [scrollReq]);

  const cite = useCallback((message, id) => {
    setFocusKey(message.key);
    if (id !== null) {
      setActiveId(id);
      setScrollReq({ key: message.key, id, n: Date.now() });
    }
    if (!wide) setSheetOpen(true);
    else if (!panelOpen) setPanelOpen(true);
  }, [wide, panelOpen]);

  const setPanel = (open) => {
    setPanelOpen(open);
    writeStore('local', PANEL_KEY, open ? 'open' : 'closed');
  };

  const requestDocIds = scope.ids.length > 0 ? scopedIds : null;

  const submit = useCallback(async (text) => {
    const question = text.trim();
    if (!question || conv.streaming) return;
    setNotice(null);
    setDraft('');
    stick.current = true;
    let id = sessionId;
    if (!id) {
      try {
        const created = await sessions.create();
        id = created.id;
        conv.adopt(id);
        navigate(`/chat/${id}`, { replace: true });
      } catch (err) {
        setNotice(err.message);
        setDraft(question);
        return;
      }
    }
    conv.send(id, question, { docIds: requestDocIds, mode });
  }, [conv, sessionId, sessions, navigate, requestDocIds, mode]);
  const retry = (message) => conv.retry(sessionId, message.key, { docIds: requestDocIds, mode });

  const sendFeedback = async (messageId, rating) => {
    try { await api.submitFeedback(messageId, rating); }
    catch (err) { setNotice(err.message); return false; }
  };

  const rephrase = (message) => {
    const index = messages.findIndex((m) => m.key === message.key);
    if (index > 0) setDraft(messages[index - 1].content);
    composerInput.current?.focus();
  };

  const openScope = () => {
    setScopeOpen(true);
    composerInput.current?.focus();
  };

  const changeMode = (value) => {
    setMode(value);
    writeStore('local', MODE_KEY, value);
  };

  const onUploadFiles = async (files) => {
    setUploadBusy(true); setNotice(null);
    try {
      const created = await upload(files);
      const valid = created.filter((doc) => doc.status !== 'failed').map((doc) => doc.id);
      if (valid.length) scope.setMany([...new Set([...scope.ids, ...valid])]);
      const rejected = created.filter((doc) => doc.status === 'failed');
      if (rejected.length) setNotice(rejected.map((doc) => `${doc.filename}: ${doc.error}`).join(' · '));
    } catch (err) { setNotice(err.message); }
    finally { setUploadBusy(false); }
  };

  const exportChat = async () => {
    if (!sessionId) return;
    try {
      const response = await api.exportSession(sessionId);
      const blob = new Blob([response.markdown || ''], { type: 'text/markdown;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a'); anchor.href = url; anchor.download = `${(session?.title || 'conversation').replace(/[^a-z0-9-_]+/gi, '-')}.md`; anchor.click(); URL.revokeObjectURL(url);
    } catch (err) { setNotice(err.message); }
  };

  const onLoadSamples = async () => {
    setSampling(true);
    try {
      await loadSamples();
    } catch (err) {
      setNotice(err.message);
    }
    setSampling(false);
  };

  useEffect(() => {
    const onKey = (event) => {
      if (event.key === '/' && !event.metaKey && !event.ctrlKey && !event.altKey && !isTyping(event.target)) {
        event.preventDefault();
        composerInput.current?.focus();
      } else if (event.key === 'Escape' && conv.streaming) {
        conv.stop();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [conv]);

  const noReady = docsStatus === 'ready' && ready.length === 0;
  const scopeLabel = ready.length === 0 ? 'Scope' : scopedIds.length === 0 ? 'All documents' : `${scopedIds.length} of ${ready.length} documents`;
  const placeholder = `Ask across ${scopeCount} ${scopeCount === 1 ? 'document' : 'documents'}`;
  const sourceCount = focused ? focused.citations.length : 0;

  const panel = (
    <EvidencePanel
      message={focused}
      activeId={activeId}
      onActive={setActiveId}
      reveal={conv.revealKey !== null && focused?.key === conv.revealKey}
    />
  );

  return (
    <div className="chat-layout" data-panel={panelOpen && wide ? 'open' : 'closed'}>
      <main className="chat" aria-labelledby="chat-title">
        <header className="chat__head">
          <h1 id="chat-title" title={session?.title}>{session ? session.title : 'New chat'}</h1>
          {sessionId ? <button type="button" className="btn btn--ghost btn--sm" onClick={exportChat} title="Export conversation as Markdown"><Download size={15}/> Export</button> : null}
          {wide ? (
            <button type="button" className="btn btn--ghost btn--sm" aria-expanded={panelOpen} aria-controls="evidence" onClick={() => setPanel(!panelOpen)}>
              {panelOpen ? <PanelRightClose size={16} strokeWidth={1.5} aria-hidden="true" /> : <PanelRightOpen size={16} strokeWidth={1.5} aria-hidden="true" />}
              {panelOpen ? 'Hide sources' : 'Show sources'}
            </button>
          ) : (
            <button type="button" className="btn btn--sm" disabled={!focused} onClick={() => setSheetOpen(true)}>
              Sources ({sourceCount})
            </button>
          )}
        </header>

        <div className="chat__scroll-wrap">
          <div
            ref={scroller}
            className="chat__scroll"
            role="region"
            aria-label="Conversation"
            tabIndex={0}
            onScroll={onScroll}
          >
            <div className="chat__col">
              {conv.loading ? (
                <div className="chat-empty" aria-hidden="true">
                  <span className="skeleton" data-w="30" />
                  <span className="skeleton" data-w="85" />
                  <span className="skeleton" data-w="70" />
                  <span className="skeleton" data-w="25" />
                  <span className="skeleton" data-w="90" />
                </div>
              ) : null}
              {conv.loadError ? (
                <div className="empty" role="alert">
                  <h2>This chat did not load</h2>
                  <p>{conv.loadError}</p>
                  <button type="button" className="btn" onClick={conv.reload}>Retry</button>
                </div>
              ) : null}
              {!conv.loading && !conv.loadError && messages.length === 0 ? (
                <EmptyChat
                  docsStatus={docsStatus}
                  readyCount={ready.length}
                  totalCount={docs.length}
                  sampling={sampling}
                  onLoadSamples={onLoadSamples}
                  onAsk={{ questions: EXAMPLE_QUESTIONS, ask: submit }}
                />
              ) : null}
              {messages.map((message) => (
                <Message
                  key={message.key}
                  message={message}
                  focused={focused?.key === message.key}
                  activeId={focused?.key === message.key ? activeId : null}
                  onFocus={() => setFocusKey(message.key)}
                  onCite={(id) => cite(message, id)}
                  onHover={setActiveId}
                  onRetry={retry}
                  onOpenScope={openScope}
                  onRephrase={rephrase}
                  onFeedback={sendFeedback}
                />
              ))}
            </div>
          </div>
          {showJump ? (
            <button type="button" className="btn jump" onClick={jumpToLatest}>
              <ArrowDown size={16} strokeWidth={1.5} aria-hidden="true" />
              Jump to latest
            </button>
          ) : null}
        </div>

        <div className="chat__composer">
          <Composer
            inputRef={composerInput}
            value={draft}
            onChange={setDraft}
            onSend={() => submit(draft)}
            onStop={conv.stop}
            streaming={conv.streaming}
            disabled={noReady || selectedProcessing || selectedUnavailable}
            disabledReason={selectedProcessing ? 'Wait for selected documents to finish indexing' : selectedUnavailable ? 'Selected documents are unavailable. Choose a ready document.' : docs.length === 0 ? 'Add documents to ask questions' : 'Wait for indexing to finish'}
            placeholder={placeholder}
            mode={mode}
            onModeChange={changeMode}
            scopeLabel={scopeLabel}
            scopeOpen={scopeOpen}
            onToggleScope={() => setScopeOpen((v) => !v)}
            scopePanelId="scope-panel"
            error={notice}
            docs={docs}
            selectedDocIds={scope.ids}
            onToggleDocument={scope.toggle}
            onUploadFiles={onUploadFiles}
            uploadBusy={uploadBusy}
            scopePanel={scopeOpen ? (
              <div id="scope-panel" className="composer__scope">
                <ScopePicker
                  docs={ready}
                  selected={selected}
                  onToggle={scope.toggle}
                  onSelectAll={() => scope.setMany(ready.map((d) => d.id))}
                  onClear={scope.clear}
                />
              </div>
            ) : null}
          />
        </div>
        <p className="sr-only" role="status" aria-live="polite">{conv.announce}</p>
      </main>

      {wide ? (
        <aside id="evidence" className="evidence" aria-label="Sources and retrieval trace" hidden={!panelOpen}>
          <header className="evidence__head">
            <h2>Sources{sourceCount > 0 ? <span className="num"> ({sourceCount})</span> : null}</h2>
          </header>
          <div className="evidence__scroll" tabIndex={0} role="region" aria-label="Source passages">{panel}</div>
        </aside>
      ) : (
        <ModalDialog open={sheetOpen} onClose={() => setSheetOpen(false)} label="Sources and retrieval trace" variant="sheet">
          <header className="evidence__head">
            <h2>Sources{sourceCount > 0 ? <span className="num"> ({sourceCount})</span> : null}</h2>
            <button type="button" className="icon-btn" aria-label="Close sources" onClick={() => setSheetOpen(false)}>
              <X size={16} strokeWidth={1.5} aria-hidden="true" />
            </button>
          </header>
          <div className="evidence__scroll" tabIndex={0} role="region" aria-label="Source passages">{panel}</div>
        </ModalDialog>
      )}
    </div>
  );
}
