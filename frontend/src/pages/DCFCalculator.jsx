import React, { useState } from 'react';
import axios from 'axios';

export default function DCFCalculator() {
  const [ticker, setTicker] = useState('AAPL');
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);

  const [inputs, setInputs] = useState({
    starting_cf: 100000000,
    net_cash: 50000000,
    shares_outstanding: 15000000,
    terminal_growth: 0.025,
  });

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

      const res = await axios.post(`http://localhost:8000/api/dcf/calculate`, payload);
      setResults(res.data);
    } catch (err) {
      console.error(err);
    }
    setLoading(false);
  };

  return (
    <div>
      <h2 style={{ marginBottom: '2rem' }}>Advanced DCF Calculator</h2>
      
      <div className="grid-3" style={{ marginBottom: '2rem' }}>
        <div className="glass-panel">
          <label className="metric-label">Ticker</label>
          <input type="text" value={ticker} onChange={e => setTicker(e.target.value)} style={{ marginTop: '0.5rem' }} />
        </div>
        <div className="glass-panel">
          <label className="metric-label">Starting FCF (USD)</label>
          <input type="number" value={inputs.starting_cf} onChange={e => setInputs({...inputs, starting_cf: e.target.value})} style={{ marginTop: '0.5rem' }} />
        </div>
        <div className="glass-panel">
          <label className="metric-label">Shares Outstanding</label>
          <input type="number" value={inputs.shares_outstanding} onChange={e => setInputs({...inputs, shares_outstanding: e.target.value})} style={{ marginTop: '0.5rem' }} />
        </div>
      </div>

      <button className="btn-primary" onClick={handleCalculate} style={{ marginBottom: '2rem' }}>
        {loading ? 'Calculating...' : 'Run Valuation'}
      </button>

      {results && (
        <div className="grid-3">
          {Object.entries(results).map(([scenario, data]) => (
            <div key={scenario} className="glass-panel">
              <h3 className="metric-label">{scenario} Scenario</h3>
              <div className="metric-value" style={{ color: 'var(--accent-cyan)' }}>
                ${data.per_share?.toFixed(2) || 'N/A'}
              </div>
              <p className="metric-label" style={{ marginTop: '0.5rem' }}>Implied Share Price</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
