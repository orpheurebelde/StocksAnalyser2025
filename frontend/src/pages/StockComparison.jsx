import React, { useState } from 'react';
import axios from 'axios';

export default function StockComparison() {
  const [tickers, setTickers] = useState('');
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleCompare = async () => {
    if (!tickers.trim()) return;
    setLoading(true);
    
    const tickerList = tickers.split(',').map(t => t.trim().toUpperCase());
    try {
      const res = await axios.post('http://localhost:8000/api/comparison/compare', { tickers: tickerList });
      setData(res.data);
    } catch (err) {
      console.error(err);
    }
    setLoading(false);
  };

  return (
    <div>
      <h2 style={{ marginBottom: '2rem' }}>Stock Comparison</h2>
      
      <div className="glass-panel" style={{ marginBottom: '2rem' }}>
        <input 
          type="text" 
          value={tickers} 
          onChange={e => setTickers(e.target.value)} 
          placeholder="Enter tickers separated by commas (e.g. AAPL, MSFT, TSLA)"
          style={{ marginBottom: '1rem' }}
        />
        <br />
        <button className="btn-primary" onClick={handleCompare} disabled={loading}>
          {loading ? 'Comparing...' : 'Compare Stocks'}
        </button>
      </div>

      {data && (
        <div style={{ display: 'flex', gap: '1rem', overflowX: 'auto' }}>
          {Object.entries(data).map(([ticker, info]) => (
            <div key={ticker} className="glass-panel" style={{ minWidth: '300px', flex: 1 }}>
              <h3 className="metric-value" style={{ marginBottom: '1rem', color: 'var(--accent-cyan)' }}>{ticker}</h3>
              {info.error ? (
                <p style={{ color: 'var(--status-red)' }}>{info.error}</p>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                  {Object.entries(info).map(([metric, val]) => (
                    <div key={metric} style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.25rem' }}>
                      <span className="metric-label">{metric}</span>
                      <span>{typeof val === 'number' ? (val > 1000 ? val.toLocaleString() : val.toFixed(2)) : (val || 'N/A')}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
