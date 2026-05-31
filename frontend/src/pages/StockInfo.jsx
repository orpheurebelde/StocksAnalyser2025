import React, { useState } from 'react';
import api from '../api';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

export default function StockInfo() {
  const [ticker, setTicker] = useState('');
  const [activeTicker, setActiveTicker] = useState('');
  const [info, setInfo] = useState(null);
  const [priceAction, setPriceAction] = useState(null);
  const [fundamentalsScore, setFundamentalsScore] = useState(null);
  const [dilution, setDilution] = useState(null);
  const [loading, setLoading] = useState(false);
  
  const [searchResults, setSearchResults] = useState([]);
  const [isSearching, setIsSearching] = useState(false);
  const [showDropdown, setShowDropdown] = useState(false);
  const [searchTimeout, setSearchTimeout] = useState(null);
  
  const [aiAnalysis, setAiAnalysis] = useState('');
  const [aiLoading, setAiLoading] = useState(false);
  const [aiPrompt, setAiPrompt] = useState('');
  const [aiRecommendation, setAiRecommendation] = useState(null);
  const [error, setError] = useState('');

  const fetchStock = async (event) => {
    event?.preventDefault();
    setShowDropdown(false);
    const nextTicker = ticker.trim().toUpperCase();
    if (!nextTicker) return;

    setLoading(true);
    setError('');
    setActiveTicker(nextTicker);
    setInfo(null);
    setPriceAction(null);
    setFundamentalsScore(null);
    setDilution(null);
    setAiAnalysis('');
    setAiPrompt('');
    setAiRecommendation(null);
    try {
      const res = await api.get(`/api/stock/${nextTicker}/full-analysis`);
      setInfo(res.data.info);
      setFundamentalsScore(res.data.fundamentals_score);
      setPriceAction(res.data.price_action);
      setDilution(res.data.dilution);
    } catch (err) {
      setError(err.response?.data?.detail || err.message);
    }
    setLoading(false);
  };

  const handleTickerChange = (e) => {
    const val = e.target.value;
    setTicker(val);
    
    if (searchTimeout) clearTimeout(searchTimeout);
    
    if (val.trim().length > 0) {
      const timeoutId = setTimeout(() => {
        searchTickers(val);
      }, 500);
      setSearchTimeout(timeoutId);
    } else {
      setSearchResults([]);
      setShowDropdown(false);
    }
  };

  const searchTickers = async (query) => {
    setIsSearching(true);
    try {
      const res = await api.get(`/api/stock/search?q=${encodeURIComponent(query)}`);
      setSearchResults(res.data.results || []);
      setShowDropdown(true);
    } catch (err) {
      console.error(err);
    }
    setIsSearching(false);
  };

  const selectTicker = (symbol) => {
    setTicker(symbol);
    setShowDropdown(false);
    setSearchResults([]);
  };

  const handleAiAnalysis = async () => {
    if (!info) return;
    const currentYear = new Date().getFullYear();
    const prompt = `You are a professional equity analyst. Today's year is ${currentYear}. Write a deep analysis using ONLY the following structured data:
    
    - Company: ${info.shortName || activeTicker}
    - Sector: ${info.sector}
    - Market Cap: $${(info.marketCap / 1e9).toFixed(2)}B
    - Current Price: $${info.currentPrice}
    - P/E (TTM): ${info.trailingPE}
    - Forward P/E: ${info.forwardPE}
    - Revenue: $${(info.totalRevenue / 1e9).toFixed(2)}B
    - Net Income: $${(info.netIncomeToCommon / 1e9).toFixed(2)}B
    - Free Cash Flow: $${(info.freeCashflow / 1e9).toFixed(2)}B
    - Shares Outstanding: ${info.sharesOutstanding}
    
    CRITICAL INSTRUCTION: The VERY FIRST LINE of your response MUST be exactly the following format:
    RATING: [Choose exactly one: STRONG BUY, BUY, HOLD, SELL, or STRONG SELL]
    
    Structure the rest of the analysis:
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
    const currentYear = new Date().getFullYear();
    const prompt = `You are a professional equity analyst. Based on the financial metrics retrieved earlier from Yahoo Finance and current market expectations for ${info.shortName || activeTicker} (${activeTicker}), generate a realistic 5-year DCF valuation.

    Use the following data as a baseline:
    - Company: ${info.shortName || activeTicker}
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
    1. Use the latest reported revenue as the starting point (Year 0 is ${currentYear}). Project cash flows from ${currentYear + 1} to ${currentYear + 5}.
    2. Run a 5-year DCF and clearly show PV of cash flows and terminal value.
    3. Calculate the implied share price.
    
    Emphasize realism, forward-looking assumptions, and avoid overly conservative or overly aggressive inputs.`;
    
    setAiPrompt(prompt);
    await fetchAiAnalysis(prompt);
  };

  const fetchAiAnalysis = async (promptToSend) => {
    setAiLoading(true);
    try {
      const res = await api.post(`/api/stock/${activeTicker}/ai-analysis`, { prompt: promptToSend });
      const text = res.data.analysis;
      setAiAnalysis(text);
      
      const ratingMatch = text.match(/RATING:\s*\[?([^\]\n*]+)\]?/i);
      if (ratingMatch) {
         let ratingStr = ratingMatch[1].toUpperCase();
         if (ratingStr.includes('STRONG BUY')) setAiRecommendation('STRONG BUY');
         else if (ratingStr.includes('STRONG SELL')) setAiRecommendation('STRONG SELL');
         else if (ratingStr.includes('BUY')) setAiRecommendation('BUY');
         else if (ratingStr.includes('SELL')) setAiRecommendation('SELL');
         else setAiRecommendation('HOLD');
      }
    } catch (err) {
      setAiAnalysis(`Error fetching AI analysis: ${err.response?.data?.detail || err.message}`);
    }
    setAiLoading(false);
  };

  // Coloring Helpers
  const getColor = (val, thGreen, thOrange, reverse=false) => {
    if (val === null || val === undefined) return 'gray';
    if (!reverse) {
      if (val >= thGreen) return 'var(--status-green)';
      if (val >= thOrange) return 'var(--accent-orange)';
      return 'var(--status-red)';
    } else {
      if (val <= thGreen) return 'var(--status-green)';
      if (val <= thOrange) return 'var(--accent-orange)';
      return 'var(--status-red)';
    }
  };

  const formatPct = (val) => val != null ? `${(val * 100).toFixed(2)}%` : 'N/A';
  const formatCur = (val) => val != null ? `$${val.toLocaleString()}` : 'N/A';
  const formatBil = (val) => val != null ? `$${(val / 1e9).toFixed(2)}B` : 'N/A';

  return (
    <div>
      <h2 style={{ marginBottom: '2rem' }}>📁 Stock Analysis & AI Intelligence</h2>
      
      <div style={{ display: 'flex', gap: '2rem', marginBottom: '2rem', alignItems: 'stretch' }}>
        <form className="glass-panel" onSubmit={fetchStock} style={{ flex: 1, display: 'flex', gap: '1rem', alignItems: 'center', position: 'relative' }}>
          <div style={{ position: 'relative', flex: 1, maxWidth: '300px' }}>
            <input 
              type="text" 
              value={ticker} 
              onChange={handleTickerChange}
              onFocus={() => { if(searchResults.length > 0) setShowDropdown(true); }}
              onBlur={() => setTimeout(() => setShowDropdown(false), 200)}
              placeholder="Enter Company or Ticker (e.g. Apple, AAPL)"
              style={{ width: '100%' }}
            />
            {showDropdown && searchResults.length > 0 && (
              <ul style={{
                position: 'absolute',
                top: '100%',
                left: 0,
                right: 0,
                maxHeight: '300px',
                overflowY: 'auto',
                background: '#1a1a1a',
                border: '1px solid rgba(255,255,255,0.1)',
                borderRadius: '8px',
                marginTop: '4px',
                padding: 0,
                listStyle: 'none',
                zIndex: 1000,
                boxShadow: '0 4px 12px rgba(0,0,0,0.5)'
              }}>
                {searchResults.map((r, i) => (
                  <li 
                    key={i} 
                    onClick={() => selectTicker(r.symbol)}
                    style={{
                      padding: '10px 15px',
                      cursor: 'pointer',
                      borderBottom: '1px solid rgba(255,255,255,0.05)',
                      display: 'flex',
                      flexDirection: 'column'
                    }}
                    onMouseOver={(e) => e.currentTarget.style.background = 'rgba(255,255,255,0.1)'}
                    onMouseOut={(e) => e.currentTarget.style.background = 'transparent'}
                  >
                    <strong style={{ color: 'var(--accent-cyan)' }}>{r.symbol}</strong>
                    <span style={{ fontSize: '0.85em', color: 'var(--text-secondary)' }}>{r.name}</span>
                  </li>
                ))}
              </ul>
            )}
            {isSearching && (
              <div style={{ position: 'absolute', right: '10px', top: '50%', transform: 'translateY(-50%)', fontSize: '0.8em', color: 'var(--text-secondary)' }}>
                Searching...
              </div>
            )}
          </div>
          <button className="btn-primary" type="submit" disabled={loading || !ticker.trim()}>
            {loading ? 'Fetching...' : 'Analyze Fundamentals & Price Action'}
          </button>
        </form>
        {aiRecommendation && (
          <div className={`glass-panel ${aiRecommendation.includes('BUY') ? 'glow-green' : aiRecommendation.includes('SELL') ? 'glow-red' : 'glow-blue'}`} style={{ minWidth: '250px', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
            <span className="metric-label" style={{ fontSize: '1rem', textTransform: 'uppercase', letterSpacing: '2px' }}>AI Consensus</span>
            <span style={{ fontSize: '2.5rem', fontWeight: 'bold', color: aiRecommendation.includes('BUY') ? 'var(--status-green)' : aiRecommendation.includes('SELL') ? 'var(--status-red)' : 'var(--accent-cyan)' }}>
              {aiRecommendation}
            </span>
          </div>
        )}
      </div>

      {error && <p style={{ color: 'var(--status-red)', marginBottom: '2rem' }}>{error}</p>}

      {info && (
        <>
          <div className="glass-panel" style={{ marginBottom: '2rem', padding: 0, overflow: 'hidden' }}>
            <iframe 
              src={`https://s.tradingview.com/widgetembed/?frameElementId=tradingview_1&symbol=${activeTicker}&interval=W&hidesidetoolbar=1&symboledit=1&saveimage=1&toolbarbg=f1f3f6&studies=[]&theme=Dark&style=2&timezone=Etc%2FGMT%2B3&hideideas=1`}
              width="100%" 
              height="500" 
              frameBorder="0" 
              allowTransparency="true" 
              scrolling="no"
              title="TradingView Chart"
            />
          </div>

          <div className="grid-2" style={{ marginBottom: '2rem', gap: '2rem' }}>
            {priceAction && (
              <div className="glass-panel">
                <h3 className="metric-label" style={{ marginBottom: '1rem', fontSize: '1.2rem' }}>📊 Price Action Score (RSI, Volume, Ichimoku, MACD)</h3>
                <div style={{ display: 'flex', alignItems: 'center', gap: '2rem' }}>
                  <div style={{ 
                    padding: '2rem', 
                    border: `2px solid ${priceAction.score >= 7 ? 'var(--status-green)' : priceAction.score >= 4 ? 'var(--accent-orange)' : 'var(--status-red)'}`,
                    borderRadius: '1rem',
                    textAlign: 'center',
                    backgroundColor: 'rgba(0,0,0,0.3)',
                    minWidth: '200px'
                  }}>
                    <div style={{ fontSize: '3rem', fontWeight: 'bold', color: priceAction.score >= 7 ? 'var(--status-green)' : priceAction.score >= 4 ? 'var(--accent-orange)' : 'var(--status-red)' }}>
                      {priceAction.score >= 7 ? 'BUY' : priceAction.score >= 4 ? 'HOLD' : 'SELL'}
                    </div>
                    <div style={{ color: 'var(--text-secondary)' }}>{priceAction.score} / {priceAction.max_score} Points</div>
                  </div>
                  <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                    {priceAction.insights.map((insight, idx) => (
                      <div key={idx} style={{ fontSize: '0.9rem', padding: '0.4rem', background: 'rgba(255,255,255,0.05)', borderRadius: '6px' }}>
                        {insight}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {fundamentalsScore && (
              <div className="glass-panel">
                <h3 className="metric-label" style={{ marginBottom: '1rem', fontSize: '1.2rem' }}>🔎 Valuation Quality Score</h3>
                <div style={{ display: 'flex', alignItems: 'center', height: '100%', paddingBottom: '2rem' }}>
                  <div style={{ 
                    padding: '2rem', 
                    border: `2px solid ${fundamentalsScore.color}`,
                    borderRadius: '1rem',
                    textAlign: 'center',
                    backgroundColor: 'rgba(0,0,0,0.3)',
                    width: '100%'
                  }}>
                    <div style={{ fontSize: '3rem', fontWeight: 'bold', color: fundamentalsScore.color }}>
                      {fundamentalsScore.label}
                    </div>
                    <div style={{ color: 'var(--text-secondary)' }}>{fundamentalsScore.score} / {fundamentalsScore.max_score} Points</div>
                  </div>
                </div>
              </div>
            )}
          </div>

          <div className="grid-2" style={{ marginBottom: '2rem', gap: '2rem' }}>
            {/* Valuation Column */}
            <div className="glass-panel">
              <h3 className="metric-label" style={{ marginBottom: '1.5rem', fontSize: '1.2rem', color: 'var(--accent-cyan)' }}>📈 Valuation</h3>
              <div className="grid-2" style={{ gap: '1.5rem' }}>
                <div>
                  <div className="metric-label">Market Cap</div>
                  <div style={{ fontSize: '1.8rem', fontWeight: 'bold' }}>{formatBil(info.marketCap)}</div>
                </div>
                <div>
                  <div className="metric-label">Current Price</div>
                  <div style={{ fontSize: '1.8rem', fontWeight: 'bold', color: 'var(--accent-cyan)' }}>{formatCur(info.currentPrice)}</div>
                </div>
                <div>
                  <div className="metric-label">Trailing P/E</div>
                  <div style={{ fontSize: '1.8rem', fontWeight: 'bold', color: getColor(info.trailingPE, 15, 25, true) }}>
                    {info.trailingPE?.toFixed(2) || 'N/A'}
                  </div>
                </div>
                <div>
                  <div className="metric-label">Forward P/E</div>
                  <div style={{ fontSize: '1.8rem', fontWeight: 'bold', color: getColor(info.forwardPE, 15, 25, true) }}>
                    {info.forwardPE?.toFixed(2) || 'N/A'}
                  </div>
                </div>
                <div>
                  <div className="metric-label">PEG Ratio</div>
                  <div style={{ fontSize: '1.8rem', fontWeight: 'bold', color: getColor(info.trailingPegRatio, 1, 2, true) }}>
                    {info.trailingPegRatio?.toFixed(2) || 'N/A'}
                  </div>
                </div>
                <div>
                  <div className="metric-label">P/B Ratio</div>
                  <div style={{ fontSize: '1.8rem', fontWeight: 'bold', color: getColor(info.priceToBook, 5, 15, true) }}>
                    {info.priceToBook?.toFixed(2) || 'N/A'}
                  </div>
                </div>
                <div>
                  <div className="metric-label">P/S Ratio</div>
                  <div style={{ fontSize: '1.8rem', fontWeight: 'bold', color: getColor(info.priceToSalesTrailing12Months, 4, 10, true) }}>
                    {info.priceToSalesTrailing12Months?.toFixed(2) || 'N/A'}
                  </div>
                </div>
              </div>
            </div>

            {/* Fundamentals Column */}
            <div className="glass-panel">
              <h3 className="metric-label" style={{ marginBottom: '1.5rem', fontSize: '1.2rem', color: 'var(--accent-blue)' }}>🏢 Fundamentals</h3>
              <div className="grid-2" style={{ gap: '1.5rem' }}>
                <div>
                  <div className="metric-label">ROE</div>
                  <div style={{ fontSize: '1.8rem', fontWeight: 'bold', color: getColor(info.returnOnEquity, 0.2, 0.1) }}>
                    {formatPct(info.returnOnEquity)}
                  </div>
                </div>
                <div>
                  <div className="metric-label">EBITDA Margin</div>
                  <div style={{ fontSize: '1.8rem', fontWeight: 'bold', color: getColor(info.ebitda / info.totalRevenue, 0.2, 0.1) }}>
                    {info.ebitda && info.totalRevenue ? formatPct(info.ebitda / info.totalRevenue) : 'N/A'}
                  </div>
                </div>
                <div>
                  <div className="metric-label">EPS (Current Year)</div>
                  <div style={{ fontSize: '1.8rem', fontWeight: 'bold', color: getColor(info.epsCurrentYear, 1, 0) }}>
                    ${info.epsCurrentYear?.toFixed(2) || 'N/A'}
                  </div>
                </div>
                <div>
                  <div className="metric-label">EPS (Forward)</div>
                  <div style={{ fontSize: '1.8rem', fontWeight: 'bold', color: getColor(info.forwardEps, 1, 0) }}>
                    ${info.forwardEps?.toFixed(2) || 'N/A'}
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div className="grid-2" style={{ marginBottom: '2rem', gap: '2rem' }}>
            <div className="glass-panel">
              <h3 className="metric-label" style={{ marginBottom: '1.5rem', fontSize: '1.2rem' }}>💰 Financials</h3>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem' }}>
                <div>
                  <div className="metric-label">Free Cash Flow</div>
                  <div style={{ fontSize: '1.2rem', fontWeight: 'bold' }}>{formatBil(info.freeCashflow)}</div>
                </div>
                <div>
                  <div className="metric-label">Net Income</div>
                  <div style={{ fontSize: '1.2rem', fontWeight: 'bold', color: info.netIncomeToCommon > 0 ? 'var(--status-green)' : 'var(--status-red)' }}>
                    {formatBil(info.netIncomeToCommon)}
                  </div>
                </div>
                <div>
                  <div className="metric-label">Total Revenue</div>
                  <div style={{ fontSize: '1.2rem', fontWeight: 'bold' }}>{formatBil(info.totalRevenue)}</div>
                </div>
                <div>
                  <div className="metric-label">Total Cash</div>
                  <div style={{ fontSize: '1.2rem', fontWeight: 'bold' }}>{formatBil(info.totalCash)}</div>
                </div>
                <div>
                  <div className="metric-label">Total Debt</div>
                  <div style={{ fontSize: '1.2rem', fontWeight: 'bold' }}>{formatBil(info.totalDebt)}</div>
                </div>
                <div>
                  <div className="metric-label">Debt vs Cash</div>
                  <div style={{ fontSize: '1.1rem', fontWeight: 'bold', color: info.totalCash > info.totalDebt ? 'var(--status-green)' : 'var(--status-red)' }}>
                    {info.totalCash > info.totalDebt ? '🟢 More Cash than Debt' : '🔴 High Debt'}
                  </div>
                </div>
              </div>
            </div>

            <div className="glass-panel">
              <h3 className="metric-label" style={{ marginBottom: '1.5rem', fontSize: '1.2rem' }}>📊 Margins & Growth</h3>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem' }}>
                <div>
                  <div className="metric-label">Gross Margin</div>
                  <div style={{ fontSize: '1.2rem', fontWeight: 'bold', color: getColor(info.grossMargins, 0.4, 0.2) }}>
                    {formatPct(info.grossMargins)}
                  </div>
                </div>
                <div>
                  <div className="metric-label">Earnings Growth</div>
                  <div style={{ fontSize: '1.2rem', fontWeight: 'bold', color: getColor(info.earningsGrowth, 0.15, 0.05) }}>
                    {formatPct(info.earningsGrowth)}
                  </div>
                </div>
                <div>
                  <div className="metric-label">Operating Margin</div>
                  <div style={{ fontSize: '1.2rem', fontWeight: 'bold', color: getColor(info.operatingMargins, 0.4, 0.2) }}>
                    {formatPct(info.operatingMargins)}
                  </div>
                </div>
                <div>
                  <div className="metric-label">Revenue Growth</div>
                  <div style={{ fontSize: '1.2rem', fontWeight: 'bold', color: getColor(info.revenueGrowth, 0.15, 0.05) }}>
                    {formatPct(info.revenueGrowth)}
                  </div>
                </div>
                <div>
                  <div className="metric-label">Profit Margin</div>
                  <div style={{ fontSize: '1.2rem', fontWeight: 'bold', color: getColor(info.profitMargins, 0.4, 0.2) }}>
                    {formatPct(info.profitMargins)}
                  </div>
                </div>
              </div>
            </div>
          </div>

          {dilution && (
            <div className="glass-panel" style={{ marginBottom: '2rem' }}>
              <h3 className="metric-label" style={{ marginBottom: '1.5rem', fontSize: '1.2rem' }}>📈 Share Dilution Check (Estimation)</h3>
              <div className="grid-3" style={{ marginBottom: '1.5rem' }}>
                <div>
                  <div className="metric-label">Current Shares Outstanding</div>
                  <div style={{ fontSize: '1.5rem', fontWeight: 'bold' }}>{dilution.current_shares?.toLocaleString() || 'N/A'}</div>
                </div>
                <div>
                  <div className="metric-label">Estimated Shares (1Y Ago)</div>
                  <div style={{ fontSize: '1.5rem', fontWeight: 'bold' }}>{dilution.past_shares?.toLocaleString() || 'N/A'}</div>
                </div>
                <div>
                  <div className="metric-label">Dilution (1 Year)</div>
                  <div style={{ fontSize: '1.5rem', fontWeight: 'bold', color: getColor(dilution.dilution_pct, 0, 3, true) }}>
                    {dilution.dilution_amount?.toLocaleString() || '0'} shares ({dilution.dilution_pct?.toFixed(2) || '0.00'}%)
                  </div>
                </div>
              </div>
              <div style={{ padding: '1.5rem', background: 'rgba(255,255,255,0.05)', borderRadius: '8px' }}>
                <h4 style={{ marginBottom: '1rem', color: 'var(--accent-cyan)' }}>🧠 Dilution Context Analysis</h4>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.8rem' }}>
                  {dilution.comments?.map((comment, idx) => (
                    <div key={idx}><ReactMarkdown>{comment}</ReactMarkdown></div>
                  ))}
                </div>
              </div>
            </div>
          )}

          <div className="glass-panel" style={{ marginBottom: '2rem' }}>
            <h3 className="metric-label" style={{ marginBottom: '1rem', fontSize: '1.2rem', color: 'var(--accent-blue)' }}>🤖 Ask Mistral AI</h3>
            
            <div style={{ display: 'flex', gap: '1rem', marginBottom: '1.5rem' }}>
              <button className="btn-primary" onClick={handleAiAnalysis} disabled={aiLoading}>
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
              <div className="markdown-content" style={{ marginTop: '2rem', padding: '1.5rem', background: 'rgba(0,0,0,0.4)', borderRadius: '8px', borderLeft: '4px solid var(--accent-purple)' }}>
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{aiAnalysis}</ReactMarkdown>
              </div>
            )}
          </div>
          
          <div className="grid-2" style={{ marginBottom: '2rem' }}>
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

            <div className="glass-panel">
              <h3 className="metric-label" style={{ marginBottom: '1rem' }}>📦 Ownership</h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', fontSize: '1.2rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span>Institutional Ownership:</span>
                  <span style={{ fontWeight: 'bold' }}>{formatPct(info.heldPercentInstitutions)}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span>Insider Ownership:</span>
                  <span style={{ fontWeight: 'bold' }}>{formatPct(info.heldPercentInsiders)}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span>Shares Short:</span>
                  <span style={{ fontWeight: 'bold' }}>{info.sharesShort ? info.sharesShort.toLocaleString() : 'N/A'}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span>Short Ratio:</span>
                  <span style={{ fontWeight: 'bold' }}>{info.shortRatio || 'N/A'}</span>
                </div>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
