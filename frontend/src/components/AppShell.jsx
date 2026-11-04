import { useEffect, useState } from 'react';
import { Link, Navigate, Outlet, useLocation } from 'react-router-dom';
import { Menu, X } from 'lucide-react';
import RailContent from './RailContent.jsx';
import ModalDialog from './ModalDialog.jsx';
import Wordmark from './Wordmark.jsx';
import { SessionsProvider } from '../state/sessions.jsx';
import { useAuth } from '../state/auth.jsx';
import { useMedia } from '../state/useMedia.js';

function Shell() {
  const compact = useMedia('(max-width: 760px)');
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(() => {
    try { return localStorage.getItem('documind.sidebar') === 'collapsed'; } catch { return false; }
  });
  useEffect(() => { if (!compact) setDrawerOpen(false); }, [compact]);
  const closeDrawer = () => setDrawerOpen(false);
  const toggleRail = () => setCollapsed((current) => {
    const next = !current;
    try { localStorage.setItem('documind.sidebar', next ? 'collapsed' : 'expanded'); } catch { /* storage is optional */ }
    return next;
  });
  return (
    <div className={`app ${collapsed && !compact ? 'app--collapsed' : ''}`}>
      <a className="skip-link" href="#main">Skip to content</a>
      {compact ? <>
        <header className="topbar"><button type="button" className="icon-btn" aria-label="Open navigation" onClick={() => setDrawerOpen(true)}><Menu size={18}/></button><Link to="/stats" className="topbar__brand" aria-label="DocuMind, go to overview"><Wordmark/></Link><span className="topbar__context">INTELLIGENCE</span></header>
        <ModalDialog open={drawerOpen} onClose={closeDrawer} label="Navigation" variant="drawer"><button type="button" className="icon-btn modal__close" aria-label="Close navigation" onClick={closeDrawer}><X size={17}/></button><RailContent onNavigate={closeDrawer}/></ModalDialog>
      </> : <aside className="app__rail" aria-label="Workspace"><RailContent collapsed={collapsed} onToggleCollapse={toggleRail}/></aside>}
      <div className="app__body" id="main" tabIndex={-1}><Outlet/></div>
    </div>
  );
}
export default function AppShell() {
  const { token } = useAuth();
  const location = useLocation();
  if (!token) { const next = encodeURIComponent(location.pathname + location.search); return <Navigate to={`/login?next=${next}`} replace/>; }
  return <SessionsProvider><Shell/></SessionsProvider>;
}
