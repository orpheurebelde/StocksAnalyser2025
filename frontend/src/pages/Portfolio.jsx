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
        <div className="grid-3">
          {data.summary.map((item, idx) => (
            <div key={idx} className="glass-panel">
              <h3 className="metric-label">{item.Symbol}</h3>
              <div className="metric-value" style={{ color: item["Unrealized Gain (%)"] > 0 ? 'var(--status-green)' : 'var(--status-red)' }}>
                {item["Unrealized Gain (%)"].toFixed(2)}%
              </div>
              <p className="metric-label" style={{ marginTop: '0.5rem' }}>
                Unrealized Gain: €{item["Unrealized Gain (€)"].toFixed(2)}
              </p>
              <p className="metric-label">Investment: €{item.Investment.toFixed(2)}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
