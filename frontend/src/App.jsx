import React from 'react';
import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';
import { LineChart, LayoutDashboard, Calculator, Info } from 'lucide-react';
import Dashboard from './pages/Dashboard';
import StockInfo from './pages/StockInfo';
import DCFCalculator from './pages/DCFCalculator';

function App() {
  return (
    <Router>
      <div className="app-container">
        <aside className="sidebar">
          <div style={{ padding: '1rem 0' }}>
            <h1 className="text-gradient">StocksAnalyser</h1>
            <p className="metric-label" style={{ marginTop: '0.5rem' }}>Next-Gen Intelligence</p>
          </div>
          
          <nav style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            <Link to="/" className="nav-link active">
              <LayoutDashboard size={20} />
              Dashboard
            </Link>
            <Link to="/stock" className="nav-link">
              <LineChart size={20} />
              Stock Analysis
            </Link>
            <Link to="/dcf" className="nav-link">
              <Calculator size={20} />
              DCF Calculator
            </Link>
          </nav>
        </aside>

        <main className="main-content">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/stock" element={<StockInfo />} />
            <Route path="/dcf" element={<DCFCalculator />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

export default App;
