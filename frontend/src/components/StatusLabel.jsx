import { stageLabel } from '../lib/format.js';

const KIND = {
  ready: { text: 'Ready', shape: 'ready' },
  failed: { text: 'Failed', shape: 'failed' },
};

/** Status is always a shape plus a text label, never colour alone. */
export default function StatusLabel({ doc }) {
  const processing = doc.status === 'processing';
  const kind = processing ? { text: stageLabel(doc), shape: 'processing' } : KIND[doc.status] || KIND.failed;
  return (
    <span className="status" data-status={kind.shape}>
      <span className="status__dot" aria-hidden="true" />
      <span className="status__text">{kind.text}</span>
      {processing && doc.stage === 'embedding' && doc.progress_total > 0 ? (
        <span className="status__bar" aria-hidden="true">
          <span style={{ '--v': Math.min(1, doc.progress_done / doc.progress_total) }} />
        </span>
      ) : null}
    </span>
  );
}
