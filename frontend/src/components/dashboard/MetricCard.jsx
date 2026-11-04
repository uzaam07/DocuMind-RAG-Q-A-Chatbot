export default function MetricCard({ label, value, note, Icon, index = 0, accent = 'silver' }) {
  return (
    <article className={`intel-metric intel-metric--${accent}`} style={{ '--stagger': `${index * 65}ms` }}>
      <div className="intel-metric__top"><span className="intel-metric__label">{label}</span><span className="intel-metric__icon"><Icon size={17} /></span></div>
      <strong className="intel-metric__value">{value}</strong>
      <span className="intel-metric__note">{note}</span>
      <span className="intel-metric__glint" aria-hidden="true" />
    </article>
  );
}
