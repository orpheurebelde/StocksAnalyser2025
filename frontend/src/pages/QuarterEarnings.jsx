import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Brain, Database, FileSearch, LineChart, RefreshCw } from 'lucide-react';
import api from '../api';

const pct = (value) => (value === null || value === undefined ? 'N/A' : `${(value * 100).toFixed(1)}%`);
const money = (value) => {
  if (value === null || value === undefined) return 'N/A';
  const abs = Math.abs(value);
  if (abs >= 1e9) return `$${(value / 1e9).toFixed(2)}B`;
  if (abs >= 1e6) return `$${(value / 1e6).toFixed(2)}M`;
  return `$${Number(value).toLocaleString()}`;
};

function ScoreTable({ score }) {
  if (!score) return null;
  return (
    <div className="glass-panel" style={{ marginBottom: '2rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem', alignItems: 'center', marginBottom: '1rem' }}>
        <div>
          <div className="metric-label">Quarter Statement Score</div>
          <h3>{score.label}</h3>
        </div>
        <div style={{ fontSize: '2.4rem', fontWeight: 800, color: score.total >= 65 ? 'var(--status-green)' : score.total >= 50 ? 'var(--status-orange)' : 'var(--status-red)' }}>
          {score.total}/{score.max}
        </div>
      </div>
      <div style={{ overflowX: 'auto' }}>
        <table className="earnings-table">
          <thead>
            <tr>
              <th>Factor</th>
              <th>Value</th>
              <th>Weight</th>
              <th>Points</th>
              <th>Verdict</th>
            </tr>
          </thead>
          <tbody>
            {score.rows.map((row) => (
              <tr key={row.factor}>
                <td>{row.factor}</td>
                <td>{pct(row.value)}</td>
                <td>{row.weight}</td>
                <td>{row.points}</td>
                <td>{row.verdict}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function MetricEvolution({ metrics }) {
  const rows = ['revenue', 'gross_profit', 'operating_income', 'net_income', 'free_cash_flow', 'cash', 'total_debt'];
  if (!metrics) return null;
  return (
    <div className="glass-panel" style={{ marginBottom: '2rem' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1rem' }}>
        <LineChart size={20} color="var(--accent-cyan)" />
        <h3>Quarter Evolution</h3>
      </div>
      <div style={{ overflowX: 'auto' }}>
        <table className="earnings-table">
          <thead>
            <tr>
              <th>Metric</th>
              <th>Latest</th>
              <th>Previous</th>
              <th>Two Quarters Ago</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((key) => {
              const values = metrics[key] || [];
              return (
                <tr key={key}>
                  <td>{key.replaceAll('_', ' ')}</td>
                  <td>{values[0] ? `${money(values[0].value)} (${values[0].period})` : 'N/A'}</td>
                  <td>{values[1] ? `${money(values[1].value)} (${values[1].period})` : 'N/A'}</td>
                  <td>{values[2] ? `${money(values[2].value)} (${values[2].period})` : 'N/A'}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function QuarterEarnings() {
  const [ticker, setTicker] = useState('AAPL');
  const [sourceUrl, setSourceUrl] = useState('');
  const [manualText, setManualText] = useState('');
  const [provider, setProvider] = useState('mistral');
  const [report, setReport] = useState(null);
  const [history, setHistory] = useState([]);
  const [score, setScore] = useState(null);
  const [analysis, setAnalysis] = useState('');
  const [loading, setLoading] = useState(false);
  const [aiLoading, setAiLoading] = useState(false);
  const [error, setError] = useState('');

  const ingest = async () => {
    setLoading(true);
    setError('');
    setAnalysis('');
    try {
      const res = await api.post(`/api/quarter-earnings/${ticker.toUpperCase()}/ingest`, {
        source_url: sourceUrl.trim() || null,
        manual_text: manualText.trim() || null,
      });
      setReport(res.data);
      setScore(res.data.score);
      setHistory(res.data.history || []);
    } catch (err) {
      setError(err.response?.data?.detail || err.message);
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
      setError(err.response?.data?.detail || err.message);
    }
    setAiLoading(false);
  };

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '1rem', marginBottom: '2rem' }}>
        <div>
          <h2>Quarter Earnings Intelligence</h2>
          <p className="metric-label">Read latest quarterly data, store it in SQLite, score performance, then analyze with Mistral or Groq.</p>
        </div>
        <Database color="var(--accent-cyan)" size={32} />
      </div>

      <div className="glass-panel" style={{ marginBottom: '2rem' }}>
        <div className="earnings-controls">
          <input value={ticker} onChange={(e) => setTicker(e.target.value)} placeholder="Ticker, e.g. MSFT" />
          <input value={sourceUrl} onChange={(e) => setSourceUrl(e.target.value)} placeholder="Optional earnings report URL" />
          <select value={provider} onChange={(e) => setProvider(e.target.value)}>
            <option value="mistral">Mistral</option>
            <option value="groq">Groq</option>
          </select>
          <button className="btn-primary" onClick={ingest} disabled={loading}>
            <FileSearch size={18} /> {loading ? 'Reading...' : 'Read & Store'}
          </button>
          <button className="btn-primary" onClick={analyze} disabled={!report || aiLoading} style={{ background: 'linear-gradient(135deg, var(--status-green), var(--accent-blue))' }}>
            <Brain size={18} /> {aiLoading ? 'Analyzing...' : `Analyze with ${provider}`}
          </button>
        </div>
        <textarea
          value={manualText}
          onChange={(e) => setManualText(e.target.value)}
          placeholder="Manual report text fallback: paste the earnings release, quarterly report, or transcript here when the website blocks network reading."
          style={{ width: '100%', minHeight: '160px', marginTop: '1rem', background: 'rgba(0,0,0,0.3)', color: 'white', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '1rem', fontFamily: 'var(--font-body)', resize: 'vertical' }}
        />
        <p className="metric-label" style={{ marginTop: '0.75rem' }}>
          Manual text wins over URL. Keep URL filled only as source reference when pasting content.
        </p>
      </div>

      {error && <p style={{ color: 'var(--status-red)', marginBottom: '2rem' }}>{error}</p>}

      {report && (
        <div className="grid-4" style={{ marginBottom: '2rem' }}>
          <div className="glass-panel metric-card">
            <span className="metric-label">Company</span>
            <span className="metric-value" style={{ fontSize: '1.4rem' }}>{report.company_name}</span>
          </div>
          <div className="glass-panel metric-card">
            <span className="metric-label">Quarter</span>
            <span className="metric-value" style={{ fontSize: '1.4rem' }}>{report.fiscal_quarter || 'N/A'}</span>
          </div>
          <div className="glass-panel metric-card">
            <span className="metric-label">Sector</span>
            <span className="metric-value" style={{ fontSize: '1.4rem' }}>{report.sector || 'N/A'}</span>
          </div>
          <div className="glass-panel metric-card">
            <span className="metric-label">Source</span>
            <span className="metric-value" style={{ fontSize: '1.2rem' }}>{report.source_type}</span>
          </div>
        </div>
      )}

      <ScoreTable score={score} />
      <MetricEvolution metrics={report?.metrics} />

      {history.length > 0 && (
        <div className="glass-panel" style={{ marginBottom: '2rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1rem' }}>
            <RefreshCw size={18} color="var(--accent-blue)" />
            <h3>Stored Reports</h3>
          </div>
          <div style={{ overflowX: 'auto' }}>
            <table className="earnings-table">
              <thead>
                <tr><th>ID</th><th>Ticker</th><th>Quarter</th><th>Sector</th><th>Created</th></tr>
              </thead>
              <tbody>
                {history.map((item) => (
                  <tr key={item.id}><td>{item.id}</td><td>{item.ticker}</td><td>{item.fiscal_quarter || 'N/A'}</td><td>{item.sector || 'N/A'}</td><td>{item.created_at}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {analysis && (
        <div className="glass-panel">
          <h3 style={{ marginBottom: '1rem' }}>Agent Guidance</h3>
          <div className="markdown-content">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{analysis}</ReactMarkdown>
          </div>
        </div>
      )}
    </div>
  );
}
