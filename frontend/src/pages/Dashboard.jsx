import React, { useEffect, useState } from 'react';
import api from '../api';

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    api.get('/api/market/analysis')
      .then(res => {
        setData(res.data);
        setLoading(false);
      })
      .catch(err => {
        console.error(err);
        setError(err.response?.data?.detail || err.message);
        setLoading(false);
      });
  }, []);

  return (
    <div>
      <h2 style={{ marginBottom: '2rem' }}>Market Analysis & Dashboard</h2>
      
      {loading ? <p>Loading Market Data...</p> : error ? <p style={{ color: 'var(--status-red)' }}>Error: {error}</p> : data && (
        <>
          <div className="grid-3" style={{ marginBottom: '2rem' }}>
            <div className="glass-panel">
              <h3 className="metric-label">Volatility Index (VIX)</h3>
              <div className="metric-value" style={{ color: data.vix > 20 ? 'var(--status-red)' : 'var(--status-green)' }}>
                {data.vix ? data.vix.toFixed(2) : 'N/A'}
              </div>
              <p className="metric-label" style={{ marginTop: '0.5rem' }}>
                {data.vix > 28 ? 'Fear Zone' : data.vix < 15 ? 'Greed Zone' : 'Neutral Zone'}
              </p>
            </div>
          </div>

          <div className="grid-3">
            {Object.entries(data.indices).map(([name, info]) => (
              <div key={name} className="glass-panel">
                <h3 className="metric-value" style={{ color: 'var(--accent-cyan)', marginBottom: '1rem' }}>{name}</h3>
                
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                  <span className="metric-label">Current Price</span>
                  <span style={{ fontWeight: 'bold' }}>${info.price.toLocaleString(undefined, {minimumFractionDigits: 2})}</span>
                </div>
                
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                  <span className="metric-label">52W Range</span>
                  <span>${info.low_52w.toFixed(0)} - ${info.high_52w.toFixed(0)}</span>
                </div>
                
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                  <span className="metric-label">RSI (14)</span>
                  <span style={{ color: info.rsi > 70 ? 'var(--status-red)' : info.rsi < 30 ? 'var(--status-green)' : 'white' }}>
                    {info.rsi.toFixed(2)}
                  </span>
                </div>
                
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                  <span className="metric-label">YTD Return</span>
                  <span style={{ color: info.ytd > 0 ? 'var(--status-green)' : 'var(--status-red)' }}>
                    {info.ytd > 0 ? '+' : ''}{info.ytd.toFixed(2)}%
                  </span>
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                  <span className="metric-label">1-Year Return</span>
                  <span style={{ color: info.ret_1y > 0 ? 'var(--status-green)' : 'var(--status-red)' }}>
                    {info.ret_1y > 0 ? '+' : ''}{info.ret_1y.toFixed(2)}%
                  </span>
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
