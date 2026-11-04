import { useId } from 'react';

/** Native radio group styled as one segmented control. Arrow keys work for free. */
export default function SegmentedControl({ label, options, value, onChange, disabled = false, mono = false }) {
  const name = useId();
  return (
    <div className="segmented" role="radiogroup" aria-label={label} data-mono={mono || undefined}>
      {options.map((option) => (
        <label key={option.value} className="segmented__option">
          <input
            type="radio"
            name={name}
            value={option.value}
            checked={value === option.value}
            disabled={disabled}
            onChange={() => onChange(option.value)}
          />
          <span>{option.label}</span>
        </label>
      ))}
    </div>
  );
}
