import React, { useState } from 'react';
import axios from 'axios';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

export default function MonteCarlo() {
  const [ticker, setTicker] = useState('AAPL');
  const [inputs, setInputs] = useState({
    n_simulations: 1000,
    total_days: 252,
    log_normal: true,
    volatility: ''
  });
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleSimulate = async () => {
    if (!ticker.trim()) return;
    setLoading(true);
    
    try {
      const payload = {
        ticker: ticker.toUpperCase(),
        n_simulations: Number(inputs.n_simulations),
        total_days: Number(inputs.total_days),
        log_normal: inputs.log_normal,
        volatility: inputs.volatility ? Number(inputs.volatility) / 100 : null
      };

      const res = await axios.post('http://localhost:8000/api/monte-carlo/simulate', payload);
      setData(res.data);
    } catch (err) {
      console.error(err);
    }
    setLoading(false);
  };

  return (
    <div>
      <h2 style={{ marginBottom: '2rem' }}>Monte Carlo Simulations</h2>
      
      <div className="grid-3" style={{ marginBottom: '2rem' }}>
        <div className="glass-panel">
          <label className="metric-label">Ticker</label>
          <input type="text" value={ticker} onChange={e => setTicker(e.target.value)} />
        </div>
        <div className="glass-panel">
          <label className="metric-label">Number of Simulations</label>
          <input type="number" value={inputs.n_simulations} onChange={e => setInputs({...inputs, n_simulations: e.target.value})} />
        </div>
        <div className="glass-panel">
          <label className="metric-label">Projection Days</label>
          <input type="number" value={inputs.total_days} onChange={e => setInputs({...inputs, total_days: e.target.value})} />
        </div>
      </div>
      
      <button className="btn-primary" onClick={handleSimulate} disabled={loading} style={{ marginBottom: '2rem' }}>
        {loading ? 'Simulating...' : 'Run Simulation'}
      </button>

      {data && (
        <>
          <div className="grid-3" style={{ marginBottom: '2rem' }}>
            <div className="glass-panel">
              <h3 className="metric-label">Current Price</h3>
              <div className="metric-value">${data.current_price.toFixed(2)}</div>
            </div>
            <div className="glass-panel">
              <h3 className="metric-label">Mean Projected Price</h3>
              <div className="metric-value" style={{ color: 'var(--accent-blue)' }}>${data.mean_price.toFixed(2)}</div>
            </div>
            <div className="glass-panel">
              <h3 className="metric-label">Probability of Increase</h3>
              <div className="metric-value" style={{ color: data.prob_increase > 50 ? 'var(--status-green)' : 'var(--status-red)' }}>
                {data.prob_increase.toFixed(2)}%
              </div>
            </div>
            <div className="glass-panel">
              <h3 className="metric-label">Bull Case (95th Percentile)</h3>
              <div className="metric-value" style={{ color: 'var(--status-green)' }}>${data.p95_price.toFixed(2)}</div>
            </div>
            <div className="glass-panel">
              <h3 className="metric-label">Bear Case (5th Percentile)</h3>
              <div className="metric-value" style={{ color: 'var(--status-red)' }}>${data.p5_price.toFixed(2)}</div>
            </div>
          </div>

          <div className="glass-panel" style={{ height: '500px' }}>
            <h3 className="metric-label" style={{ marginBottom: '1rem' }}>Simulated Price Paths (Percentiles)</h3>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={data.chart_data} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border-color)" />
                <XAxis dataKey="day" stroke="var(--text-secondary)" />
                <YAxis stroke="var(--text-secondary)" domain={['dataMin', 'dataMax']} />
                <Tooltip contentStyle={{ backgroundColor: 'var(--bg-secondary)', border: '1px solid var(--border-color)' }} />
                <Line type="monotone" dataKey="p95" stroke="var(--status-green)" strokeWidth={2} dot={false} name="95th Pctl" />
                <Line type="monotone" dataKey="mean" stroke="var(--accent-blue)" strokeWidth={3} dot={false} name="Mean" />
                <Line type="monotone" dataKey="p5" stroke="var(--status-red)" strokeWidth={2} dot={false} name="5th Pctl" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </>
      )}
    </div>
  );
}
