const rtf = new Intl.RelativeTimeFormat('en', { numeric: 'auto' });

export function formatBytes(bytes) {
  if (!Number.isFinite(bytes) || bytes < 0) return '-';
  if (bytes < 1024) return `${bytes} B`;
  const kb = bytes / 1024;
  if (kb < 1024) return `${kb < 10 ? kb.toFixed(1) : Math.round(kb)} KB`;
  const mb = kb / 1024;
  return `${mb < 10 ? mb.toFixed(1) : Math.round(mb)} MB`;
}

export function relativeTime(iso, now = Date.now()) {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return '-';
  const seconds = Math.round((then - now) / 1000);
  const abs = Math.abs(seconds);
  if (abs < 45) return 'just now';
  if (abs < 3600) return rtf.format(Math.round(seconds / 60), 'minute');
  if (abs < 86400) return rtf.format(Math.round(seconds / 3600), 'hour');
  if (abs < 86400 * 30) return rtf.format(Math.round(seconds / 86400), 'day');
  return new Date(then).toLocaleDateString('en', { year: 'numeric', month: 'short', day: 'numeric' });
}

export function exactTime(iso) {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? '' : d.toLocaleString('en', { dateStyle: 'medium', timeStyle: 'medium' });
}

const STAGE_LABELS = {
  queued: 'Queued',
  parsing: 'Parsing',
  chunking: 'Chunking',
  indexing: 'Indexing',
  done: 'Finishing',
};

export function stageLabel(doc) {
  if (doc.stage === 'embedding') {
    return doc.progress_total > 0
      ? `Embedding ${doc.progress_done}/${doc.progress_total}`
      : 'Embedding';
  }
  return STAGE_LABELS[doc.stage] || 'Processing';
}

export function typeLabel(fileType) {
  return fileType && fileType !== 'unknown' ? fileType.toUpperCase() : 'Unknown';
}

export function formatScore(score) {
  return Number.isFinite(score) ? score.toFixed(2) : '-';
}

export function formatMs(value) {
  return Number.isFinite(value) ? `${Math.round(value).toLocaleString('en')} ms` : '-';
}

export function formatPercent(fraction) {
  return Number.isFinite(fraction) ? `${(fraction * 100).toFixed(1)}%` : '-';
}

export function formatDecimal(value, digits = 3) {
  return Number.isFinite(value) ? value.toFixed(digits) : '-';
}

export function lowerFirst(text) {
  return text ? text.charAt(0).toLowerCase() + text.slice(1) : '';
}
