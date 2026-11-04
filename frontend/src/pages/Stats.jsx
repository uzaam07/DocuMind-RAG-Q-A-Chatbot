import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Activity, ArrowRight, ArrowUpRight, Clock3, Database, FileImage, FileSpreadsheet, FileText,
  FileType2, Gauge, Layers3, MessageCircle, MessageSquare, Plus, RefreshCw,
  Search, ShieldCheck, Sparkles, UploadCloud, Zap,
} from 'lucide-react';
import { api } from '../api/client.js';
import { useDocuments } from '../state/useDocuments.js';
import { useSessions } from '../state/sessions.jsx';
import { exactTime, formatMs, formatPercent, relativeTime } from '../lib/format.js';
import MetricCard from '../components/dashboard/MetricCard.jsx';
import DashboardSection from '../components/dashboard/DashboardSection.jsx';
import DashboardChart from '../components/dashboard/DashboardChart.jsx';
import ActivityFeed from '../components/dashboard/ActivityFeed.jsx';
import QuickActions from '../components/dashboard/QuickActions.jsx';
import { useTitle } from '../state/useTitle.js';

const TYPE_META = {
  pdf: { label: 'PDF', Icon: FileText }, docx: { label: 'Word', Icon: FileType2 },
  txt: { label: 'Text', Icon: FileText }, md: { label: 'Markdown', Icon: FileText },
  xlsx: { label: 'Spreadsheets', Icon: FileSpreadsheet }, pptx: { label: 'Presentations', Icon: FileText },
  html: { label: 'Web pages', Icon: FileText }, htm: { label: 'Web pages', Icon: FileText },
  png: { label: 'Images', Icon: FileImage }, jpg: { label: 'Images', Icon: FileImage },
  jpeg: { label: 'Images', Icon: FileImage }, webp: { label: 'Images', Icon: FileImage },
};

function dateLabel(value) {
  if (!value) return 'Date unavailable';
  try { return relativeTime(value); } catch { return 'Recently'; }
}
function typeOf(doc) {
  const ext = (doc.file_type || doc.filename?.split('.').pop() || '').toLowerCase();
  return TYPE_META[ext] || { label: ext.toUpperCase() || 'File', Icon: FileText };
}
function CacheCard({ title, cache, Icon }) {
  const total = (cache?.hits || 0) + (cache?.misses || 0);
  const hitWidth = total ? ((cache.hits || 0) / total) * 100 : 0;
  return (
    <div className="cache-insight">
      <div className="cache-insight__top"><span className="cache-insight__icon"><Icon size={16}/></span><div><strong>{title}</strong><small>{(cache?.entries || 0).toLocaleString('en')} stored entries</small></div><b>{formatPercent(cache?.hit_rate || 0)}</b></div>
      <div className="cache-insight__track" role="img" aria-label={`${formatPercent(cache?.hit_rate || 0)} hit rate`}><span style={{ width: `${hitWidth}%` }}/></div>
      <div className="cache-insight__legend"><span><i className="legend-dot legend-dot--hit"/> {(cache?.hits || 0).toLocaleString('en')} hits</span><span><i className="legend-dot legend-dot--miss"/> {(cache?.misses || 0).toLocaleString('en')} misses</span></div>
    </div>
  );
}
function EmptyState({ title, copy, action }) {
  return <div className="intel-empty"><span className="intel-empty__mark"><Sparkles size={18}/></span><strong>{title}</strong><p>{copy}</p>{action}</div>;
}

export default function Stats() {
  useTitle('Intelligence overview');
  const { docs, status: docsStatus, upload } = useDocuments();
  const { sessions, status: sessionsStatus } = useSessions();
  const [state, setState] = useState({ status: 'loading', stats: null, result: null, error: null });
  const [uploading, setUploading] = useState(false);
  const [uploadNotice, setUploadNotice] = useState('');
  const fileInput = useRef(null);

  const load = useCallback(async (signal) => {
    try {
      const [stats, result] = await Promise.all([api.stats(signal), api.latestEval(signal)]);
      setState({ status: 'ready', stats, result, error: null });
    } catch (err) {
      if (err.name === 'AbortError') return;
      setState({ status: 'error', stats: null, result: null, error: err.message });
    }
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    load(controller.signal);
    return () => controller.abort();
  }, [load]);

  const { stats, result, status, error } = state;
  const readyDocs = docs.filter((doc) => doc.status === 'ready');
  const processingDocs = docs.filter((doc) => doc.status === 'processing');
  const failedDocs = docs.filter((doc) => doc.status === 'failed');
  const recentDocs = [...docs].sort((a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0)).slice(0, 5);
  const recentSessions = [...sessions].sort((a, b) => new Date(b.updated_at || b.created_at || 0) - new Date(a.updated_at || a.created_at || 0)).slice(0, 5);
  const fileTypes = useMemo(() => {
    const groups = new Map();
    docs.forEach((doc) => {
      const type = typeOf(doc);
      const key = type.label;
      groups.set(key, { ...type, count: (groups.get(key)?.count || 0) + 1 });
    });
    return [...groups.values()].sort((a, b) => b.count - a.count).slice(0, 5);
  }, [docs]);
  const typeMax = Math.max(1, ...fileTypes.map((item) => item.count));
  const activity = useMemo(() => [
    ...docs.map((doc) => ({ id: `doc-${doc.id}`, kind: 'document', title: doc.filename, detail: doc.status === 'ready' ? 'Indexed and ready for retrieval' : doc.status === 'failed' ? 'Indexing failed' : 'Indexing in progress', date: doc.updated_at || doc.created_at, status: doc.status })),
    ...sessions.map((session) => ({ id: `session-${session.id}`, kind: 'chat', title: session.title || 'Untitled conversation', detail: 'Conversation updated', date: session.updated_at || session.created_at })),
  ].filter((item) => item.date).sort((a, b) => new Date(b.date) - new Date(a.date)).slice(0, 6), [docs, sessions]);

  const handleUpload = async (files) => {
    if (!files?.length) return;
    setUploading(true); setUploadNotice('');
    try {
      const created = await upload(files);
      const failed = created.filter((doc) => doc.status === 'failed').length;
      setUploadNotice(failed ? `${failed} file${failed === 1 ? '' : 's'} need attention.` : `${created.length} file${created.length === 1 ? '' : 's'} added. Indexing has started.`);
    } catch (err) { setUploadNotice(err.message); }
    finally { setUploading(false); }
  };

  return (
    <main className="page intel-page" aria-labelledby="stats-title">
      <header className="intel-header">
        <div className="intel-header__copy"><div className="intel-breadcrumb"><span>WORKSPACE</span><span>/</span><span>INTELLIGENCE</span></div><div className="intel-title-row"><div><span className="intel-overline"><span className="intel-overline__pulse"/> YOUR KNOWLEDGE SYSTEM</span><h1 id="stats-title">Intelligence <em>overview.</em></h1><p>See what's indexed, what's moving, and how your retrieval stack is performing.</p></div></div></div>
        <div className="intel-header__actions"><Link className="btn btn--soft" to="/documents"><Layers3 size={16}/> Library</Link><Link className="btn btn--primary" to="/chat"><Sparkles size={16}/> Ask DocuMind <ArrowUpRight size={15}/></Link></div>
      </header>

      {status === 'loading' ? <div className="intel-loading"><span/><span/><span/><span/></div> : null}
      {status === 'error' ? <div className="empty" role="alert"><h2>Intelligence overview unavailable</h2><p>{error}</p><button className="btn" type="button" onClick={() => { setState((current) => ({ ...current, status: 'loading' })); load(); }}><RefreshCw size={15}/> Try again</button></div> : null}

      {status === 'ready' && stats ? <>
        <section className="intel-metrics" aria-label="Workspace metrics">
          <MetricCard index={0} label="KNOWLEDGE ASSETS" value={stats.usage.documents.toLocaleString('en')} note={`${readyDocs.length} ready · ${processingDocs.length} processing`} Icon={Database} accent="blue"/>
          <MetricCard index={1} label="CONVERSATIONS" value={stats.usage.sessions.toLocaleString('en')} note="Saved research threads" Icon={MessageCircle} accent="silver"/>
          <MetricCard index={2} label="MESSAGES EXCHANGED" value={stats.usage.messages.toLocaleString('en')} note="Questions and responses" Icon={Activity} accent="ice"/>
          <MetricCard index={3} label="ANSWER CACHE HIT RATE" value={formatPercent(stats.answer_cache.hit_rate)} note="Since this server process started" Icon={Zap} accent="sage"/>
        </section>

        <QuickActions onUpload={() => fileInput.current?.click()}/>

        <section className="intel-feature-grid">
          <article className="intel-panel intel-panel--hero">
            <DashboardSection eyebrow="RETRIEVAL PERFORMANCE" title="Signal, not noise." detail="Compare the latest measured retrieval performance across your configured modes." action={<span className="intel-live-tag"><span/> {result?.available ? 'EVALUATED' : 'AWAITING DATA'}</span>}/>
            {result?.available ? <DashboardChart result={result}/> : <EmptyState title="No evaluation snapshot yet" copy="Run the offline evaluation harness to populate retrieval quality metrics."/>}
          </article>
          <article className="intel-panel intel-panel--upload">
            <div className="upload-orbit"><span/><span/><span/><UploadCloud size={25}/></div>
            <span className="intel-eyebrow">EXPAND YOUR KNOWLEDGE</span><h2>Bring your next source into focus.</h2><p>Drop in a document and let DocuMind make it searchable, contextual and ready for questions.</p>
            <button type="button" className="btn btn--primary intel-upload-button" onClick={() => fileInput.current?.click()} disabled={uploading}><Plus size={16}/>{uploading ? 'Uploading…' : 'Add documents'}</button>
            <input ref={fileInput} className="sr-only" type="file" multiple accept=".pdf,.docx,.txt,.md,.xlsx,.pptx,.html,.htm,.png,.jpg,.jpeg,.webp" onChange={(event) => { handleUpload(event.target.files); event.target.value = ''; }}/>
            {uploadNotice ? <span className="intel-upload-note" role="status">{uploadNotice}</span> : <span className="intel-upload-note">PDF · DOCX · XLSX · PPTX · TXT · IMAGES</span>}
          </article>
        </section>

        <section className="intel-two-col">
          <article className="intel-panel">
            <DashboardSection eyebrow="SYSTEM EFFICIENCY" title="Cache intelligence" detail="Process-level cache activity since the API server started."/>
            <div className="cache-stack"><CacheCard title="Answer cache" cache={stats.answer_cache} Icon={Zap}/><CacheCard title="Embedding cache" cache={stats.embedding_cache} Icon={Database}/></div>
            <p className="intel-footnote">Cache counters are shared by the running server process. Entry counts are shown separately from hit-rate totals.</p>
          </article>
          <article className="intel-panel">
            <DashboardSection eyebrow="KNOWLEDGE COMPOSITION" title="Your source mix" detail={`${docs.length} uploaded ${docs.length === 1 ? 'file' : 'files'} grouped by format.`} action={<Link className="intel-text-link" to="/documents">View library <ArrowRight size={14}/></Link>}/>
            {fileTypes.length ? <div className="source-mix">{fileTypes.map(({ label, Icon, count }) => <div className="source-mix__row" key={label}><span className="source-mix__type"><Icon size={15}/>{label}</span><div className="source-mix__track"><i style={{ width: `${(count / typeMax) * 100}%` }}/></div><strong>{count}</strong></div>)}</div> : <EmptyState title="Your library is ready for its first source" copy="Upload a PDF, presentation, spreadsheet or other supported file to start building your knowledge base." action={<Link to="/documents" className="intel-text-link">Open documents <ArrowRight size={14}/></Link>}/>}
            <div className="source-status"><span><i className="source-status__dot source-status__dot--ready"/>{readyDocs.length} ready</span><span><i className="source-status__dot source-status__dot--processing"/>{processingDocs.length} processing</span><span><i className="source-status__dot source-status__dot--failed"/>{failedDocs.length} failed</span></div>
          </article>
        </section>

        <section className="intel-two-col intel-two-col--lower">
          <article className="intel-panel">
            <DashboardSection eyebrow="RECENT KNOWLEDGE" title="Recently added" detail="Your latest source files and their indexing state." action={<Link className="intel-text-link" to="/documents">All documents <ArrowRight size={14}/></Link>}/>
            {docsStatus === 'loading' ? <div className="intel-empty">Loading your document library…</div> : recentDocs.length ? <div className="intel-list">{recentDocs.map((doc) => { const meta = typeOf(doc); const Icon = meta.Icon; return <div className="intel-list__item" key={doc.id}><span className="intel-file-icon"><Icon size={17}/></span><div className="intel-list__copy"><strong title={doc.filename}>{doc.filename}</strong><small>{meta.label} · {dateLabel(doc.created_at)}</small></div><span className={`intel-status intel-status--${doc.status}`}>{doc.status}</span></div>; })}</div> : <EmptyState title="No documents yet" copy="Your latest uploads will appear here." action={<Link to="/documents" className="intel-text-link">Upload your first file <ArrowRight size={14}/></Link>}/>}
          </article>
          <article className="intel-panel">
            <DashboardSection eyebrow="RESEARCH HISTORY" title="Recent conversations" detail="Pick up where your last question left off." action={<Link className="intel-text-link" to="/chat">Open chat <ArrowRight size={14}/></Link>}/>
            {sessionsStatus === 'loading' ? <div className="intel-empty">Loading conversations…</div> : recentSessions.length ? <div className="intel-list">{recentSessions.map((session) => <Link className="intel-list__item intel-list__item--link" to={`/chat/${session.id}`} key={session.id}><span className="intel-chat-icon"><MessageSquare size={16}/></span><span className="intel-list__copy"><strong title={session.title}>{session.title || 'Untitled conversation'}</strong><small>Updated {dateLabel(session.updated_at || session.created_at)}</small></span><ArrowUpRight size={15} className="intel-list__arrow"/></Link>)}</div> : <EmptyState title="No conversations yet" copy="Start a conversation with your indexed documents." action={<Link to="/chat" className="intel-text-link">Start a conversation <ArrowRight size={14}/></Link>}/>}
          </article>
        </section>

        <section className="intel-two-col">
          <article className="intel-panel">
            <DashboardSection eyebrow="WORKSPACE PULSE" title="Recent activity" detail="A timeline assembled from document and conversation timestamps."/>
            <ActivityFeed items={activity} formatDate={dateLabel} formatExact={exactTime}/>
            <p className="intel-footnote">Based on existing record timestamps; this is not a separate audit-event feed.</p>
          </article>
          <article className="intel-panel intel-panel--retrieval">
            <DashboardSection eyebrow="RETRIEVAL PIPELINE" title="Under the hood" detail="A quick view of the systems supporting evidence-led answers."/>
            <div className="pipeline-list"><div><span className="pipeline-list__icon"><Search size={15}/></span><div><strong>Hybrid search</strong><small>Semantic + lexical retrieval with rank fusion</small></div><span className="pipeline-list__state">Configured</span></div><div><span className="pipeline-list__icon"><Layers3 size={15}/></span><div><strong>Document indexing</strong><small>Chunking, embeddings and vector storage</small></div><span className="pipeline-list__state">{processingDocs.length ? `${processingDocs.length} active` : 'Idle'}</span></div><div><span className="pipeline-list__icon"><ShieldCheck size={15}/></span><div><strong>Evidence citations</strong><small>Answers linked back to source passages</small></div><span className="pipeline-list__state">Enabled</span></div></div>
            <div className="retrieval-footer"><span><Gauge size={15}/> Retrieval evaluation</span><strong>{result?.available ? 'Snapshot available' : 'Not run yet'}</strong></div>
          </article>
        </section>
        <footer className="intel-footer"><span>DOCUMIND INTELLIGENCE / PRIVATE WORKSPACE</span><span><Clock3 size={13}/> Stats refreshed when this view loads</span></footer>
      </> : null}
    </main>
  );
}
