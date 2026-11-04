import { useId } from 'react';

export default function ScopePicker({ docs, selected, onToggle, onSelectAll, onClear }) {
  const hintId = useId();
  if (docs.length === 0) {
    return <p className="scope__empty">No indexed documents yet. Upload one on the Documents page.</p>;
  }
  return (
    <fieldset className="scope" aria-describedby={hintId}>
      <legend>Documents in scope</legend>
      <p id={hintId} className="muted scope__hint">
        Questions search only the checked documents. With none checked, all {docs.length} are searched.
      </p>
      <div className="scope__actions">
        <button type="button" className="link-button" onClick={onSelectAll}>Select all</button>
        <button type="button" className="link-button" onClick={onClear} disabled={selected.size === 0}>Clear selection</button>
      </div>
      <ul className="scope__list">
        {docs.map((doc) => (
          <li key={doc.id}>
            <label className="check">
              <input type="checkbox" checked={selected.has(doc.id)} onChange={() => onToggle(doc.id)} />
              <span className="check__label" title={doc.filename}>{doc.filename}</span>
            </label>
          </li>
        ))}
      </ul>
    </fieldset>
  );
}
