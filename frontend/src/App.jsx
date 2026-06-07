import { useState } from 'react';
import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';
import { LineChart, LayoutDashboard, Calculator, Activity, GitCompare, Briefcase, Menu, FileText } from 'lucide-react';
import Dashboard from './pages/Dashboard';
import StockInfo from './pages/StockInfo';
import DCFCalculator from './pages/DCFCalculator';
import MonteCarlo from './pages/MonteCarlo';
import StockComparison from './pages/StockComparison';
import Portfolio from './pages/Portfolio';
import QuarterEarnings from './pages/QuarterEarnings';

function App() {
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);

  return (
    <Router>
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
          </Routes>
        </main>
      </div>
    </Router>
  );
}

export default App;
