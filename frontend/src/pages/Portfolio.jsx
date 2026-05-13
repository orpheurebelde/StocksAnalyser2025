import React, { useState } from 'react';
import api from '../api';

export default function Portfolio() {
  const [file, setFile] = useState(null);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleUpload = async () => {
    if (!file) return;
    setLoading(true);
    setError('');
    
    const formData = new FormData();
    formData.append('file', file);
    
    try {
      const res = await api.post(`/api/portfolio/analyze`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      setData(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || err.message);
    }
    setLoading(false);
  };

  return (
    <div>
      <h2 style={{ marginBottom: '2rem' }}>Portfolio Analysis</h2>
      
      <div className="glass-panel" style={{ marginBottom: '2rem' }}>
        <input 
          type="file" 
          accept=".csv" 
          onChange={(e) => setFile(e.target.files[0])} 
          style={{ marginBottom: '1rem' }}
        />
        <br />
        <button className="btn-primary" onClick={handleUpload} disabled={loading || !file}>
          {loading ? 'Analyzing...' : 'Upload & Analyze CSV'}
        </button>
        {error && <p style={{ color: 'var(--status-red)', marginTop: '1rem' }}>{error}</p>}
      </div>

      {data && (
        <div style={{ marginTop: '2rem' }}>
          <h3 style={{ marginBottom: '1rem', color: 'var(--accent-cyan)' }}>Advanced Risk Metrics (1Y Historical)</h3>
          {data.metrics && data.metrics.length > 0 ? (
            <div className="grid-4" style={{ marginBottom: '2rem' }}>
              {data.metrics.map((m, idx) => (
                <div key={idx} className="glass-panel">
                  <div className="metric-label">{m.Metric}</div>
                  <div className="metric-value">{m.Value}</div>
                </div>
              ))}
            </div>
          ) : (
            <p style={{ color: 'var(--text-secondary)' }}>Risk metrics could not be calculated.</p>
          )}

          <h3 style={{ marginBottom: '1rem', color: 'var(--accent-cyan)' }}>Compiled Stock Summary</h3>
          <div className="glass-panel" style={{ overflowX: 'auto', marginBottom: '2rem' }}>
            <table style={{ width: '100%', textAlign: 'left', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border-color)' }}>
                  <th style={{ padding: '0.5rem' }}>Symbol</th>
                  <th style={{ padding: '0.5rem' }}>Quantity</th>
                  <th style={{ padding: '0.5rem' }}>Investment (€)</th>
                  <th style={{ padding: '0.5rem' }}>Market Value (€)</th>
                  <th style={{ padding: '0.5rem' }}>Unrealized Gain (€)</th>
                  <th style={{ padding: '0.5rem' }}>Unrealized Gain (%)</th>
                </tr>
              </thead>
              <tbody>
                {data.summary.map((row, idx) => (
                  <tr key={idx} style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                    <td style={{ padding: '0.5rem' }}>{row.Symbol}</td>
                    <td style={{ padding: '0.5rem' }}>{row.Quantity}</td>
                    <td style={{ padding: '0.5rem' }}>{row.Investment.toFixed(2)}</td>
                    <td style={{ padding: '0.5rem' }}>{row['Market Value'].toFixed(2)}</td>
                    <td style={{ padding: '0.5rem', color: row['Unrealized Gain (€)'] > 0 ? 'var(--status-green)' : 'var(--status-red)' }}>
                      {row['Unrealized Gain (€)'].toFixed(2)}
                    </td>
                    <td style={{ padding: '0.5rem', color: row['Unrealized Gain (%)'] > 0 ? 'var(--status-green)' : 'var(--status-red)' }}>
                      {row['Unrealized Gain (%)'].toFixed(2)}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
