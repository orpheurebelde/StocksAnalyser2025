import React, { useState } from 'react';
import axios from 'axios';

export default function StockInfo() {
  const [ticker, setTicker] = useState('AAPL');
  const [info, setInfo] = useState(null);
  const [loading, setLoading] = useState(false);

  const fetchStock = async () => {
    setLoading(true);
    try {
      const res = await axios.get(`http://localhost:8000/api/stock/${ticker}/info`);
      setInfo(res.data.info);
    } catch (err) {
      console.error(err);
    }
    setLoading(false);
  };

  return (
    <div>
      <h2 style={{ marginBottom: '2rem' }}>Stock Analysis</h2>
      
      <div style={{ display: 'flex', gap: '1rem', marginBottom: '2rem' }}>
        <input 
          type="text" 
          value={ticker} 
          onChange={(e) => setTicker(e.target.value)}
          placeholder="Enter Ticker (e.g. AAPL)"
          style={{ maxWidth: '300px' }}
        />
        <button className="btn-primary" onClick={fetchStock}>
          {loading ? 'Analyzing...' : 'Analyze'}
        </button>
      </div>

      {info && (
        <div className="grid-3">
          <div className="glass-panel">
            <h3 className="metric-label">Market Cap</h3>
            <div className="metric-value">${(info.marketCap / 1e9).toFixed(2)}B</div>
          </div>
          <div className="glass-panel">
            <h3 className="metric-label">Trailing P/E</h3>
            <div className="metric-value">{info.trailingPE?.toFixed(2) || 'N/A'}</div>
          </div>
          <div className="glass-panel">
            <h3 className="metric-label">Forward P/E</h3>
            <div className="metric-value">{info.forwardPE?.toFixed(2) || 'N/A'}</div>
          </div>
          <div className="glass-panel" style={{ gridColumn: '1 / -1' }}>
            <h3 className="metric-label" style={{ marginBottom: '1rem' }}>Business Summary</h3>
            <p style={{ color: 'var(--text-secondary)' }}>{info.longBusinessSummary}</p>
          </div>
        </div>
      )}
    </div>
  );
}
