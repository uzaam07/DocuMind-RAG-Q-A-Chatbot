import { ArrowUpRight, FileUp, MessageSquareText } from 'lucide-react';
import { Link } from 'react-router-dom';

export default function QuickActions({ onUpload }) {
  return (
    <section className="intel-quick-actions" aria-label="Quick actions">
      <span className="intel-quick-actions__label">QUICK ACCESS</span>
      <button type="button" onClick={onUpload}><FileUp size={15}/><span>Upload source</span><ArrowUpRight size={13}/></button>
      <Link to="/chat"><MessageSquareText size={15}/><span>Ask a question</span><ArrowUpRight size={13}/></Link>
      <Link to="/documents"><ArrowUpRight size={15}/><span>Explore library</span></Link>
    </section>
  );
}
