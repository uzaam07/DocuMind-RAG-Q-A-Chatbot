import { FileText, MessageSquare } from 'lucide-react';

export default function ActivityFeed({ items, formatDate, formatExact }) {
  if (!items.length) return <div className="intel-empty"><span className="intel-empty__mark"><FileText size={18}/></span><strong>Your activity will appear here</strong><p>Uploads and conversations will create a useful workspace timeline.</p></div>;
  return (
    <div className="activity-timeline">
      {items.map((item) => <div className="activity-timeline__item" key={item.id}>
        <span className={`activity-timeline__icon activity-timeline__icon--${item.kind}`}>{item.kind === 'document' ? <FileText size={14}/> : <MessageSquare size={14}/>}</span>
        <div><strong>{item.title}</strong><small>{item.detail}</small></div>
        <time dateTime={item.date} title={formatExact(item.date)}>{formatDate(item.date)}</time>
      </div>)}
    </div>
  );
}
