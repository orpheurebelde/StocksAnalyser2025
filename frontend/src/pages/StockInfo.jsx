import React, { useState } from 'react';
import api from '../api';
import ReactMarkdown from 'react-markdown';

export default function StockInfo() {
  const [ticker, setTicker] = useState('AAPL');
  const [info, setInfo] = useState(null);
  const [loading, setLoading] = useState(false);
  const [aiAnalysis, setAiAnalysis] = useState('');
  const [aiLoading, setAiLoading] = useState(false);
  const [aiPrompt, setAiPrompt] = useState('Analyze the fundamentals of this stock and give me a buy/sell/hold recommendation.');
  const [error, setError] = useState('');

  const fetchStock = async () => {
    setLoading(true);
    setError('');
    setInfo(null);
    setAiAnalysis('');
    try {
      const res = await api.get(`/api/stock/${ticker}/info`);
      setInfo(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || err.message);
    }
    setLoading(false);
  };

  const fetchAiAnalysis = async () => {
    setAiLoading(true);
    try {
      const res = await api.post(`/api/stock/${ticker}/ai-analysis`, { prompt: aiPrompt });
      setAiAnalysis(res.data.analysis);
    } catch (err) {
      setAiAnalysis(`Error fetching AI analysis: ${err.response?.data?.detail || err.message}`);
    }
    setAiLoading(false);
  };

  return (
    <div>
      <h2 style={{ marginBottom: '2rem' }}>Stock Analysis & AI Intelligence</h2>
      
      <div className="glass-panel" style={{ display: 'flex', gap: '1rem', marginBottom: '2rem', alignItems: 'center' }}>
        <input 
          type="text" 
          value={ticker} 
          onChange={(e) => setTicker(e.target.value)}
          placeholder="Enter Ticker (e.g. AAPL)"
          style={{ maxWidth: '300px' }}
        />
        <button className="btn-primary" onClick={fetchStock} disabled={loading}>
          {loading ? 'Fetching...' : 'Analyze Fundamentals'}
        </button>
      </div>

      {error && <p style={{ color: 'var(--status-red)', marginBottom: '2rem' }}>{error}</p>}

      {info && (
        <>
          <div className="grid-3" style={{ marginBottom: '2rem' }}>
            <div className="glass-panel">
              <h3 className="metric-label">Company</h3>
              <div className="metric-value" style={{ fontSize: '1.5rem' }}>{info.shortName || ticker}</div>
              <p className="metric-label" style={{ marginTop: '0.5rem' }}>Sector: {info.sector}</p>
            </div>
            <div className="glass-panel">
              <h3 className="metric-label">Market Cap</h3>
              <div className="metric-value">${(info.marketCap / 1e9).toFixed(2)}B</div>
            </div>
            <div className="glass-panel">
              <h3 className="metric-label">Current Price</h3>
              <div className="metric-value" style={{ color: 'var(--accent-cyan)' }}>${info.currentPrice?.toFixed(2) || 'N/A'}</div>
              <p className="metric-label" style={{ marginTop: '0.5rem' }}>52W Range: ${info.fiftyTwoWeekLow} - ${info.fiftyTwoWeekHigh}</p>
            </div>
            <div className="glass-panel">
              <h3 className="metric-label">Trailing P/E</h3>
              <div className="metric-value">{info.trailingPE?.toFixed(2) || 'N/A'}</div>
            </div>
            <div className="glass-panel">
              <h3 className="metric-label">Forward P/E</h3>
              <div className="metric-value">{info.forwardPE?.toFixed(2) || 'N/A'}</div>
            </div>
            <div className="glass-panel">
              <h3 className="metric-label">Profit Margin</h3>
              <div className="metric-value" style={{ color: info.profitMargins > 0 ? 'var(--status-green)' : 'var(--status-red)' }}>
                {info.profitMargins ? (info.profitMargins * 100).toFixed(2) + '%' : 'N/A'}
              </div>
            </div>
          </div>

          <div className="glass-panel" style={{ marginBottom: '2rem' }}>
            <h3 className="metric-label" style={{ marginBottom: '1rem', fontSize: '1.2rem', color: 'var(--accent-blue)' }}>Ask Mistral AI</h3>
            <textarea 
              value={aiPrompt}
              onChange={e => setAiPrompt(e.target.value)}
              style={{ width: '100%', height: '80px', background: 'rgba(0,0,0,0.3)', color: 'white', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '1rem', marginBottom: '1rem', fontFamily: 'var(--font-body)' }}
            />
            <button className="btn-primary" onClick={fetchAiAnalysis} disabled={aiLoading}>
              {aiLoading ? 'Mistral is analyzing...' : 'Generate AI Report'}
            </button>

            {aiAnalysis && (
              <div style={{ marginTop: '2rem', padding: '1.5rem', background: 'rgba(0,0,0,0.4)', borderRadius: '8px', borderLeft: '4px solid var(--accent-purple)' }}>
                <ReactMarkdown>{aiAnalysis}</ReactMarkdown>
              </div>
            )}
          </div>
          
          <div className="glass-panel">
            <h3 className="metric-label" style={{ marginBottom: '1rem' }}>Business Summary</h3>
            <p style={{ color: 'var(--text-secondary)' }}>{info.longBusinessSummary}</p>
          </div>
        </>
      )}
    </div>
  );
}
