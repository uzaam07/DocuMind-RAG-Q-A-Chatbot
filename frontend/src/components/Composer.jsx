import { useId, useLayoutEffect, useRef, useState } from 'react';
import { ArrowUp, Check, FileText, FolderOpen, Plus, Square, SlidersHorizontal, Upload, X } from 'lucide-react';
import SegmentedControl from './SegmentedControl.jsx';

export const MODES = [
  { value: 'vector', label: 'vector' },
  { value: 'hybrid', label: 'hybrid' },
  { value: 'hybrid_rerank', label: 'hybrid_rerank' },
];

const MAX_HEIGHT_PX = 176;

export default function Composer({
  inputRef, value, onChange, onSend, onStop, streaming, disabled, disabledReason,
  placeholder, mode, onModeChange, scopeLabel, scopeOpen, onToggleScope, scopePanelId, scopePanel, error,
  docs = [], selectedDocIds = [], onToggleDocument, onUploadFiles, uploadBusy = false,
}) {
  const hintId = useId();
  const canSend = !disabled && value.trim().length > 0;
  const [attachOpen, setAttachOpen] = useState(false);
  const [showExisting, setShowExisting] = useState(false);
  const fileInput = useRef(null);

  useLayoutEffect(() => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, MAX_HEIGHT_PX)}px`;
  }, [value, inputRef]);

  const onKeyDown = (event) => {
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      if (canSend && !streaming) onSend();
    }
  };

  return (
    <form
      className="composer"
      onSubmit={(event) => {
        event.preventDefault();
        if (canSend && !streaming) onSend();
      }}
    >
      {scopePanel}
      {error ? (
        <p className="field-error" role="alert">{error}</p>
      ) : null}
      <div className="composer__box">
        <div className="composer__input-row">
        <div className="composer__attach-wrap">
          <button type="button" className="icon-btn composer__attach" aria-label="Attach documents" aria-expanded={attachOpen} onClick={() => setAttachOpen((v) => !v)}><Plus size={18} strokeWidth={1.7}/></button>
          {attachOpen ? (
            <div className="attach-menu" role="menu" aria-label="Document attachments">
              <button type="button" role="menuitem" onClick={() => fileInput.current?.click()} disabled={uploadBusy}><Upload size={16}/><span>{uploadBusy ? 'Uploading…' : 'Upload new documents'}</span></button>
              <button type="button" role="menuitem" onClick={() => setShowExisting((v) => !v)}><FolderOpen size={16}/><span>Attach existing documents</span></button>
              {showExisting ? <div className="attach-menu__docs">
                {docs.length === 0 ? <p>No documents uploaded yet.</p> : docs.map((doc) => <label key={doc.id} className="attach-menu__doc"><input type="checkbox" checked={selectedDocIds.includes(doc.id)} disabled={doc.status !== 'ready'} onChange={() => onToggleDocument?.(doc.id)}/><span><strong>{doc.filename}</strong><small>{doc.status === 'ready' ? 'Ready to use' : doc.status === 'processing' ? 'Indexing in progress' : 'Indexing failed'}</small></span>{selectedDocIds.includes(doc.id) ? <Check size={15}/> : null}</label>)}
              </div> : null}
              <p className="attach-menu__note">Only indexed documents can be used as evidence.</p>
            </div>
          ) : null}
          <input ref={fileInput} type="file" hidden multiple accept=".pdf,.docx,.txt,.md,.xlsx,.pptx,.html,.htm,.png,.jpg,.jpeg,.webp" onChange={async (event) => { const files = Array.from(event.target.files || []); if (files.length) await onUploadFiles?.(files); event.target.value = ''; setAttachOpen(false); }} />
        </div>
        <label htmlFor="composer-input" className="sr-only">Question</label>
        <textarea
          id="composer-input"
          ref={inputRef}
          rows={1}
          value={value}
          maxLength={2000}
          disabled={disabled}
          placeholder={disabled ? disabledReason : placeholder}
          aria-describedby={hintId}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={onKeyDown}
        />
        </div>
        {selectedDocIds.length > 0 ? <div className="composer__attachments" aria-label="Selected documents">
          {docs.filter((doc) => selectedDocIds.includes(doc.id)).map((doc) => <span key={doc.id} className="composer__attachment" data-status={doc.status}><FileText size={13}/><span title={doc.filename}>{doc.filename}</span><small>{doc.status === 'ready' ? 'Ready' : doc.status === 'processing' ? 'Indexing' : 'Failed'}</small><button type="button" className="icon-btn" aria-label={`Remove ${doc.filename} from chat scope`} onClick={() => onToggleDocument?.(doc.id)}><X size={13}/></button></span>)}
        </div> : null}
        <div className="composer__bar">
          <button
            type="button"
            className="btn btn--ghost btn--sm"
            aria-expanded={scopeOpen}
            aria-controls={scopePanelId}
            onClick={onToggleScope}
          >
            <SlidersHorizontal size={16} strokeWidth={1.5} aria-hidden="true" />
            {scopeLabel}
          </button>
          <SegmentedControl label="Retrieval mode" options={MODES} value={mode} onChange={onModeChange} mono />
          {streaming ? (
            <button type="button" className="btn btn--sm composer__send" onClick={onStop}>
              <Square size={16} strokeWidth={1.5} aria-hidden="true" />
              Stop
            </button>
          ) : (
            <button type="submit" className="btn btn--primary btn--sm composer__send" disabled={!canSend}>
              <ArrowUp size={16} strokeWidth={1.5} aria-hidden="true" />
              Ask
            </button>
          )}
        </div>
      </div>
      <p id={hintId} className="composer__hint">
        Enter to ask, Shift+Enter for a new line, / to focus here, Esc to stop.
      </p>
    </form>
  );
}
