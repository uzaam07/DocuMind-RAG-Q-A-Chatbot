import { Link, NavLink, useNavigate } from 'react-router-dom';
import { ChartColumn, Files, LogOut, MessageSquare, PanelLeftClose, PanelLeftOpen, Sparkles } from 'lucide-react';
import Wordmark from './Wordmark.jsx';
import SessionList from './SessionList.jsx';
import ThemeToggle from './ThemeToggle.jsx';
import { useAuth } from '../state/auth.jsx';

const NAV = [
  { to: '/stats', label: 'Overview', Icon: ChartColumn },
  { to: '/documents', label: 'Knowledge library', Icon: Files },
  { to: '/chat', label: 'AI conversations', Icon: MessageSquare },
];

export default function RailContent({ onNavigate, collapsed = false, onToggleCollapse }) {
  const { user, signOut } = useAuth();
  const navigate = useNavigate();
  const handleSignOut = () => { navigate('/login', { replace: true }); signOut(); };
  return (
    <div className={`rail ${collapsed ? 'rail--collapsed' : ''}`}>
      <div className="rail__brand-row">
        <Link to="/stats" className="rail__brand" aria-label="DocuMind, go to overview" onClick={onNavigate}><Wordmark /></Link>
        {onToggleCollapse ? <button type="button" className="rail__collapse" onClick={onToggleCollapse} aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'} title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}>{collapsed ? <PanelLeftOpen size={17}/> : <PanelLeftClose size={17}/>}</button> : null}
      </div>
      <div className="rail__workspace"><span className="rail__workspace-mark"><Sparkles size={15}/></span><span className="rail__workspace-copy"><strong>Personal workspace</strong><small>PRIVATE KNOWLEDGE BASE</small></span><span className="rail__workspace-chevron">⌄</span></div>
      <nav aria-label="Main" className="rail__nav">
        <span className="rail__section-label">WORKSPACE</span>
        <ul>{NAV.map(({ to, label, Icon }) => <li key={to}><NavLink to={to} className="rail__link" onClick={onNavigate} title={collapsed ? label : undefined}><span className="rail__link-icon"><Icon size={17} strokeWidth={1.7}/></span><span className="rail__link-label">{label}</span><span className="rail__active-mark"/></NavLink></li>)}</ul>
      </nav>
      <div className="rail__sessions"><SessionList onNavigate={onNavigate}/></div>
      <div className="rail__foot">
        <div className="rail__foot-tools"><ThemeToggle className="btn btn--ghost btn--sm rail__theme"/></div>
        <div className="account"><span className="account__avatar" title={user?.email || 'Your account'}>{(user?.email || 'U').slice(0, 1).toUpperCase()}</span><span className="account__identity"><strong>{user?.email || 'Your account'}</strong><small>Personal account</small></span><button type="button" className="account__logout" onClick={handleSignOut} aria-label="Sign out" title="Sign out"><LogOut size={16}/></button></div>
      </div>
    </div>
  );
}
