import { Fragment, useEffect, useRef, useState } from 'react';
import { RotateCw, Trash2 } from 'lucide-react';
import StatusLabel from './StatusLabel.jsx';
import { exactTime, formatBytes, relativeTime, typeLabel } from '../lib/format.js';

const COLUMN_COUNT = 8;

function ConfirmRow({ doc, busy, onConfirm, onCancel }) {
  const cancelRef = useRef(null);
  useEffect(() => {
    cancelRef.current?.focus();
  }, []);
  const subject = doc.chunk_count > 0
    ? `this document and its ${doc.chunk_count} ${doc.chunk_count === 1 ? 'chunk' : 'chunks'}`
    : 'this document';
  return (
    <tr className="confirm-row">
      <td colSpan={COLUMN_COUNT}>
        <div className="confirm" role="group" aria-label={`Confirm deleting ${doc.filename}`}>
          <p>Delete {subject}? This cannot be undone.</p>
          <button type="button" className="btn btn--danger btn--sm" disabled={busy} onClick={onConfirm}>
            {busy ? 'Deleting' : 'Delete'}
          </button>
          <button type="button" ref={cancelRef} className="btn btn--sm" disabled={busy} onClick={onCancel}>
            Cancel
          </button>
        </div>
      </td>
    </tr>
  );
}

export default function DocTable({ docs, selected, onToggle, onToggleAll, onReindex, onDelete }) {
  const [confirmId, setConfirmId] = useState(null);
  const [busyId, setBusyId] = useState(null);
  const headRef = useRef(null);

  const selectable = docs.filter((doc) => doc.status === 'ready');
  const selectedCount = selectable.filter((doc) => selected.has(doc.id)).length;
  const allSelected = selectable.length > 0 && selectedCount === selectable.length;

  useEffect(() => {
    if (headRef.current) headRef.current.indeterminate = selectedCount > 0 && !allSelected;
  }, [selectedCount, allSelected]);

  const run = async (id, action) => {
    setBusyId(id);
    try {
      await action(id);
    } finally {
      setBusyId(null);
      setConfirmId(null);
    }
  };

  return (
    <div className="doctable-wrap">
      <table className="doctable">
        <caption className="sr-only">Uploaded documents</caption>
        <colgroup>
          <col className="c-check" />
          <col className="c-name" />
          <col className="c-type" />
          <col className="c-size" />
          <col className="c-chunks" />
          <col className="c-status" />
          <col className="c-indexed" />
          <col className="c-actions" />
        </colgroup>
        <thead>
          <tr>
            <th scope="col" className="cell-check">
              <input
                ref={headRef}
                type="checkbox"
                aria-label="Include all ready documents in scope"
                checked={allSelected}
                disabled={selectable.length === 0}
                onChange={() => onToggleAll(selectable, !allSelected)}
              />
            </th>
            <th scope="col">Name</th>
            <th scope="col" className="cell-type">Type</th>
            <th scope="col" className="cell-num">Size</th>
            <th scope="col" className="cell-num">Chunks</th>
            <th scope="col">Status</th>
            <th scope="col" className="cell-indexed">Indexed</th>
            <th scope="col" className="cell-actions"><span className="sr-only">Actions</span></th>
          </tr>
        </thead>
        <tbody>
          {docs.map((doc) => {
            const ready = doc.status === 'ready';
            const failed = doc.status === 'failed';
            const busy = busyId === doc.id;
            return (
              <Fragment key={doc.id}>
              <tr data-status={doc.status} data-selected={selected.has(doc.id) || undefined}>
                <td className="cell-check">
                  <input
                    type="checkbox"
                    aria-label={`Include ${doc.filename} in scope`}
                    checked={selected.has(doc.id)}
                    disabled={!ready}
                    onChange={() => onToggle(doc.id)}
                  />
                </td>
                <td className="cell-name">
                  <span className="doc-name" title={doc.filename}>{doc.filename}</span>
                  {failed && doc.error ? <span className="doc-error">{doc.error}</span> : null}
                </td>
                <td className="cell-type">{typeLabel(doc.file_type)}</td>
                <td className="cell-num num">{formatBytes(doc.size_bytes)}</td>
                <td className="cell-num num">{ready ? doc.chunk_count : '-'}</td>
                <td className="cell-status"><StatusLabel doc={doc} /></td>
                <td className="cell-indexed" title={ready ? exactTime(doc.updated_at) : undefined}>
                  {ready ? relativeTime(doc.updated_at) : '-'}
                </td>
                <td className="cell-actions">
                  <button
                    type="button"
                    className="btn btn--ghost btn--sm"
                    disabled={doc.status === 'processing' || busy}
                    onClick={() => run(doc.id, onReindex)}
                  >
                    <RotateCw size={16} strokeWidth={1.5} aria-hidden="true" />
                    <span className="btn__text">{failed ? 'Retry' : 'Reindex'}</span>
                    <span className="sr-only"> {doc.filename}</span>
                  </button>
                  <button
                    type="button"
                    className="btn btn--ghost btn--sm"
                    disabled={busy}
                    aria-expanded={confirmId === doc.id}
                    onClick={() => setConfirmId(doc.id)}
                  >
                    <Trash2 size={16} strokeWidth={1.5} aria-hidden="true" />
                    <span className="btn__text">Delete</span>
                    <span className="sr-only"> {doc.filename}</span>
                  </button>
                </td>
              </tr>
              {confirmId === doc.id ? (
                <ConfirmRow
                  doc={doc}
                  busy={busy}
                  onConfirm={() => run(doc.id, onDelete)}
                  onCancel={() => setConfirmId(null)}
                />
              ) : null}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
