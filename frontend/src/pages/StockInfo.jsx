import React, { useState } from 'react';
import api from '../api';
import ReactMarkdown from 'react-markdown';

export default function StockInfo() {
  const [ticker, setTicker] = useState('AAPL');
  const [info, setInfo] = useState(null);
  const [priceAction, setPriceAction] = useState(null);
  const [loading, setLoading] = useState(false);
  
  const [aiAnalysis, setAiAnalysis] = useState('');
  const [aiLoading, setAiLoading] = useState(false);
  const [aiPrompt, setAiPrompt] = useState('');
  const [error, setError] = useState('');

  const fetchStock = async () => {
    setLoading(true);
    setError('');
    setInfo(null);
    setPriceAction(null);
    setAiAnalysis('');
    try {
      const [infoRes, paRes] = await Promise.all([
        api.get(`/api/stock/${ticker.toUpperCase()}/info`),
        api.get(`/api/stock/${ticker.toUpperCase()}/price-action`)
      ]);
      setInfo(infoRes.data);
      setPriceAction(paRes.data);
    } catch (err) {
      setError(err.response?.data?.detail || err.message);
    }
    setLoading(false);
  };

  const cleanAiOutput = (text, currentPrice) => {
    if (!currentPrice) return text;
    // Basic regex to replace hallucinated prices with the real current price
    return text.replace(/(\$?)\d+(?:\.\d{1,2})?/g, (match, sign) => {
      // If it looks like a stock price and is near the current price, or if it's explicitly labeled "Current Price"
      return match; // simplified, just return the text for now
    });
  };

  const handleAiGeneral = async () => {
    if (!info) return;
    const prompt = `You are a professional equity analyst. Write a deep analysis using ONLY the following structured data:
    
    - Company: ${info.shortName || ticker}
    - Sector: ${info.sector}
    - Market Cap: $${(info.marketCap / 1e9).toFixed(2)}B
    - Current Price: $${info.currentPrice}
    - P/E (TTM): ${info.trailingPE}
    - Forward P/E: ${info.forwardPE}
    - Revenue: $${(info.totalRevenue / 1e9).toFixed(2)}B
    - Net Income: $${(info.netIncomeToCommon / 1e9).toFixed(2)}B
    - Free Cash Flow: $${(info.freeCashflow / 1e9).toFixed(2)}B
    - Shares Outstanding: ${info.sharesOutstanding}
    
    Structure the analysis:
    1. **Executive Summary**
    2. **Valuation**
    3. **Financial Health**
    4. **Growth Potential**
    5. **Risks**
    6. **Fair Value vs Current Price**
    7. **12-Month Target & Recommendation**`;
    
    setAiPrompt(prompt);
    await fetchAiAnalysis(prompt);
  };

  const handleAiDCF = async () => {
    if (!info) return;
    const prompt = `You are a professional equity analyst. Based on the financial metrics retrieved earlier from Yahoo Finance and current market expectations for ${info.shortName || ticker} (${ticker.toUpperCase()}), generate a realistic 5-year DCF valuation.

    Use the following data as a baseline:
    - Company: ${info.shortName || ticker}
    - Sector: ${info.sector}
    - Market Cap: $${(info.marketCap / 1e9).toFixed(2)}B
    - Current Price: $${info.currentPrice}
    - Revenue (TTM): $${(info.totalRevenue / 1e9).toFixed(2)}B
    - Free Cash Flow (TTM): $${(info.freeCashflow / 1e9).toFixed(2)}B
    - Shares Outstanding: ${info.sharesOutstanding}
    - Total Debt: $${(info.totalDebt / 1e9).toFixed(2)}B
    - Total Cash: $${(info.totalCash / 1e9).toFixed(2)}B
    - EPS Growth: ${info.earningsQuarterlyGrowth}
    - Revenue Growth: ${info.revenueGrowth}

    DCF guidelines:
    1. Use the latest reported revenue as the starting point.
    2. Run a 5-year DCF and clearly show PV of cash flows and terminal value.
    3. Calculate the implied share price.
    
    Emphasize realism, forward-looking assumptions, and avoid overly conservative or overly aggressive inputs.`;
    
    setAiPrompt(prompt);
    await fetchAiAnalysis(prompt);
  };

  const fetchAiAnalysis = async (promptToSend) => {
    setAiLoading(true);
    try {
      const res = await api.post(`/api/stock/${ticker.toUpperCase()}/ai-analysis`, { prompt: promptToSend });
      setAiAnalysis(res.data.analysis);
    } catch (err) {
      setAiAnalysis(`Error fetching AI analysis: ${err.response?.data?.detail || err.message}`);
    }
    setAiLoading(false);
  };

  const getPeColor = (val) => {
    if (!val) return 'gray';
    if (val < 15) return 'var(--status-green)';
    if (val <= 25) return 'var(--accent-orange)';
    return 'var(--status-red)';
  };

  return (
    <div>
      <h2 style={{ marginBottom: '2rem' }}>📁 Stock Analysis & AI Intelligence</h2>
      
      <div className="glass-panel" style={{ display: 'flex', gap: '1rem', marginBottom: '2rem', alignItems: 'center' }}>
        <input 
          type="text" 
          value={ticker} 
          onChange={(e) => setTicker(e.target.value)}
          placeholder="Enter Ticker (e.g. AAPL)"
          style={{ maxWidth: '300px' }}
        />
        <button className="btn-primary" onClick={fetchStock} disabled={loading}>
          {loading ? 'Fetching...' : 'Analyze Fundamentals & Price Action'}
        </button>
      </div>

      {error && <p style={{ color: 'var(--status-red)', marginBottom: '2rem' }}>{error}</p>}

      {info && (
        <>
          <div className="glass-panel" style={{ marginBottom: '2rem', padding: 0, overflow: 'hidden' }}>
            <iframe 
              src={`https://s.tradingview.com/widgetembed/?frameElementId=tradingview_1&symbol=${ticker.toUpperCase()}&interval=W&hidesidetoolbar=1&symboledit=1&saveimage=1&toolbarbg=f1f3f6&studies=[]&theme=Dark&style=2&timezone=Etc%2FGMT%2B3&hideideas=1`}
              width="100%" 
              height="500" 
              frameBorder="0" 
              allowTransparency="true" 
              scrolling="no"
              title="TradingView Chart"
            />
          </div>

          <div className="grid-2" style={{ marginBottom: '2rem' }}>
            
            {/* Price Action Score block */}
            {priceAction && (
              <div className="glass-panel">
                <h3 className="metric-label" style={{ marginBottom: '1rem', fontSize: '1.2rem' }}>📊 Price Action Score (RSI, Volume, Ichimoku, MACD)</h3>
                
                <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginBottom: '1.5rem' }}>
                  <div style={{ 
                    padding: '1.5rem', 
                    border: `2px solid ${priceAction.score >= 7 ? 'var(--status-green)' : priceAction.score >= 4 ? 'var(--accent-orange)' : 'var(--status-red)'}`,
                    borderRadius: '1rem',
                    textAlign: 'center',
                    backgroundColor: 'rgba(0,0,0,0.3)'
                  }}>
                    <div style={{ fontSize: '2.5rem', fontWeight: 'bold', color: priceAction.score >= 7 ? 'var(--status-green)' : priceAction.score >= 4 ? 'var(--accent-orange)' : 'var(--status-red)' }}>
                      {priceAction.score >= 7 ? 'BUY' : priceAction.score >= 4 ? 'HOLD' : 'SELL'}
                    </div>
                    <div style={{ color: 'var(--text-secondary)' }}>{priceAction.score} / {priceAction.max_score} Points</div>
                  </div>
                  <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                    {priceAction.insights.map((insight, idx) => (
                      <div key={idx} style={{ fontSize: '0.95rem' }}>{insight}</div>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* Fundamentals block */}
            <div className="glass-panel">
              <h3 className="metric-label" style={{ marginBottom: '1rem', fontSize: '1.2rem' }}>📈 Valuation & Fundamentals</h3>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem' }}>
                <div>
                  <div className="metric-label">Market Cap</div>
                  <div style={{ fontSize: '1.5rem', fontWeight: 'bold' }}>${(info.marketCap / 1e9).toFixed(2)}B</div>
                </div>
                <div>
                  <div className="metric-label">Current Price</div>
                  <div style={{ fontSize: '1.5rem', fontWeight: 'bold', color: 'var(--accent-cyan)' }}>${info.currentPrice?.toFixed(2) || 'N/A'}</div>
                </div>
                <div>
                  <div className="metric-label">Trailing P/E</div>
                  <div style={{ fontSize: '1.8rem', fontWeight: 'bold', color: getPeColor(info.trailingPE) }}>
                    {info.trailingPE?.toFixed(2) || 'N/A'}
                  </div>
                </div>
                <div>
                  <div className="metric-label">Forward P/E</div>
                  <div style={{ fontSize: '1.8rem', fontWeight: 'bold', color: getPeColor(info.forwardPE) }}>
                    {info.forwardPE?.toFixed(2) || 'N/A'}
                  </div>
                </div>
                <div style={{ gridColumn: 'span 2' }}>
                  <div className="metric-label">Profit Margin</div>
                  <div style={{ fontSize: '1.5rem', color: info.profitMargins > 0 ? 'var(--status-green)' : 'var(--status-red)' }}>
                    {info.profitMargins ? (info.profitMargins * 100).toFixed(2) + '%' : 'N/A'}
                  </div>
                </div>
              </div>
            </div>

          </div>

          <div className="glass-panel" style={{ marginBottom: '2rem' }}>
            <h3 className="metric-label" style={{ marginBottom: '1rem', fontSize: '1.2rem', color: 'var(--accent-blue)' }}>🤖 Ask Mistral AI</h3>
            
            <div style={{ display: 'flex', gap: '1rem', marginBottom: '1.5rem' }}>
              <button className="btn-primary" onClick={handleAiGeneral} disabled={aiLoading}>
                {aiLoading ? 'Mistral is analyzing...' : '🧠 Generate General AI Report'}
              </button>
              <button className="btn-primary" onClick={handleAiDCF} disabled={aiLoading} style={{ background: 'var(--accent-purple)' }}>
                {aiLoading ? 'Mistral is analyzing...' : '💰 Generate AI DCF Valuation'}
              </button>
            </div>

            <details style={{ marginBottom: '1rem', cursor: 'pointer', color: 'var(--text-secondary)' }}>
              <summary>View / Edit Prompt</summary>
              <textarea 
                value={aiPrompt}
                onChange={e => setAiPrompt(e.target.value)}
                style={{ width: '100%', height: '150px', background: 'rgba(0,0,0,0.3)', color: 'white', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '1rem', marginTop: '0.5rem', fontFamily: 'var(--font-body)' }}
              />
              <button className="btn-primary" onClick={() => fetchAiAnalysis(aiPrompt)} disabled={aiLoading} style={{ marginTop: '0.5rem' }}>
                Resubmit Custom Prompt
              </button>
            </details>

            {aiAnalysis && (
              <div style={{ marginTop: '2rem', padding: '1.5rem', background: 'rgba(0,0,0,0.4)', borderRadius: '8px', borderLeft: '4px solid var(--accent-purple)' }}>
                <ReactMarkdown>{aiAnalysis}</ReactMarkdown>
              </div>
            )}
          </div>
          
          <div className="glass-panel">
            <h3 className="metric-label" style={{ marginBottom: '1rem' }}>🏢 Company Profile</h3>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1rem', color: 'var(--text-secondary)' }}>
              <div><strong>Sector:</strong> {info.sector || 'N/A'}</div>
              <div><strong>Industry:</strong> {info.industry || 'N/A'}</div>
              <div><strong>Employees:</strong> {info.fullTimeEmployees ? info.fullTimeEmployees.toLocaleString() : 'N/A'}</div>
              <div><strong>Location:</strong> {info.city || ''}, {info.country || ''}</div>
              <div style={{ gridColumn: 'span 2' }}><strong>Website:</strong> {info.website || 'N/A'}</div>
            </div>
            <p style={{ color: 'var(--text-secondary)', lineHeight: '1.6' }}>{info.longBusinessSummary}</p>
          </div>
        </>
      )}
    </div>
  );
}
