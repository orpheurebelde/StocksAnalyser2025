import { useEffect, useRef, useState } from 'react';
import { Pencil, Plus, RefreshCw, Trash2, X } from 'lucide-react';
import api from '../api';

const peValue = (value) => (typeof value === 'number' ? value.toFixed(2) : 'N/A');
const priceValue = (value, currency) => (typeof value === 'number' ? `${value.toFixed(2)} ${currency || ''}`.trim() : 'N/A');
const yearlyEvolution = (values, valueKey) => {
  const byYear = new Map();
  (values || []).forEach((item) => byYear.set(item.date.slice(0, 4), item));
  const rows = [...byYear.entries()].sort(([left], [right]) => left.localeCompare(right)).slice(-5);
  return rows.map(([year, item], index) => {
    const current = item[valueKey];
    const previous = index > 0 ? rows[index - 1][1][valueKey] : null;
    return {
      year,
      value: current,
      change: previous && current != null ? (current / previous - 1) * 100 : null,
    };
  });
};

function HoldingRow({ holding, onSave, onRemove }) {
  const [quantity, setQuantity] = useState(String(holding.quantity ?? 1));
  const [acquisitionDate, setAcquisitionDate] = useState(holding.acquisition_date || '');

  return (
    <tr>
      <td>{holding.ticker}</td>
      <td><input type="number" min="0.000001" step="any" value={quantity} onChange={(event) => setQuantity(event.target.value)} style={{ width: 130 }} /></td>
      <td><input type="date" value={acquisitionDate} onChange={(event) => setAcquisitionDate(event.target.value)} /></td>
      <td>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button className="table-action" type="button" onClick={() => onSave(holding.ticker, Number(quantity), acquisitionDate)} disabled={!Number(quantity) || Number(quantity) <= 0}>Save</button>
          <button className="table-action" type="button" onClick={() => onRemove(holding.ticker)} style={{ color: 'var(--status-red)' }}><X size={15} /> Remove</button>
        </div>
      </td>
    </tr>
  );
}

export default function Portfolio() {
  const [portfolios, setPortfolios] = useState([]);
  const [maxPortfolios, setMaxPortfolios] = useState(5);
  const [selectedId, setSelectedId] = useState(null);
  const [portfolioName, setPortfolioName] = useState('');
  const [tickerQuery, setTickerQuery] = useState('');
  const [newQuantity, setNewQuantity] = useState('1');
  const [newAcquisitionDate, setNewAcquisitionDate] = useState(new Date().toISOString().slice(0, 10));
  const [trading212Key, setTrading212Key] = useState('');
  const [trading212Secret, setTrading212Secret] = useState('');
  const [trading212Environment, setTrading212Environment] = useState('live');
  const [brokerStatus, setBrokerStatus] = useState('');
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
      const response = await api.post(`/api/portfolio/${selected.id}/tickers`, {
        ticker: symbol,
        quantity: Number(newQuantity),
        acquisition_date: newAcquisitionDate || null,
      });
      replacePortfolio(response.data.portfolio);
      setTickerQuery('');
      setSearchResults([]);
      setAnalysis(null);
    } catch (requestError) {
      setError(requestError.response?.data?.detail || requestError.message);
    }
  };

  const updateHolding = async (ticker, quantity, acquisitionDate) => {
    if (!selected) return;
    try {
      const response = await api.patch(`/api/portfolio/${selected.id}/tickers/${encodeURIComponent(ticker)}`, {
        quantity,
        acquisition_date: acquisitionDate || null,
      });
      replacePortfolio(response.data.portfolio);
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

  const importTrading212 = async () => {
    if (!selected || !trading212Key || !trading212Secret) return;
    setLoading(true);
    setError('');
    setBrokerStatus('');
    try {
      const response = await api.post(`/api/portfolio/${selected.id}/import/trading212`, {
        api_key: trading212Key,
        api_secret: trading212Secret,
        environment: trading212Environment,
      });
      replacePortfolio(response.data.portfolio);
      setAnalysis(null);
      setBrokerStatus(`Imported ${response.data.imported.length} Trading 212 positions. Credentials were not stored.`);
      setTrading212Key('');
      setTrading212Secret('');
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

            <div style={{ marginTop: '1.25rem', maxWidth: '620px' }}>
              <div style={{ display: 'grid', gridTemplateColumns: 'minmax(200px, 1fr) 130px 170px', gap: '0.6rem' }}>
                <input value={tickerQuery} onChange={(event) => searchTickers(event.target.value)} placeholder="Search company or ticker" />
                <input type="number" min="0.000001" step="any" value={newQuantity} onChange={(event) => setNewQuantity(event.target.value)} placeholder="Quantity" />
                <input type="date" value={newAcquisitionDate} onChange={(event) => setNewAcquisitionDate(event.target.value)} />
              </div>
              {searchResults.length > 0 && (
                <div style={{ marginTop: '0.4rem', padding: '0.4rem', border: '1px solid var(--border-color)', borderRadius: '10px', background: '#090b12' }}>
                  {searchResults.map((result) => (
                    <button
                      key={result.symbol}
                      type="button"
                      className="ticker-choice"
                      onClick={() => addTicker(result.symbol)}
                      disabled={!Number(newQuantity) || Number(newQuantity) <= 0}
                      style={{ width: '100%' }}
                    >
                      <strong>{result.symbol}</strong>
                      <span>{result.name}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>

            <div style={{ overflowX: 'auto', marginTop: '1rem' }}>
              {selected.holdings?.length ? (
                <table className="earnings-table">
                  <thead><tr><th>Ticker</th><th>Stocks acquired</th><th>Acquisition date</th><th>Actions</th></tr></thead>
                  <tbody>
                    {selected.holdings.map((holding) => (
                      <HoldingRow key={holding.ticker} holding={holding} onSave={updateHolding} onRemove={removeTicker} />
                    ))}
                  </tbody>
                </table>
              ) : <span className="metric-label">No tickers added.</span>}
            </div>

            <button className="btn-primary" onClick={refreshAnalysis} disabled={loading || !selected.tickers.length} style={{ marginTop: '1.25rem' }}>
              <RefreshCw size={17} className={loading ? 'spin-icon' : ''} /> {loading ? 'Loading market data...' : 'Update analysis'}
            </button>
          </div>

          <div className="glass-panel" style={{ marginBottom: '1.5rem' }}>
            <div className="metric-label">Direct broker import</div>
            <h3 style={{ marginBottom: '0.5rem' }}>Trading 212</h3>
            <p className="metric-label" style={{ marginBottom: '1rem' }}>Use read-only Portfolio permission. Key and secret are sent once and never stored.</p>
            <div style={{ display: 'grid', gridTemplateColumns: 'minmax(180px, 1fr) minmax(180px, 1fr) 120px auto', gap: '0.6rem', alignItems: 'center' }}>
              <input value={trading212Key} onChange={(event) => setTrading212Key(event.target.value)} placeholder="API key" autoComplete="off" />
              <input type="password" value={trading212Secret} onChange={(event) => setTrading212Secret(event.target.value)} placeholder="API secret" autoComplete="new-password" />
              <select value={trading212Environment} onChange={(event) => setTrading212Environment(event.target.value)}>
                <option value="live">Live</option>
                <option value="demo">Demo</option>
              </select>
              <button className="btn-primary" type="button" onClick={importTrading212} disabled={loading || !trading212Key || !trading212Secret}>Import positions</button>
            </div>
            {brokerStatus && <p className="metric-label" role="status" style={{ marginTop: '0.8rem' }}>{brokerStatus}</p>}
            <p className="metric-label" style={{ marginTop: '1rem' }}>Trade Republic direct API unavailable. Use official statement/CSV import; login credentials must never be entered here.</p>
          </div>

          {analysis?.tickers?.map((item) => (
            <section key={item.ticker} className="glass-panel" style={{ marginBottom: '1.5rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem', flexWrap: 'wrap', marginBottom: '1rem' }}>
                <div>
                  <div className="metric-label">{item.ticker}</div>
                  <h3>{item.name}</h3>
                </div>
                <div style={{ display: 'flex', gap: '1.5rem', flexWrap: 'wrap' }}>
                  <div><div className="metric-label">Stocks acquired</div><strong>{item.quantity}</strong></div>
                  <div><div className="metric-label">Acquisition date</div><strong>{item.acquisition_date || 'N/A'}</strong></div>
                  <div><div className="metric-label">Current price</div><strong>{priceValue(item.current_price, item.currency)}</strong></div>
                  <div><div className="metric-label">Current P/E</div><strong>{peValue(item.trailing_pe)}</strong></div>
                  <div><div className="metric-label">Forward P/E</div><strong>{peValue(item.forward_pe)}</strong></div>
                </div>
              </div>
              <div style={{ overflowX: 'auto' }}>
                <table className="earnings-table">
                  <thead><tr><th>Year</th><th>Year-end price</th><th>Annual evolution</th></tr></thead>
                  <tbody>
                    {yearlyEvolution(item.evolution, 'close').map((row) => (
                      <tr key={row.year}>
                        <td>{row.year}</td>
                        <td>{priceValue(row.value, item.currency)}</td>
                        <td style={{ color: row.change == null ? 'var(--text-secondary)' : row.change >= 0 ? 'var(--status-green)' : 'var(--status-red)' }}>
                          {row.change == null ? 'Base year' : `${row.change.toFixed(2)}%`}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          ))}

          {analysis?.portfolio_evolution?.length > 0 && (
            <section className="glass-panel" style={{ marginBottom: '1.5rem' }}>
              <div className="metric-label">Portfolio evolution</div>
              <h3 style={{ marginBottom: '0.35rem' }}>{selected.name} five-year performance</h3>
              <p className="metric-label" style={{ marginBottom: '1rem' }}>{analysis.evolution_method}</p>
              <div style={{ overflowX: 'auto' }}>
                <table className="earnings-table">
                  <thead><tr><th>Year</th><th>Portfolio index</th><th>Annual evolution</th><th>Total evolution</th></tr></thead>
                  <tbody>
                    {yearlyEvolution(analysis.portfolio_evolution, 'index').map((row, index, rows) => {
                      const base = rows[0]?.value;
                      const total = base ? (row.value / base - 1) * 100 : null;
                      return (
                        <tr key={row.year}>
                          <td>{row.year}</td>
                          <td>{row.value.toFixed(2)}</td>
                          <td style={{ color: row.change == null ? 'var(--text-secondary)' : row.change >= 0 ? 'var(--status-green)' : 'var(--status-red)' }}>
                            {row.change == null ? 'Base year' : `${row.change.toFixed(2)}%`}
                          </td>
                          <td>{total == null ? 'N/A' : `${total.toFixed(2)}%`}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </section>
          )}
        </>
      )}

      {!portfolios.length && !loading && <div className="glass-panel"><span className="metric-label">Create first portfolio to begin.</span></div>}
      {error && <p style={{ color: 'var(--status-red)', marginTop: '1rem' }}>{error}</p>}
    </div>
  );
}
