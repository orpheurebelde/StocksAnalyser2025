import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { BarChart3, Brain, Database, FileUp, Landmark, RefreshCw, ShieldAlert } from 'lucide-react';
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
  const riskHits = (filing.risk_terms || []).filter((item) => item.count > 0);
  return (
    <>
      <div className="filing-hero glass-panel">
        <div>
          <div className="metric-label">Uploaded 10-Q Filing</div>
          <h2>{filing.company_name || report.company_name}</h2>
          <p>{filing.form_type || '10-Q'} | {filing.fiscal_quarter || 'Period not extracted'} | {filing.filename || 'PDF'}</p>
        </div>
        <div className="filing-score">
          <span>{score?.total ?? 'N/A'}</span>
          <small>{score?.label || 'Not scored'}</small>
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

      <div className="grid-2" style={{ marginBottom: '2rem' }}>
        <div className="glass-panel">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1rem' }}>
            <BarChart3 size={20} color="var(--accent-cyan)" />
            <h3>10-Q Score Table</h3>
          </div>
          <div style={{ overflowX: 'auto' }}>
            <table className="earnings-table">
              <thead><tr><th>Factor</th><th>Value</th><th>Points</th><th>Verdict</th></tr></thead>
              <tbody>
                {(score?.rows || []).map((row) => (
                  <tr key={row.factor}><td>{row.factor}</td><td>{typeof row.value === 'number' && row.factor !== 'Risk Language' ? pct(row.value) : row.value ?? 'N/A'}</td><td>{row.points}/{row.weight}</td><td>{row.verdict}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="glass-panel">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1rem' }}>
            <ShieldAlert size={20} color="var(--status-orange)" />
            <h3>Risk Language</h3>
          </div>
          {riskHits.length ? riskHits.map((item) => (
            <div className="risk-row" key={item.term}><span>{item.term}</span><strong>{item.count}</strong></div>
          )) : <p className="metric-label">No tracked risk terms found in extracted text.</p>}
          <p className="metric-label" style={{ marginTop: '1rem' }}>Extraction reads selectable PDF text. Values can need analyst review when table columns are ambiguous.</p>
        </div>
      </div>
    </>
  );
}

function QuarterComparison({ report, history }) {
  if (!report || history.length < 2) return null;
  const previous = history.find((item) => item.id !== report.id);
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

export default function QuarterEarnings() {
  const [ticker, setTicker] = useState('AAPL');
  const [pdfFile, setPdfFile] = useState(null);
  const [provider, setProvider] = useState('mistral');
  const [report, setReport] = useState(null);
  const [history, setHistory] = useState([]);
  const [score, setScore] = useState(null);
  const [analysis, setAnalysis] = useState('');
  const [loading, setLoading] = useState(false);
  const [aiLoading, setAiLoading] = useState(false);
  const [error, setError] = useState('');

  const loadExisting = async () => {
    setLoading(true);
    setError('');
    setAnalysis('');
    try {
      const res = await api.get(`/api/quarter-earnings/${ticker.toUpperCase()}/reports`);
      const reports = res.data.reports || [];
      setHistory(reports);
      if (reports.length) {
        setReport(reports[0]);
        setScore(reports[0].score);
      } else {
        setReport(null);
        setScore(null);
        setError(`No stored 10-Q filings found for ${ticker.toUpperCase()}.`);
      }
    } catch (err) {
      setError(apiError(err));
    }
    setLoading(false);
  };

  const ingestPdf = async () => {
    if (!pdfFile) {
      setError('Choose a 10-Q PDF first.');
      return;
    }
    setLoading(true);
    setError('');
    setAnalysis('');
    try {
      const formData = new FormData();
      formData.append('file', pdfFile);
      const res = await api.post(`/api/quarter-earnings/${ticker.toUpperCase()}/ingest-pdf`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setReport(res.data);
      setScore(res.data.score);
      setHistory(res.data.history || []);
    } catch (err) {
      setError(apiError(err));
    }
    setLoading(false);
  };

  const analyze = async () => {
    if (!report?.id) return;
    setAiLoading(true);
    setError('');
    try {
      const res = await api.post(`/api/quarter-earnings/${report.id}/analyze`, { provider });
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
          <p className="metric-label">Upload one 10-Q PDF, extract filing data into SQLite, interpret board, then analyze with Mistral or Groq.</p>
        </div>
        <Landmark color="var(--accent-cyan)" size={34} />
      </div>

      <div className="glass-panel" style={{ marginBottom: '2rem' }}>
        <div className="filing-controls">
          <input value={ticker} onChange={(e) => setTicker(e.target.value)} placeholder="Ticker, e.g. MU" />
          <input type="file" accept="application/pdf,.pdf" onChange={(e) => setPdfFile(e.target.files?.[0] || null)} />
          <select value={provider} onChange={(e) => setProvider(e.target.value)}>
            <option value="mistral">Mistral</option>
            <option value="groq">Groq</option>
          </select>
          <button className="btn-primary" onClick={ingestPdf} disabled={loading || !pdfFile}>
            <FileUp size={18} /> {loading ? 'Reading 10-Q...' : 'Load 10-Q PDF'}
          </button>
          <button className="btn-primary" onClick={loadExisting} disabled={loading} style={{ background: 'linear-gradient(135deg, var(--accent-purple), var(--accent-blue))' }}>
            <RefreshCw size={18} /> {loading ? 'Loading...' : 'Load Existing'}
          </button>
          <button className="btn-primary" onClick={analyze} disabled={!report || aiLoading} style={{ background: 'linear-gradient(135deg, var(--status-green), var(--accent-blue))' }}>
            <Brain size={18} /> {aiLoading ? 'Analyzing...' : `Analyze with ${provider}`}
          </button>
        </div>
        <p className="metric-label" style={{ marginTop: '0.75rem' }}>Only uploaded 10-Q PDFs are supported. Web scraping and manual text loading removed.</p>
      </div>

      {error && <p style={{ color: 'var(--status-red)', marginBottom: '2rem' }}>{error}</p>}

      <FilingBoard report={report} score={score} />
      <QuarterComparison report={report} history={history} />

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
                {history.map((item) => (
                  <tr key={item.id}>
                    <td>{item.id}</td>
                    <td>{item.ticker}</td>
                    <td>{item.fiscal_quarter || 'N/A'}</td>
                    <td>{item.score?.total ?? 'N/A'} / 100</td>
                    <td>{item.company_name || 'N/A'}</td>
                    <td><button className="table-action" onClick={() => { setReport(item); setScore(item.score); setAnalysis(''); }}>Open</button></td>
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
    </div>
  );
}
