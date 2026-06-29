import { useEffect, useRef, useState } from 'react';
import { LineChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { Pencil, Plus, RefreshCw, Trash2, X } from 'lucide-react';
import api from '../api';

const peValue = (value) => (typeof value === 'number' ? value.toFixed(2) : 'N/A');
const priceValue = (value, currency) => (typeof value === 'number' ? `${value.toFixed(2)} ${currency || ''}`.trim() : 'N/A');

export default function Portfolio() {
  const [portfolios, setPortfolios] = useState([]);
  const [maxPortfolios, setMaxPortfolios] = useState(5);
  const [selectedId, setSelectedId] = useState(null);
  const [portfolioName, setPortfolioName] = useState('');
  const [tickerQuery, setTickerQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const searchTimerRef = useRef(null);
  const searchRequestRef = useRef(0);

  const selected = portfolios.find((portfolio) => portfolio.id === selectedId) || null;

  useEffect(() => {
    let active = true;
    api.get('/api/portfolio')
      .then((response) => {
        if (!active) return;
        const items = response.data.portfolios || [];
        setPortfolios(items);
        setMaxPortfolios(response.data.max_portfolios || 5);
        setSelectedId(items[0]?.id || null);
      })
      .catch((requestError) => {
        if (active) setError(requestError.response?.data?.detail || requestError.message);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => { active = false; };
  }, []);

  const selectPortfolio = (portfolioId) => {
    setSelectedId(portfolioId);
    setAnalysis(null);
  };

  const replacePortfolio = (portfolio) => {
    setPortfolios((items) => items.map((item) => item.id === portfolio.id ? portfolio : item));
  };

  const createPortfolio = async () => {
    if (!portfolioName.trim()) return;
    setError('');
    try {
      const response = await api.post('/api/portfolio', { name: portfolioName.trim() });
      const portfolio = response.data.portfolio;
      setPortfolios((items) => [portfolio, ...items]);
      setSelectedId(portfolio.id);
      setPortfolioName('');
    } catch (requestError) {
      setError(requestError.response?.data?.detail || requestError.message);
    }
  };

  const renamePortfolio = async () => {
    if (!selected) return;
    const name = window.prompt('Portfolio name', selected.name)?.trim();
    if (!name || name === selected.name) return;
    try {
      const response = await api.patch(`/api/portfolio/${selected.id}`, { name });
      replacePortfolio(response.data.portfolio);
    } catch (requestError) {
      setError(requestError.response?.data?.detail || requestError.message);
    }
  };

  const deletePortfolio = async () => {
    if (!selected || !window.confirm(`Delete portfolio "${selected.name}"?`)) return;
    try {
      await api.delete(`/api/portfolio/${selected.id}`);
      const remaining = portfolios.filter((item) => item.id !== selected.id);
      setPortfolios(remaining);
      setSelectedId(remaining[0]?.id || null);
      setAnalysis(null);
    } catch (requestError) {
      setError(requestError.response?.data?.detail || requestError.message);
    }
  };

  const searchTickers = async (value) => {
    setTickerQuery(value);
    if (searchTimerRef.current) clearTimeout(searchTimerRef.current);
    if (!value.trim()) {
      setSearchResults([]);
      return;
    }
    searchTimerRef.current = setTimeout(async () => {
      const requestId = ++searchRequestRef.current;
      try {
        const response = await api.get(`/api/stock/search?q=${encodeURIComponent(value.trim())}`);
        if (requestId === searchRequestRef.current) setSearchResults(response.data.results || []);
      } catch {
        if (requestId === searchRequestRef.current) setSearchResults([]);
      }
    }, 350);
  };

  const addTicker = async (symbol) => {
    if (!selected) return;
    setError('');
    try {
      const response = await api.post(`/api/portfolio/${selected.id}/tickers`, { ticker: symbol });
      replacePortfolio(response.data.portfolio);
      setTickerQuery('');
      setSearchResults([]);
      setAnalysis(null);
    } catch (requestError) {
      setError(requestError.response?.data?.detail || requestError.message);
    }
  };

  const removeTicker = async (ticker) => {
    if (!selected) return;
    try {
      const response = await api.delete(`/api/portfolio/${selected.id}/tickers/${encodeURIComponent(ticker)}`);
      replacePortfolio(response.data.portfolio);
      setAnalysis(null);
    } catch (requestError) {
      setError(requestError.response?.data?.detail || requestError.message);
    }
  };

  const refreshAnalysis = async () => {
    if (!selected) return;
    setLoading(true);
    setError('');
    try {
      const response = await api.get(`/api/portfolio/${selected.id}/analysis`);
      setAnalysis(response.data);
    } catch (requestError) {
      setError(requestError.response?.data?.detail || requestError.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <h2 style={{ marginBottom: '0.5rem' }}>Portfolio Analysis</h2>
      <p className="metric-label" style={{ marginBottom: '2rem' }}>Store up to {maxPortfolios} portfolios. Track 5-year price evolution and valuation multiples.</p>

      <div className="glass-panel" style={{ marginBottom: '1.5rem' }}>
        <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', alignItems: 'center' }}>
          <input
            value={portfolioName}
            onChange={(event) => setPortfolioName(event.target.value)}
            onKeyDown={(event) => { if (event.key === 'Enter') createPortfolio(); }}
            placeholder="New portfolio name"
            maxLength={80}
          />
          <button className="btn-primary" onClick={createPortfolio} disabled={!portfolioName.trim() || portfolios.length >= maxPortfolios}>
            <Plus size={17} /> Create portfolio
          </button>
          <span className="metric-label">{portfolios.length}/{maxPortfolios}</span>
        </div>
      </div>

      {portfolios.length > 0 && (
        <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', marginBottom: '1.5rem' }}>
          {portfolios.map((portfolio) => (
            <button
              key={portfolio.id}
              className={portfolio.id === selectedId ? 'btn-primary' : 'table-action'}
              onClick={() => selectPortfolio(portfolio.id)}
            >
              {portfolio.name} ({portfolio.tickers.length})
            </button>
          ))}
        </div>
      )}

      {selected && (
        <>
          <div className="glass-panel" style={{ marginBottom: '1.5rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem', flexWrap: 'wrap', alignItems: 'center' }}>
              <div>
                <div className="metric-label">Selected portfolio</div>
                <h3>{selected.name}</h3>
              </div>
              <div style={{ display: 'flex', gap: '0.5rem' }}>
                <button className="table-action" onClick={renamePortfolio}><Pencil size={16} /> Rename</button>
                <button className="table-action" onClick={deletePortfolio} style={{ color: 'var(--status-red)' }}><Trash2 size={16} /> Delete</button>
              </div>
            </div>

            <div style={{ position: 'relative', marginTop: '1.25rem', maxWidth: '520px' }}>
              <input
                value={tickerQuery}
                onChange={(event) => searchTickers(event.target.value)}
                placeholder="Search company or ticker"
                style={{ width: '100%' }}
              />
              {searchResults.length > 0 && (
                <div className="glass-panel" style={{ position: 'absolute', left: 0, right: 0, top: 'calc(100% + 4px)', zIndex: 20, padding: '0.4rem' }}>
                  {searchResults.map((result) => (
                    <button
                      key={result.symbol}
                      type="button"
                      className="ticker-choice"
                      onClick={() => addTicker(result.symbol)}
                      style={{ width: '100%' }}
                    >
                      <strong>{result.symbol}</strong>
                      <span>{result.name}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>

            <div style={{ display: 'flex', gap: '0.6rem', flexWrap: 'wrap', marginTop: '1rem' }}>
              {selected.tickers.map((ticker) => (
                <span key={ticker} className="table-action" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}>
                  {ticker}
                  <button type="button" onClick={() => removeTicker(ticker)} aria-label={`Remove ${ticker}`} style={{ border: 0, background: 'transparent', color: 'var(--status-red)', cursor: 'pointer', padding: 0 }}>
                    <X size={15} />
                  </button>
                </span>
              ))}
              {!selected.tickers.length && <span className="metric-label">No tickers added.</span>}
            </div>

            <button className="btn-primary" onClick={refreshAnalysis} disabled={loading || !selected.tickers.length} style={{ marginTop: '1.25rem' }}>
              <RefreshCw size={17} className={loading ? 'spin-icon' : ''} /> {loading ? 'Loading market data...' : 'Update analysis'}
            </button>
          </div>

          {analysis?.tickers?.map((item) => (
            <section key={item.ticker} className="glass-panel" style={{ marginBottom: '1.5rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem', flexWrap: 'wrap', marginBottom: '1rem' }}>
                <div>
                  <div className="metric-label">{item.ticker}</div>
                  <h3>{item.name}</h3>
                </div>
                <div style={{ display: 'flex', gap: '1.5rem', flexWrap: 'wrap' }}>
                  <div><div className="metric-label">Current price</div><strong>{priceValue(item.current_price, item.currency)}</strong></div>
                  <div><div className="metric-label">Current P/E</div><strong>{peValue(item.trailing_pe)}</strong></div>
                  <div><div className="metric-label">Forward P/E</div><strong>{peValue(item.forward_pe)}</strong></div>
                </div>
              </div>
              <div style={{ width: '100%', height: 280 }}>
                <ResponsiveContainer>
                  <LineChart data={item.evolution}>
                    <XAxis dataKey="date" stroke="var(--text-secondary)" minTickGap={35} tick={{ fontSize: 11 }} />
                    <YAxis stroke="var(--text-secondary)" domain={['auto', 'auto']} tick={{ fontSize: 11 }} />
                    <Tooltip contentStyle={{ background: '#12121a', border: '1px solid var(--border-color)' }} />
                    <Line type="monotone" dataKey="close" name="Monthly close" stroke="var(--accent-cyan)" strokeWidth={2} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </section>
          ))}
        </>
      )}

      {!portfolios.length && !loading && <div className="glass-panel"><span className="metric-label">Create first portfolio to begin.</span></div>}
      {error && <p style={{ color: 'var(--status-red)', marginTop: '1rem' }}>{error}</p>}
    </div>
  );
}
