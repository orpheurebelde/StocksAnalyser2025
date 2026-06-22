import { useCallback, useEffect, useState } from 'react';
import { BrowserRouter as Router, Link, Navigate, Route, Routes } from 'react-router-dom';
import { Activity, Briefcase, Calculator, FileText, GitCompare, LayoutDashboard, LineChart, LogOut, Menu } from 'lucide-react';
import api from './api';
import Dashboard from './pages/Dashboard';
import DCFCalculator from './pages/DCFCalculator';
import Login from './pages/Login';
import MonteCarlo from './pages/MonteCarlo';
import Portfolio from './pages/Portfolio';
import QuarterEarnings from './pages/QuarterEarnings';
import StockComparison from './pages/StockComparison';
import StockInfo from './pages/StockInfo';

function AuthenticatedApp({ user, onLogout }) {
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);

  return (
    <div className="app-container">
      <aside className={`sidebar ${isSidebarCollapsed ? 'collapsed' : ''}`}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '1rem 0' }}>
          {!isSidebarCollapsed && (
            <div>
              <h1 className="text-gradient" style={{ fontSize: '1.8rem' }}>StocksAnalyser</h1>
              <p className="metric-label" style={{ marginTop: '0.5rem', fontSize: '0.8rem' }}>Next-Gen Intelligence</p>
            </div>
          )}
          <button
            onClick={() => setIsSidebarCollapsed(!isSidebarCollapsed)}
            style={{ background: 'transparent', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
            title="Toggle Sidebar"
          >
            <Menu size={24} />
          </button>
        </div>

        <nav style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
          <Link to="/" className="nav-link" title="Market Analysis">
            <LayoutDashboard size={20} style={{ flexShrink: 0 }} />
            {!isSidebarCollapsed && <span>Market Analysis</span>}
          </Link>
          <Link to="/stock" className="nav-link" title="Stock Analysis">
            <LineChart size={20} style={{ flexShrink: 0 }} />
            {!isSidebarCollapsed && <span>Stock Analysis</span>}
          </Link>
          <Link to="/monte-carlo" className="nav-link" title="Monte Carlo">
            <Activity size={20} style={{ flexShrink: 0 }} />
            {!isSidebarCollapsed && <span>Monte Carlo</span>}
          </Link>
          <Link to="/comparison" className="nav-link" title="Stock Comparison">
            <GitCompare size={20} style={{ flexShrink: 0 }} />
            {!isSidebarCollapsed && <span>Stock Comparison</span>}
          </Link>
          <Link to="/portfolio" className="nav-link" title="Portfolio Analysis">
            <Briefcase size={20} style={{ flexShrink: 0 }} />
            {!isSidebarCollapsed && <span>Portfolio Analysis</span>}
          </Link>
          <Link to="/dcf" className="nav-link" title="DCF Calculator">
            <Calculator size={20} style={{ flexShrink: 0 }} />
            {!isSidebarCollapsed && <span>DCF Calculator</span>}
          </Link>
          <Link to="/quarter-earnings" className="nav-link" title="Quarter Earnings">
            <FileText size={20} style={{ flexShrink: 0 }} />
            {!isSidebarCollapsed && <span>Quarter Earnings</span>}
          </Link>
        </nav>

        <div className={`sidebar-user ${isSidebarCollapsed ? 'collapsed' : ''}`}>
          {user.picture_url ? <img src={user.picture_url} alt="" referrerPolicy="no-referrer" /> : <div className="sidebar-user-fallback">{(user.name || user.email || '?')[0]}</div>}
          {!isSidebarCollapsed && (
            <div className="sidebar-user-copy">
              <strong>{user.name || 'Signed-in user'}</strong>
              <small>{user.email}{user.is_admin ? ' | Admin' : ''}</small>
            </div>
          )}
          <button onClick={onLogout} title="Sign out" aria-label="Sign out"><LogOut size={18} /></button>
        </div>
      </aside>

      <main className={`main-content ${isSidebarCollapsed ? 'expanded' : ''}`}>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/stock" element={<StockInfo />} />
          <Route path="/dcf" element={<DCFCalculator />} />
          <Route path="/monte-carlo" element={<MonteCarlo />} />
          <Route path="/comparison" element={<StockComparison />} />
          <Route path="/portfolio" element={<Portfolio />} />
          <Route path="/quarter-earnings" element={<QuarterEarnings />} />
          <Route path="/login" element={<Navigate to="/" replace />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
}

function AppRoutes() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const onAuthenticated = useCallback((authenticatedUser) => {
    setUser(authenticatedUser);
  }, []);

  useEffect(() => {
    let active = true;
    api.get('/api/auth/me')
      .then((response) => { if (active) setUser(response.data.user); })
      .catch(() => { if (active) setUser(null); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    const handleUnauthorized = () => setUser(null);
    window.addEventListener('auth:unauthorized', handleUnauthorized);
    return () => window.removeEventListener('auth:unauthorized', handleUnauthorized);
  }, []);

  const logout = async () => {
    try {
      await api.post('/api/auth/logout');
    } finally {
      window.google?.accounts?.id?.disableAutoSelect();
      setUser(null);
    }
  };

  if (loading) {
    return <div className="auth-loading"><div className="auth-loading-ring" /><span>Checking secure session...</span></div>;
  }
  if (!user) {
    return (
      <Routes>
        <Route path="/login" element={<Login onAuthenticated={onAuthenticated} />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    );
  }
  return <AuthenticatedApp user={user} onLogout={logout} />;
}

export default function App() {
  return <Router><AppRoutes /></Router>;
}
