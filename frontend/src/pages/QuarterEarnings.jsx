import { useEffect, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { BarChart3, Brain, Database, Landmark, RefreshCw, Search, Trash2 } from 'lucide-react';
import { LineChart as ReLineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import api from '../api';

const statementKeys = [
  ['revenue', 'Revenue'],
  ['operating_income', 'Operating Income'],
  ['net_income', 'Net Income'],
  ['operating_cash_flow', 'Operating Cash Flow'],
  ['cash', 'Cash'],
  ['total_assets', 'Total Assets'],
  ['total_liabilities', 'Total Liabilities'],
];

const money = (value) => {
  if (value === null || value === undefined) return 'N/A';
  const abs = Math.abs(value);
  if (abs >= 1e9) return `$${(value / 1e9).toFixed(2)}B`;
  if (abs >= 1e6) return `$${(value / 1e6).toFixed(2)}M`;
  return `$${Number(value).toLocaleString()}`;
};

const pct = (value) => (value === null || value === undefined ? 'N/A' : `${(value * 100).toFixed(1)}%`);

const valueChange = (current, previous) => {
  if (current === null || current === undefined || previous === null || previous === undefined || previous === 0) return null;
  return (current - previous) / Math.abs(previous);
};

const apiError = (err) => {
  if (err.response?.data?.detail) return err.response.data.detail;
  if (err.message === 'Network Error') return 'Network Error: backend did not return a readable response. Check Render deploy/logs.';
  return err.message;
};

function FilingMetricCard({ label, item }) {
  const growth = item?.growth;
  const color = growth === null || growth === undefined ? 'var(--text-secondary)' : growth >= 0 ? 'var(--status-green)' : 'var(--status-red)';
  const width = growth === null || growth === undefined ? 12 : Math.min(100, Math.max(8, Math.abs(growth) * 140));
  return (
    <div className="glass-panel metric-card">
      <span className="metric-label">{label}</span>
      <span className="metric-value" style={{ fontSize: '1.45rem' }}>{money(item?.current)}</span>
      <span style={{ color }}>{pct(growth)} vs prior column</span>
      <div className="filing-bar"><span style={{ width: `${width}%`, background: color }} /></div>
      <span className="metric-label">Prior: {money(item?.prior)} | {item?.confidence || 'missing'}</span>
    </div>
  );
}

function FilingBoard({ report, score }) {
  if (!report) return null;
  const filing = report.metrics || {};
  const statements = filing.statements || {};
  return (
    <>
      <div className="filing-hero glass-panel">
        <div>
          <div className="metric-label">SEC Filing</div>
          <h2>{filing.company_name || report.company_name}</h2>
          <p>{filing.form_type || '10-Q'} | {filing.fiscal_quarter || 'Period not extracted'} | {filing.filename || 'PDF'}</p>
        </div>
        <div className="filing-score">
          <span>{score?.total ?? 'N/A'}</span>
          <small>{score?.label || 'Not scored'}</small>
          {score?.confidence && <small>Confidence {score.confidence.score}/100 | {score.confidence.level}</small>}
          <strong>{score?.suggestion || 'NO RATING'}</strong>
          {score?.legend && (
            <div className="score-tooltip">
              <div className="metric-label">Score Legend</div>
              {score.legend.map((item) => (
                <p key={item.range}><b>{item.range}</b> {item.label} | {item.suggestion}: {item.meaning}</p>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="grid-4" style={{ marginBottom: '2rem' }}>
        <FilingMetricCard label="Revenue" item={statements.revenue} />
        <FilingMetricCard label="Operating Income" item={statements.operating_income} />
        <FilingMetricCard label="Net Income" item={statements.net_income} />
        <FilingMetricCard label="Operating Cash Flow" item={statements.operating_cash_flow} />
      </div>

      <div className="grid-3" style={{ marginBottom: '2rem' }}>
        <FilingMetricCard label="Cash" item={statements.cash} />
        <FilingMetricCard label="Total Assets" item={statements.total_assets} />
        <FilingMetricCard label="Total Liabilities" item={statements.total_liabilities} />
      </div>

      <div className="glass-panel" style={{ marginBottom: '2rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1rem' }}>
          <BarChart3 size={20} color="var(--accent-cyan)" />
          <h3>10-Q Score Table</h3>
        </div>
        <div style={{ overflowX: 'auto' }}>
          <table className="earnings-table">
            <thead><tr><th>Factor</th><th>Value</th><th>Points</th><th>Verdict</th></tr></thead>
            <tbody>
              {(score?.rows || []).filter((row) => row.factor !== 'Risk Language').map((row) => (
                <tr
                  key={row.factor}
                  title={`${row.factor}: ${row.verdict}. Points show earned score out of factor weight. Growth factors reward positive current-vs-prior filing trends.`}
                >
                  <td>{row.factor}</td><td>{typeof row.value === 'number' ? pct(row.value) : row.value ?? 'N/A'}</td><td>{row.points}/{row.weight}</td><td>{row.verdict}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}

function QuarterComparison({ report, history }) {
  if (!report || history.length < 2) return null;
  const sameTicker = history.filter((item) => item.ticker === report.ticker);
  const currentIndex = sameTicker.findIndex((item) => item.id === report.id);
  const previous = currentIndex >= 0 ? sameTicker[currentIndex + 1] : null;
  if (!previous) return null;
  const currentStatements = report.metrics?.statements || {};
  const previousStatements = previous.metrics?.statements || {};
  return (
    <div className="glass-panel" style={{ marginBottom: '2rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem', alignItems: 'center', marginBottom: '1rem' }}>
        <div>
          <div className="metric-label">Stored Quarter Comparison</div>
          <h3>{report.fiscal_quarter || 'Current filing'} vs {previous.fiscal_quarter || 'Previous filing'}</h3>
        </div>
        <div className="metric-label">Current score {report.score?.total ?? 'N/A'} | Previous score {previous.score?.total ?? 'N/A'}</div>
      </div>
      <div className="comparison-strip">
        {statementKeys.map(([key, label]) => {
          const current = currentStatements[key]?.current;
          const prior = previousStatements[key]?.current;
          const change = valueChange(current, prior);
          const color = change === null ? 'var(--text-secondary)' : change >= 0 ? 'var(--status-green)' : 'var(--status-red)';
          return (
            <div className="comparison-card" key={key}>
              <span className="metric-label">{label}</span>
              <strong>{money(current)}</strong>
              <span style={{ color }}>{pct(change)}</span>
              <small>Prev filing: {money(prior)}</small>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function EvolutionCharts({ history, ticker }) {
  const rows = history
    .filter((item) => !ticker || item.ticker === ticker)
    .slice()
    .sort((a, b) => a.id - b.id)
    .map((item) => ({
      period: item.fiscal_quarter || `#${item.id}`,
      revenue: item.metrics?.statements?.revenue?.current ?? null,
      netIncome: item.metrics?.statements?.net_income?.current ?? null,
      operatingCashFlow: item.metrics?.statements?.operating_cash_flow?.current ?? null,
      score: item.score?.total ?? null,
    }));
  if (rows.length < 2) return null;
  return (
    <div className="glass-panel" style={{ marginBottom: '2rem' }}>
      <div className="metric-label">Evolution Graphics</div>
      <h3>{ticker || 'Selected ticker'} quarterly evolution</h3>
      <div className="evolution-grid">
        <div className="chart-box">
          <ResponsiveContainer width="100%" height={260}>
            <ReLineChart data={rows}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" />
              <XAxis dataKey="period" stroke="var(--text-secondary)" tick={{ fontSize: 11 }} />
              <YAxis stroke="var(--text-secondary)" tickFormatter={(value) => money(value)} />
              <Tooltip formatter={(value) => money(value)} contentStyle={{ background: '#12121a', border: '1px solid var(--border-color)' }} />
              <Legend />
              <Line type="monotone" dataKey="revenue" name="Revenue" stroke="var(--accent-cyan)" strokeWidth={2} connectNulls />
              <Line type="monotone" dataKey="netIncome" name="Net Income" stroke="var(--status-green)" strokeWidth={2} connectNulls />
              <Line type="monotone" dataKey="operatingCashFlow" name="Op Cash Flow" stroke="var(--accent-purple)" strokeWidth={2} connectNulls />
            </ReLineChart>
          </ResponsiveContainer>
        </div>
        <div className="chart-box">
          <ResponsiveContainer width="100%" height={260}>
            <ReLineChart data={rows}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" />
              <XAxis dataKey="period" stroke="var(--text-secondary)" tick={{ fontSize: 11 }} />
              <YAxis stroke="var(--text-secondary)" domain={[0, 100]} />
              <Tooltip contentStyle={{ background: '#12121a', border: '1px solid var(--border-color)' }} />
              <Legend />
              <Line type="monotone" dataKey="score" name="Score" stroke="var(--accent-blue)" strokeWidth={3} connectNulls />
            </ReLineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}

export default function QuarterEarnings() {
  const [report, setReport] = useState(null);
  const [history, setHistory] = useState([]);
  const [score, setScore] = useState(null);
  const [analysis, setAnalysis] = useState('');
  const [loading, setLoading] = useState(false);
  const [aiLoading, setAiLoading] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [showTickerModal, setShowTickerModal] = useState(false);
  const [selectedTicker, setSelectedTicker] = useState('');
  const [availableTickers, setAvailableTickers] = useState([]);
  const [dbStatus, setDbStatus] = useState(null);
  const [secTicker, setSecTicker] = useState('ZS');
  const [secMode, setSecMode] = useState('last_4_quarters');
  const [searchResults, setSearchResults] = useState([]);
  const [isSearching, setIsSearching] = useState(false);
  const [showSearchDropdown, setShowSearchDropdown] = useState(false);
  const [searchTimeout, setSearchTimeout] = useState(null);

  const visibleHistory = selectedTicker ? history.filter((item) => item.ticker === selectedTicker) : history;

  const loadDbStatus = async () => {
    try {
      const res = await api.get('/api/quarter-earnings/db-status');
      setDbStatus(res.data);
    } catch {
      setDbStatus(null);
    }
  };

  useEffect(() => {
    loadDbStatus();
  }, []);

  const openTicker = async (ticker) => {
    setLoading(true);
    setError('');
    setNotice('');
    try {
      const res = await api.get(`/api/quarter-earnings/${ticker}/reports`);
      const rows = res.data.reports || [];
      setHistory(rows);
      setSelectedTicker(ticker);
      setReport(rows[0] || null);
      setScore(rows[0]?.score || null);
      setAnalysis('');
      setShowTickerModal(false);
      setNotice(`Loaded ${rows.length} stored 10-Q filings for ${ticker}.`);
    } catch (err) {
      setError(apiError(err));
    }
    setLoading(false);
  };

  const loadExisting = async () => {
    setLoading(true);
    setError('');
    setNotice('');
    setAnalysis('');
    try {
      const res = await api.get('/api/quarter-earnings/tickers');
      const tickers = res.data.tickers || [];
      await loadDbStatus();
      setAvailableTickers(tickers);
      if (tickers.length) {
        setShowTickerModal(true);
        setNotice(`Found ${tickers.length} tickers in DB.`);
      } else {
        setAvailableTickers([]);
        setShowTickerModal(true);
      setNotice('DB is empty. Import SEC filings to create the first stored filing.');
      }
    } catch (err) {
      setError(apiError(err));
    }
    setLoading(false);
  };

  const cleanExisting = async () => {
    if (!window.confirm('Delete all stored quarter earnings filings and analyses?')) return;
    setLoading(true);
    setError('');
    setNotice('');
    setAnalysis('');
    try {
      const res = await api.delete('/api/quarter-earnings/reports');
      setHistory([]);
      setReport(null);
      setScore(null);
      setSelectedTicker('');
      setAvailableTickers([]);
      setShowTickerModal(false);
      setNotice(`Cleaned DB: ${res.data.deleted_reports} filings and ${res.data.deleted_analyses} analyses removed.`);
    } catch (err) {
      setError(apiError(err));
    }
    setLoading(false);
  };

  const importSec = async () => {
    const ticker = secTicker.trim().toUpperCase();
    if (!ticker) {
      setError('Enter a ticker for SEC import.');
      return;
    }
    setLoading(true);
    setError('');
    setNotice('');
    setAnalysis('');
    try {
      const res = await api.post('/api/quarter-earnings/sec/import', { ticker, mode: secMode });
      const rows = res.data.history || [];
      setHistory(rows);
      setSelectedTicker(res.data.ticker);
      setReport(res.data.latest || rows[0] || null);
      setScore(res.data.score || rows[0]?.score || null);
      await loadDbStatus();
      setNotice(`Imported ${res.data.imported} SEC filings for ${res.data.ticker}. Metrics loaded from SEC XBRL.`);
    } catch (err) {
      setError(apiError(err));
    }
    setLoading(false);
  };

  const handleTickerChange = (event) => {
    const value = event.target.value;
    setSecTicker(value.toUpperCase());
    if (searchTimeout) clearTimeout(searchTimeout);
    if (value.trim().length < 1) {
      setSearchResults([]);
      setShowSearchDropdown(false);
      return;
    }
    const timeoutId = setTimeout(async () => {
      setIsSearching(true);
      try {
        const res = await api.get(`/api/stock/search?q=${encodeURIComponent(value)}`);
        setSearchResults(res.data.results || []);
        setShowSearchDropdown(true);
      } catch {
        setSearchResults([]);
      }
      setIsSearching(false);
    }, 400);
    setSearchTimeout(timeoutId);
  };

  const selectTicker = (symbol) => {
    setSecTicker(symbol);
    setSearchResults([]);
    setShowSearchDropdown(false);
  };

  const analyze = async () => {
    if (!report?.id) return;
    setAiLoading(true);
    setError('');
    try {
      const res = await api.post(`/api/quarter-earnings/${report.id}/analyze`, { provider: 'unified' });
      setAnalysis(res.data.analysis);
      setScore(res.data.score);
    } catch (err) {
      setError(apiError(err));
    }
    setAiLoading(false);
  };

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '1rem', marginBottom: '2rem' }}>
        <div>
          <h2>10-Q Filing Intelligence</h2>
          <p className="metric-label">Import public SEC filings into DB, compare quarters, then generate unified Mistral + Groq analysis.</p>
        </div>
        <Landmark color="var(--accent-cyan)" size={34} />
      </div>

      <div className="glass-panel" style={{ marginBottom: '2rem' }}>
        <div className="filing-controls">
          <div style={{ position: 'relative', minWidth: 280 }}>
            <Search size={16} style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-secondary)' }} />
            <input
              aria-label="SEC ticker"
              value={secTicker}
              onChange={handleTickerChange}
              onFocus={() => { if (searchResults.length > 0) setShowSearchDropdown(true); }}
              onBlur={() => setTimeout(() => setShowSearchDropdown(false), 200)}
              placeholder="Company or ticker"
              style={{ width: '100%', paddingLeft: 38 }}
            />
            {showSearchDropdown && searchResults.length > 0 && (
              <ul style={{
                position: 'absolute',
                top: '100%',
                left: 0,
                right: 0,
                maxHeight: '280px',
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
                {searchResults.map((result, index) => (
                  <li
                    key={`${result.symbol}-${index}`}
                    onClick={() => selectTicker(result.symbol)}
                    style={{ padding: '10px 15px', cursor: 'pointer', borderBottom: '1px solid rgba(255,255,255,0.05)' }}
                  >
                    <strong style={{ color: 'var(--accent-cyan)' }}>{result.symbol}</strong>
                    <span style={{ marginLeft: 8, color: 'var(--text-secondary)' }}>{result.name}</span>
                  </li>
                ))}
              </ul>
            )}
            {isSearching && (
              <span style={{ position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)', fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Searching</span>
            )}
          </div>
          <select value={secMode} onChange={(e) => setSecMode(e.target.value)}>
            <option value="last_4_quarters">Last 4 quarters</option>
            <option value="last_quarter">Last quarter</option>
            <option value="this_year_quarters">This year quarters</option>
            <option value="last_year_quarters">Last year quarters</option>
            <option value="last_4_quarters_plus_10k">Last 4 + 10-K</option>
          </select>
          <button className="btn-primary" onClick={importSec} disabled={loading} style={{ background: 'linear-gradient(135deg, var(--accent-cyan), var(--accent-blue))' }}>
            <Database size={18} /> {loading ? 'Importing...' : 'Import SEC'}
          </button>
          <button className="pdf-icon-button" onClick={loadExisting} disabled={loading} title="Load existing filings" type="button">
            <RefreshCw size={22} />
          </button>
          <button className="pdf-icon-button" onClick={cleanExisting} disabled={loading} title="Clean DB" type="button" style={{ color: 'var(--status-red)' }}>
            <Trash2 size={22} />
          </button>
          <button className="btn-primary" onClick={analyze} disabled={!report || aiLoading} style={{ background: 'linear-gradient(135deg, var(--status-green), var(--accent-blue))' }}>
            <Brain size={18} /> {aiLoading ? 'Analyzing...' : 'Unified AI Analysis'}
          </button>
        </div>
        <p className="metric-label" style={{ marginTop: '0.75rem' }}>SEC import uses public EDGAR XBRL for financial metrics and filing text for AI context.</p>
        {dbStatus && (
          <div className="db-status-strip">
            <Database size={18} color={dbStatus.env_configured ? 'var(--status-green)' : 'var(--status-orange)'} />
            <span>
              {dbStatus.backend === 'postgres'
                ? `Postgres configured on backend via ${dbStatus.env_name}.`
                : dbStatus.env_configured
                  ? `SQLite persistent path configured on backend: ${dbStatus.path}`
                  : `SQLite uses default backend path: ${dbStatus.path}. For production, set DATABASE_URL or POSTGRES_URL from Neon.`}
            </span>
            <strong>{dbStatus.report_count} filings</strong>
          </div>
        )}
      </div>

      {notice && <p style={{ color: 'var(--status-green)', marginBottom: '2rem' }}>{notice}</p>}
      {error && <p style={{ color: 'var(--status-red)', marginBottom: '2rem' }}>{error}</p>}

      <FilingBoard report={report} score={score} />
      <QuarterComparison report={report} history={history} />
      <EvolutionCharts history={history} ticker={selectedTicker || report?.ticker} />

      {history.length > 0 && (
        <div className="glass-panel" style={{ marginBottom: '2rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1rem' }}>
            <RefreshCw size={18} color="var(--accent-blue)" />
            <h3>Stored 10-Q Filings</h3>
          </div>
          <div style={{ overflowX: 'auto' }}>
            <table className="earnings-table">
              <thead><tr><th>ID</th><th>Ticker</th><th>Period</th><th>Score</th><th>Company</th><th>Action</th></tr></thead>
              <tbody>
                {visibleHistory.map((item) => (
                  <tr key={item.id}>
                    <td>{item.id}</td>
                    <td>{item.ticker}</td>
                    <td>{item.fiscal_quarter || 'N/A'}</td>
                    <td>{item.score?.total ?? 'N/A'} / 100</td>
                    <td>{item.company_name || 'N/A'}</td>
                    <td><button className="table-action" onClick={() => { setSelectedTicker(item.ticker); setReport(item); setScore(item.score); setAnalysis(''); }}>Open</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {analysis && (
        <div className="glass-panel">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1rem' }}>
            <Database size={18} color="var(--accent-cyan)" />
            <h3>10-Q AI Analysis</h3>
          </div>
          <div className="markdown-content">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{analysis}</ReactMarkdown>
          </div>
        </div>
      )}

      {showTickerModal && (
        <div className="modal-backdrop">
          <div className="ticker-modal glass-panel">
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem', alignItems: 'center', marginBottom: '1rem' }}>
              <div>
                <div className="metric-label">Available DB Tickers</div>
                <h3>Select ticker to load</h3>
              </div>
              <button className="table-action" onClick={() => setShowTickerModal(false)}>Close</button>
            </div>
            <div className="ticker-list">
              {availableTickers.length ? availableTickers.map((group) => (
                <button className="ticker-choice" key={group.ticker} onClick={() => openTicker(group.ticker)}>
                  <strong>{group.ticker}</strong>
                  <span>{group.filing_count} filings</span>
                  <small>Latest DB record #{group.latest_id}</small>
                </button>
              )) : (
                <div className="empty-state">
                  <strong>No tickers stored yet</strong>
                  <span>Import SEC filings to create first stored filing.</span>
                  {dbStatus && dbStatus.backend !== 'postgres' && (
                    <span>Production persistence needs Neon Postgres. Set <code>DATABASE_URL</code> or <code>POSTGRES_URL</code> on backend.</span>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
