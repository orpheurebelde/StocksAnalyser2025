import { useCallback, useEffect, useRef, useState } from 'react';
import { BrowserRouter as Router, Navigate, NavLink, Route, Routes } from 'react-router-dom';
import { Activity, Briefcase, Calculator, ChevronLeft, ChevronRight, FileText, GitCompare, LayoutDashboard, LineChart, LogOut, Menu, UserCircle, X } from 'lucide-react';
import api from './api';
import Dashboard from './pages/Dashboard';
import DCFCalculator from './pages/DCFCalculator';
import Login from './pages/Login';
import MonteCarlo from './pages/MonteCarlo';
import Portfolio from './pages/Portfolio';
import Profile from './pages/Profile';
import QuarterEarnings from './pages/QuarterEarnings';
import StockComparison from './pages/StockComparison';
import StockInfo from './pages/StockInfo';

function AuthenticatedApp({ user, onLogout }) {
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(true);
  const [isMobileOpen, setIsMobileOpen] = useState(false);
  const showLabels = !isSidebarCollapsed || isMobileOpen;
  const navigation = [
    { to: '/', label: 'Market Analysis', icon: LayoutDashboard, end: true },
    { to: '/stock', label: 'Stock Analysis', icon: LineChart },
    { to: '/monte-carlo', label: 'Monte Carlo', icon: Activity },
    { to: '/comparison', label: 'Stock Comparison', icon: GitCompare },
    { to: '/portfolio', label: 'Portfolio Analysis', icon: Briefcase },
    { to: '/dcf', label: 'DCF Calculator', icon: Calculator },
    { to: '/quarter-earnings', label: 'Quarter Earnings', icon: FileText },
    { to: '/profile', label: 'Profile', icon: UserCircle },
  ];

  return (
    <div className="app-container">
      <button className="mobile-menu-trigger" onClick={() => setIsMobileOpen((open) => !open)} aria-label={isMobileOpen ? 'Close navigation' : 'Open navigation'} aria-expanded={isMobileOpen}>
        {isMobileOpen ? <X size={22} /> : <Menu size={22} />}
      </button>
      {isMobileOpen && <button className="sidebar-backdrop" aria-label="Close navigation" onClick={() => setIsMobileOpen(false)} />}
      <aside className={`sidebar ${isSidebarCollapsed ? 'collapsed' : ''} ${isMobileOpen ? 'mobile-open' : ''}`}>
        <div className="sidebar-header">
          {showLabels ? (
            <div className="sidebar-brand-copy">
              <h1 className="text-gradient">StocksAnalyser</h1>
              <p>Market intelligence</p>
            </div>
          ) : <div className="sidebar-brand-mark" aria-label="StocksAnalyser">SA</div>}
          <button
            className="sidebar-collapse-button"
            onClick={() => setIsSidebarCollapsed((collapsed) => !collapsed)}
            title={isSidebarCollapsed ? 'Expand menu' : 'Collapse menu'}
            aria-label={isSidebarCollapsed ? 'Expand menu' : 'Collapse menu'}
          >
            {isSidebarCollapsed ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
          </button>
        </div>

        <nav className="sidebar-navigation">
          <span className="sidebar-section-label">{showLabels ? 'Workspace' : '•••'}</span>
          {navigation.map(({ to, label, icon: Icon, end }) => (
            <NavLink key={to} to={to} end={end} className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`} title={isSidebarCollapsed && !isMobileOpen ? label : undefined} onClick={() => setIsMobileOpen(false)}>
              <Icon size={20} />
              {showLabels && <span>{label}</span>}
              {!showLabels && <span className="nav-tooltip">{label}</span>}
            </NavLink>
          ))}
        </nav>

        <div className={`sidebar-user ${isSidebarCollapsed ? 'collapsed' : ''}`}>
          {user.picture_url ? <img src={user.picture_url} alt="" referrerPolicy="no-referrer" /> : <div className="sidebar-user-fallback">{(user.name || user.email || '?')[0]}</div>}
          {showLabels && (
            <div className="sidebar-user-copy">
              <strong>{user.name || 'Signed-in user'}</strong>
              <small>{user.email}{user.is_admin ? ' | Admin' : ''}</small>
            </div>
          )}
          <button onClick={onLogout} title="Logout" aria-label="Logout">
            <LogOut size={18} /> {showLabels && <span>Logout</span>}
          </button>
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
          <Route path="/profile" element={<Profile user={user} onLogout={onLogout} />} />
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
  const authChangedRef = useRef(false);

  const onAuthenticated = useCallback((authenticatedUser) => {
    authChangedRef.current = true;
    setUser(authenticatedUser);
    setLoading(false);
  }, []);

  useEffect(() => {
    let active = true;
    api.get('/api/auth/me')
      .then((response) => { if (active && !authChangedRef.current) setUser(response.data.user); })
      .catch(() => { if (active && !authChangedRef.current) setUser(null); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    const handleUnauthorized = () => {
      authChangedRef.current = true;
      setUser(null);
      setLoading(false);
    };
    window.addEventListener('auth:unauthorized', handleUnauthorized);
    return () => window.removeEventListener('auth:unauthorized', handleUnauthorized);
  }, []);

  const logout = async () => {
    authChangedRef.current = true;
    try {
      await api.post('/api/auth/logout');
    } finally {
      window.google?.accounts?.id?.disableAutoSelect();
      setUser(null);
    }
  };

  if (loading) {
    return (
      <Routes>
        <Route path="*" element={<Login onAuthenticated={onAuthenticated} sessionChecking />} />
      </Routes>
    );
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
