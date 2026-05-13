import React, { useState } from 'react';
import api from '../api';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

export default function DCFCalculator() {
  const [ticker, setTicker] = useState('AAPL');
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [fetching, setFetching] = useState(false);

  const [inputs, setInputs] = useState({
    starting_cf: 100000000,
    net_cash: 50000000,
    shares_outstanding: 15000000,
    terminal_growth: 0.025,
  });

  const fetchStockData = async () => {
    if (!ticker.trim()) return;
    setFetching(true);
    try {
      const res = await api.get(`/api/stock/${ticker.toUpperCase()}/info`);
      const info = res.data;
      
      const fcf = info.freeCashflow || 0;
      const tCash = info.totalCash || 0;
      const tDebt = info.totalDebt || 0;
      const shares = info.sharesOutstanding || info.impliedSharesOutstanding || 0;
      
      setInputs({
        ...inputs,
        starting_cf: fcf,
        net_cash: tCash - tDebt,
        shares_outstanding: shares
      });
    } catch (err) {
      console.error("Failed to preload:", err);
      alert("Failed to preload stock data. Ensure the ticker is valid.");
    }
    setFetching(false);
  };

  const handleCalculate = async () => {
    setLoading(true);
    try {
      const payload = {
        ticker,
        starting_cf: Number(inputs.starting_cf),
        net_cash: Number(inputs.net_cash),
        shares_outstanding: Number(inputs.shares_outstanding),
        growth_rates: [0.15, 0.12, 0.10, 0.08, 0.05], // 5 year multi-stage
        discount_rates: { Bull: 0.08, Base: 0.09, Bear: 0.10 },
        terminal_growth: Number(inputs.terminal_growth)
      };

      const res = await api.post(`/api/dcf/calculate`, payload);
      setResults(res.data);
    } catch (err) {
      console.error(err);
    }
    setLoading(false);
  };

  const getChartData = () => {
    if (!results || !results.Base) return [];
    const base = results.Base;
    const data = base.pv_years.map((val, idx) => ({
      name: `Year ${idx + 1}`,
      PV: val
    }));
    data.push({ name: 'Terminal', PV: base.pv_terminal });
    return data;
  };

  return (
    <div>
      <h2 style={{ marginBottom: '2rem' }}>📉 Advanced DCF Calculator</h2>
      
      <div className="grid-3" style={{ marginBottom: '2rem' }}>
        <div className="glass-panel" style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
          <label className="metric-label">Ticker</label>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <input type="text" value={ticker} onChange={e => setTicker(e.target.value)} style={{ flex: 1, marginTop: 0 }} />
            <button className="btn-primary" onClick={fetchStockData} disabled={fetching} style={{ padding: '0.5rem' }}>
              {fetching ? '...' : 'Preload'}
            </button>
          </div>
        </div>
        <div className="glass-panel">
          <label className="metric-label">Starting FCF (USD)</label>
          <input type="number" value={inputs.starting_cf} onChange={e => setInputs({...inputs, starting_cf: e.target.value})} style={{ marginTop: '0.5rem' }} />
        </div>
        <div className="glass-panel">
          <label className="metric-label">Net Cash (USD)</label>
          <input type="number" value={inputs.net_cash} onChange={e => setInputs({...inputs, net_cash: e.target.value})} style={{ marginTop: '0.5rem' }} />
        </div>
        <div className="glass-panel">
          <label className="metric-label">Shares Outstanding</label>
          <input type="number" value={inputs.shares_outstanding} onChange={e => setInputs({...inputs, shares_outstanding: e.target.value})} style={{ marginTop: '0.5rem' }} />
        </div>
        <div className="glass-panel">
          <label className="metric-label">Terminal Growth Rate (e.g. 0.025)</label>
          <input type="number" step="0.001" value={inputs.terminal_growth} onChange={e => setInputs({...inputs, terminal_growth: e.target.value})} style={{ marginTop: '0.5rem' }} />
        </div>
      </div>

      <button className="btn-primary" onClick={handleCalculate} style={{ marginBottom: '2rem' }}>
        {loading ? 'Calculating...' : 'Run Valuation'}
      </button>

      {results && (
        <>
          <div className="grid-3" style={{ marginBottom: '2rem' }}>
            {Object.entries(results).map(([scenario, data]) => (
              <div key={scenario} className="glass-panel">
                <h3 className="metric-label">{scenario} Scenario</h3>
                <div className="metric-value" style={{ color: 'var(--accent-cyan)' }}>
                  ${data.per_share?.toFixed(2) || 'N/A'}
                </div>
                <p className="metric-label" style={{ marginTop: '0.5rem' }}>Implied Share Price</p>
                <div style={{ marginTop: '1rem', borderTop: '1px solid rgba(255,255,255,0.1)', paddingTop: '1rem' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.9rem' }}>
                    <span>Enterprise Value:</span>
                    <span>${(data.ev / 1e9).toFixed(2)}B</span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.9rem' }}>
                    <span>Equity Value:</span>
                    <span>${(data.equity / 1e9).toFixed(2)}B</span>
                  </div>
                </div>
              </div>
            ))}
          </div>

          <div className="glass-panel">
            <h3 className="metric-label" style={{ marginBottom: '1rem' }}>Present Value Breakdown (Base Scenario)</h3>
            <div style={{ height: '400px', width: '100%' }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={getChartData()} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                  <XAxis dataKey="name" stroke="rgba(255,255,255,0.5)" />
                  <YAxis stroke="rgba(255,255,255,0.5)" tickFormatter={(val) => `$${(val/1e9).toFixed(1)}B`} />
                  <Tooltip 
                    contentStyle={{ backgroundColor: 'rgba(0,0,0,0.8)', border: '1px solid var(--border-color)', borderRadius: '8px' }}
                    formatter={(val) => [`$${(val/1e9).toFixed(2)}B`, 'Present Value']}
                  />
                  <Bar dataKey="PV" fill="var(--accent-cyan)" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
