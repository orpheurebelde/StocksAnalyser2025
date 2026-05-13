import React, { useEffect, useState } from 'react';
import axios from 'axios';

export default function Dashboard() {
  const [vix, setVix] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    axios.get('http://localhost:8000/api/market/vix')
      .then(res => {
        setVix(res.data.vix);
        setLoading(false);
      })
      .catch(err => {
        console.error(err);
        setLoading(false);
      });
  }, []);

  return (
    <div>
      <h2 style={{ marginBottom: '2rem' }}>Market Dashboard</h2>
      
      <div className="grid-3">
        <div className="glass-panel">
          <h3 className="metric-label">Volatility Index (VIX)</h3>
          {loading ? (
            <p>Loading...</p>
          ) : (
            <div className="metric-value" style={{ color: vix > 20 ? 'var(--status-red)' : 'var(--status-green)' }}>
              {vix ? vix.toFixed(2) : 'N/A'}
            </div>
          )}
          <p className="metric-label" style={{ marginTop: '0.5rem' }}>
            {vix > 28 ? 'Fear Zone' : vix < 15 ? 'Greed Zone' : 'Neutral Zone'}
          </p>
        </div>

        <div className="glass-panel">
          <h3 className="metric-label">Market Sentiment</h3>
          <div className="metric-value" style={{ color: 'var(--accent-blue)' }}>Bullish</div>
          <p className="metric-label" style={{ marginTop: '0.5rem' }}>AAII Survey Data</p>
        </div>
      </div>
    </div>
  );
}
