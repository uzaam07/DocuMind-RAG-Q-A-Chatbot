import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, FileUp, Search, ShieldCheck, Sparkles, TriangleAlert, Upload, X } from 'lucide-react';
import DocTable from '../components/DocTable.jsx';
import DropOverlay from '../components/DropOverlay.jsx';
import TableSkeleton from '../components/TableSkeleton.jsx';
import { useDocuments } from '../state/useDocuments.js';
import { useScope } from '../state/scope.jsx';
import { useTitle } from '../state/useTitle.js';

const ACCEPT = '.pdf,.docx,.txt,.md,.xlsx,.pptx,.html,.htm,.png,.jpg,.jpeg,.webp';

function hasFiles(event) {
  return Array.from(event.dataTransfer?.types || []).includes('Files');
}

export default function Documents() {
  useTitle('Documents');
  const { docs, status, error, retryLoad, upload, loadSamples, reindex, remove } = useDocuments();
  const scope = useScope();
  const selected = useMemo(() => new Set(scope.ids), [scope.ids]);
  const [filter, setFilter] = useState('');
  const [notice, setNotice] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [sampling, setSampling] = useState(false);
  const [dragging, setDragging] = useState(false);
  const fileInput = useRef(null);
  const dragDepth = useRef(0);

  const submitFiles = useCallback(async (fileList) => {
    const files = Array.from(fileList);
    if (files.length === 0) return;
    setUploading(true);
    setNotice(null);
    try {
      const created = await upload(files);
      const rejected = created.filter((doc) => doc.status === 'failed').length;
      setNotice(rejected > 0
        ? { kind: 'error', text: `${rejected} of ${created.length} files could not be indexed. The reason is shown on each row.` }
        : { kind: 'info', text: `Uploaded ${created.length} ${created.length === 1 ? 'file' : 'files'}. Indexing has started.` });
    } catch (err) {
      setNotice({ kind: 'error', text: err.message });
    } finally {
      setUploading(false);
    }
  }, [upload]);

  useEffect(() => {
    const onEnter = (event) => {
      if (!hasFiles(event)) return;
      event.preventDefault();
      dragDepth.current += 1;
      setDragging(true);
    };
    const onOver = (event) => {
      if (hasFiles(event)) event.preventDefault();
    };
    const onLeave = (event) => {
      if (!hasFiles(event)) return;
      dragDepth.current = Math.max(0, dragDepth.current - 1);
      if (dragDepth.current === 0) setDragging(false);
    };
    const onDrop = (event) => {
      if (!hasFiles(event)) return;
      event.preventDefault();
      dragDepth.current = 0;
      setDragging(false);
      submitFiles(event.dataTransfer.files);
    };
    window.addEventListener('dragenter', onEnter);
    window.addEventListener('dragover', onOver);
    window.addEventListener('dragleave', onLeave);
    window.addEventListener('drop', onDrop);
    return () => {
      window.removeEventListener('dragenter', onEnter);
      window.removeEventListener('dragover', onOver);
      window.removeEventListener('dragleave', onLeave);
      window.removeEventListener('drop', onDrop);
    };
  }, [submitFiles]);

  const attempt = async (action) => {
    setNotice(null);
    try {
      await action();
    } catch (err) {
      setNotice({ kind: 'error', text: err.message });
    }
  };

  const onLoadSamples = async () => {
    setSampling(true);
    await attempt(loadSamples);
    setSampling(false);
  };

  const ready = docs.filter((doc) => doc.status === 'ready');
  const selectedCount = ready.filter((doc) => selected.has(doc.id)).length;
  const needle = filter.trim().toLowerCase();
  const visible = needle ? docs.filter((doc) => doc.filename.toLowerCase().includes(needle)) : docs;

  const onToggleAll = (list, on) => {
    const ids = new Set(scope.ids);
    for (const doc of list) {
      if (on) ids.add(doc.id);
      else ids.delete(doc.id);
    }
    scope.setMany([...ids]);
  };

  return (
    <main className="page" aria-labelledby="documents-title">
      <header className="page__head documents-head">
        <div className="documents-head__intro">
          <span className="intel-overline"><span className="intel-overline__pulse"/> KNOWLEDGE MANAGEMENT</span>
          <h1 id="documents-title">Knowledge <em>library.</em></h1>
          <p>Every source, organized and ready to become an answer.</p>
        </div>
        <div className="toolbar">
          <button type="button" className="btn btn--primary" disabled={uploading} onClick={() => fileInput.current?.click()}>
            <Upload size={16} strokeWidth={1.5} aria-hidden="true" />
            {uploading ? 'Uploading' : 'Upload documents'}
          </button>
          <input
            ref={fileInput}
            className="sr-only"
            type="file"
            multiple
            accept={ACCEPT}
            tabIndex={-1}
            aria-hidden="true"
            onChange={(event) => {
              submitFiles(event.target.files);
              event.target.value = '';
            }}
          />
          <div className="search">
            <Search size={16} strokeWidth={1.5} aria-hidden="true" />
            <label htmlFor="doc-filter" className="sr-only">Filter documents by name</label>
            <input
              id="doc-filter"
              type="search"
              className="input"
              placeholder="Filter by name"
              value={filter}
              onChange={(event) => setFilter(event.target.value)}
            />
          </div>
          <p className="scope-count" aria-live="polite">
            <span className="num">{selectedCount}</span> of <span className="num">{ready.length}</span> selected
            <span className="muted">{selectedCount === 0 && ready.length > 0 ? ', chat searches all' : ''}</span>
          </p>
        </div>
      </header>

      {notice ? (
        <div className="notice" data-kind={notice.kind} role={notice.kind === 'error' ? 'alert' : 'status'}>
          {notice.kind === 'error' ? <TriangleAlert size={16} strokeWidth={1.5} aria-hidden="true" /> : null}
          <p>{notice.text}</p>
          <button type="button" className="icon-btn" aria-label="Dismiss message" onClick={() => setNotice(null)}>
            <X size={16} strokeWidth={1.5} aria-hidden="true" />
          </button>
        </div>
      ) : null}

      {status === 'loading' ? <TableSkeleton /> : null}

      {status === 'error' ? (
        <div className="empty" role="alert">
          <h2>Documents did not load</h2>
          <p>{error}</p>
          <button type="button" className="btn" onClick={retryLoad}>Retry</button>
        </div>
      ) : null}

      {status === 'ready' && docs.length === 0 ? (
        <div className="empty empty--onboarding">
          <span className="empty__icon"><FileUp size={22}/></span>
          <span className="login__kicker">GETTING STARTED · STEP 01</span>
          <h2>Your workspace starts with a document.</h2>
          <p>Upload PDF, DOCX, TXT, Markdown, XLSX, PPTX, HTML or image files. DocuMind will index its contents so you can ask questions and inspect the supporting passages.</p>
          <div className="onboarding-steps"><div className="onboarding-step onboarding-step--active"><span>01</span><strong>Upload</strong><small>Add your source files</small></div><ArrowRight size={15}/><div className="onboarding-step"><span>02</span><strong>Ask</strong><small>Use natural language</small></div><ArrowRight size={15}/><div className="onboarding-step"><span>03</span><strong>Verify</strong><small>Review cited evidence</small></div></div>
          <p className="onboarding-privacy"><ShieldCheck size={14}/> Your documents are available inside your private workspace.</p>
          <dl className="facts">
            <div><dt>Types</dt><dd>PDF, DOCX, TXT, MD, XLSX, PPTX, HTML, PNG, JPG, WEBP</dd></div>
            <div><dt>Limit</dt><dd>20 MB per file</dd></div>
            <div><dt>OCR</dt><dd>Scanned PDFs and images</dd></div>
          </dl>
          <div className="empty__actions">
            <button type="button" className="btn" disabled={sampling} onClick={onLoadSamples}>
              {sampling ? 'Loading samples' : 'Load sample documents'}
            </button>
            <span className="muted">Adds a small set of example documents so you can try questions right away.</span>
          </div>
        </div>
      ) : null}

      {status === 'ready' && docs.length > 0 ? (
        <>
          {error ? <p className="field-error" role="alert">Could not refresh the list: {error}</p> : null}
          {visible.length > 0 ? (
            <DocTable
              docs={visible}
              selected={selected}
              onToggle={scope.toggle}
              onToggleAll={onToggleAll}
              onReindex={(id) => attempt(() => reindex(id))}
              onDelete={(id) => attempt(() => remove(id))}
            />
          ) : (
            <div className="empty">
              <h2>No match</h2>
              <p>No document name contains &ldquo;{filter.trim()}&rdquo;.</p>
              <button type="button" className="btn" onClick={() => setFilter('')}>Clear filter</button>
            </div>
          )}
          <p className="page__foot">
            {ready.length > 0 ? (
              <>Selected documents are the scope for <Link to="/chat">Chat</Link>. With none selected, chat searches every ready document.</>
            ) : (
              'Documents become selectable once indexing finishes.'
            )}
          </p>
        </>
      ) : null}

      {dragging ? <DropOverlay /> : null}
    </main>
  );
}
