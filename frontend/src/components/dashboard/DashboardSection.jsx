export default function DashboardSection({ eyebrow, title, detail, action }) {
  return (
    <div className="intel-panel__heading">
      <div><span className="intel-eyebrow">{eyebrow}</span><h2>{title}</h2>{detail ? <p>{detail}</p> : null}</div>
      {action}
    </div>
  );
}
