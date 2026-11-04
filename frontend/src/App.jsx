import { BrowserRouter, Link, Navigate, Route, Routes } from 'react-router-dom';
import { AuthProvider } from './state/auth.jsx';
import { ThemeProvider } from './state/theme.jsx';
import { ScopeProvider } from './state/scope.jsx';
import AppShell from './components/AppShell.jsx';
import Login from './pages/Login.jsx';
import Chat from './pages/Chat.jsx';
import Documents from './pages/Documents.jsx';
import Stats from './pages/Stats.jsx';
import { useTitle } from './state/useTitle.js';

function NotFound() {
  useTitle('Page not found');
  return (
    <main className="page">
      <div className="empty">
        <h1>Page not found</h1>
        <p>This address does not match a page in DocuMind.</p>
        <Link className="btn" to="/chat">Go to chat</Link>
      </div>
    </main>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <ThemeProvider>
        <AuthProvider>
          <ScopeProvider>
            <Routes>
              <Route path="/login" element={<Login />} />
              <Route element={<AppShell />}>
                <Route path="/chat/:sessionId?" element={<Chat />} />
                <Route path="/documents" element={<Documents />} />
                <Route path="/stats" element={<Stats />} />
                <Route path="*" element={<NotFound />} />
              </Route>
              <Route path="/" element={<Navigate to="/stats" replace />} />
            </Routes>
          </ScopeProvider>
        </AuthProvider>
      </ThemeProvider>
    </BrowserRouter>
  );
}
