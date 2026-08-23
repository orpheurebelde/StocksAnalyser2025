import { useMemo, useState } from 'react';
import { Area, Bar, CartesianGrid, Cell, ComposedChart, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import api from '../api';

const initialInputs = {
  current_price: 0, starting_cf: 0, net_cash: 0, shares_outstanding: 0,
  current_revenue: 0, current_margin: 0, target_margin: 15, tax_rate: 21,
  discount_rate_base: 9, terminal_growth: 2.5,
  fcf_growth_rates: [10, 9, 8, 7, 6], revenue_growth_rates: [15, 13, 11, 9, 7],
};

const money = (value) => {
  if (value == null || !Number.isFinite(Number(value))) return 'N/A';
  const absolute = Math.abs(value);
  if (absolute >= 1e9) return `${value < 0 ? '-' : ''}$${(absolute / 1e9).toFixed(2)}B`;
  if (absolute >= 1e6) return `${value < 0 ? '-' : ''}$${(absolute / 1e6).toFixed(2)}M`;
  return `${value < 0 ? '-' : ''}$${absolute.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
};
const percent = (value) => value == null ? 'N/A' : `${(value * 100).toFixed(1)}%`;
const numberValue = (value) => Number(value) || 0;

function NumericField({ label, value, onChange, suffix, step = 'any', hint }) {
  return (
    <label className="dcf-field">
      <span>{label}</span>
      <div className="dcf-input-wrap">
        <input type="number" step={step} value={value} onChange={(event) => onChange(event.target.value)} />
        {suffix && <small>{suffix}</small>}
      </div>
      {hint && <em>{hint}</em>}
    </label>
  );
}

export default function DCFCalculator() {
  const [ticker, setTicker] = useState('AAPL');
  const [modelType, setModelType] = useState('Standard');
  const [inputs, setInputs] = useState(initialInputs);
  const [infoData, setInfoData] = useState(null);
  const [results, setResults] = useState(null);
  const [fetching, setFetching] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [quotaBlocked, setQuotaBlocked] = useState(false);
  const [quotaRequested, setQuotaRequested] = useState(false);

  const growthRates = modelType === 'Standard' ? inputs.fcf_growth_rates : inputs.revenue_growth_rates;
  const updateInput = (key, value) => setInputs((current) => ({ ...current, [key]: value }));
  const updateGrowth = (index, value) => {
    const key = modelType === 'Standard' ? 'fcf_growth_rates' : 'revenue_growth_rates';
    setInputs((current) => ({ ...current, [key]: current[key].map((rate, position) => position === index ? value : rate) }));
  };

  const fetchStockData = async () => {
    if (!ticker.trim()) return;
    setFetching(true); setError(''); setResults(null);
    try {
      const { data } = await api.get(`/api/stock/${ticker.trim().toUpperCase()}/full-analysis`);
      const info = data.info || {};
      const fcf = numberValue(info.freeCashflow);
      const revenueGrowth = Math.max(-50, Math.min(100, numberValue(info.revenueGrowth || 0.10) * 100));
      const suggested = [revenueGrowth, revenueGrowth * 0.9, revenueGrowth * 0.8, revenueGrowth * 0.7, revenueGrowth * 0.6].map((rate) => Number(rate.toFixed(1)));
      setInfoData(info);
      setModelType(fcf > 0 ? 'Standard' : 'Revenue');
      setInputs((current) => ({
        ...current,
        current_price: numberValue(info.currentPrice || info.regularMarketPrice),
        starting_cf: fcf,
        net_cash: numberValue(info.totalCash) - numberValue(info.totalDebt),
        shares_outstanding: numberValue(info.sharesOutstanding || info.impliedSharesOutstanding),
        current_revenue: numberValue(info.totalRevenue),
        current_margin: numberValue(info.operatingMargins) * 100,
        target_margin: Math.max(10, numberValue(info.operatingMargins) * 100),
        fcf_growth_rates: suggested,
        revenue_growth_rates: suggested,
      }));
    } catch (requestError) {
      setError(requestError.response?.data?.detail || 'Could not preload this ticker.');
    } finally { setFetching(false); }
  };

  const handleCalculate = async () => {
    setLoading(true); setError('');
    const baseRate = numberValue(inputs.discount_rate_base) / 100;
    const payload = {
      ticker: ticker.trim().toUpperCase(), model_type: modelType,
      starting_cf: numberValue(inputs.starting_cf), net_cash: numberValue(inputs.net_cash),
      shares_outstanding: numberValue(inputs.shares_outstanding), current_price: numberValue(inputs.current_price),
      growth_rates: inputs.fcf_growth_rates.map((rate) => numberValue(rate) / 100),
      discount_rates: { Bull: baseRate - 0.01, Base: baseRate, Bear: baseRate + 0.01 },
      terminal_growth: numberValue(inputs.terminal_growth) / 100,
      current_revenue: numberValue(inputs.current_revenue),
      revenue_growth_rates: inputs.revenue_growth_rates.map((rate) => numberValue(rate) / 100),
      current_margin: numberValue(inputs.current_margin) / 100,
      target_margin: numberValue(inputs.target_margin) / 100,
      tax_rate: numberValue(inputs.tax_rate) / 100,
    };
    try {
      const { data } = await api.post('/api/dcf/calculate', payload);
      setResults(data);
    } catch (requestError) {
      const detail = requestError.response?.data?.detail || requestError.message;
      if (requestError.response?.status === 403 && detail.includes('Daily analysis limit')) setQuotaBlocked(true);
      setError(detail);
    } finally { setLoading(false); }
  };

  const requestQuota = async () => { await api.post('/api/auth/analysis-quota/request'); setQuotaRequested(true); };
  const base = results?.scenarios?.Base;
  const chartData = useMemo(() => results?.forecast?.map((row, index) => ({
    name: `Y${row.year}`, FCF: row.fcf, PV: base?.pv_years?.[index],
  })) || [], [results, base]);
  const valueMix = base ? [
    { name: 'Explicit forecast', value: base.pv_years.reduce((sum, value) => sum + value, 0) },
    { name: 'Terminal value', value: base.pv_terminal },
  ] : [];

  return (
    <div className="dcf-page">
      {quotaBlocked && <div className="glass-panel quota-warning"><p>Daily shared analysis limit reached.</p><button type="button" onClick={requestQuota} disabled={quotaRequested}>{quotaRequested ? 'Authorization pending' : 'Request authorization'}</button></div>}
      <header className="dcf-hero">
        <div><span className="dcf-eyebrow">Intrinsic value laboratory</span><h2>5-Year DCF Calculator</h2><p>Company data sets the baseline. Every forecast assumption remains visible and editable.</p></div>
        {infoData && <div className="dcf-quote"><small>{ticker.toUpperCase()} market price</small><strong>${numberValue(inputs.current_price).toFixed(2)}</strong><span>{infoData.shortName || infoData.longName}</span></div>}
      </header>

      <section className="glass-panel dcf-ticker-bar">
        <label><span>Ticker</span><input value={ticker} onChange={(event) => setTicker(event.target.value.toUpperCase())} placeholder="AAPL" /></label>
        <button className="btn-primary" onClick={fetchStockData} disabled={fetching}>{fetching ? 'Loading company data…' : 'Load company data'}</button>
        <div className="dcf-model-tabs" aria-label="Valuation model">
          <button className={modelType === 'Standard' ? 'active' : ''} onClick={() => setModelType('Standard')}>FCF model</button>
          <button className={modelType === 'Revenue' ? 'active' : ''} onClick={() => setModelType('Revenue')}>Revenue model</button>
        </div>
      </section>
      {error && <div className="dcf-alert error">{error}</div>}

      <div className="dcf-workspace">
        <section className="glass-panel dcf-assumptions">
          <div className="dcf-section-title"><div><span>01</span><h3>Company baseline</h3></div><small>Auto-filled · editable</small></div>
          <div className="dcf-fields-grid">
            <NumericField label="Current price" value={inputs.current_price} onChange={(v) => updateInput('current_price', v)} suffix="$ / share" />
            <NumericField label="Net cash (cash − debt)" value={inputs.net_cash} onChange={(v) => updateInput('net_cash', v)} suffix="$" />
            <NumericField label="Diluted shares" value={inputs.shares_outstanding} onChange={(v) => updateInput('shares_outstanding', v)} suffix="shares" />
            {modelType === 'Standard' ?
              <NumericField label="Starting free cash flow" value={inputs.starting_cf} onChange={(v) => updateInput('starting_cf', v)} suffix="$" hint="Latest provider-reported period" /> :
              <><NumericField label="Starting revenue" value={inputs.current_revenue} onChange={(v) => updateInput('current_revenue', v)} suffix="$" /><NumericField label="Current operating margin" value={inputs.current_margin} onChange={(v) => updateInput('current_margin', v)} suffix="%" /></>}
          </div>

          <div className="dcf-section-title"><div><span>02</span><h3>Explicit forecast</h3></div><small>Five annual assumptions</small></div>
          <div className="dcf-growth-grid">
            {growthRates.map((rate, index) => <NumericField key={index} label={`Year ${index + 1}`} value={rate} onChange={(v) => updateGrowth(index, v)} suffix="% growth" step="0.1" />)}
          </div>
          {modelType === 'Revenue' && <div className="dcf-fields-grid compact"><NumericField label="Year 5 target operating margin" value={inputs.target_margin} onChange={(v) => updateInput('target_margin', v)} suffix="%" /><NumericField label="Cash tax rate" value={inputs.tax_rate} onChange={(v) => updateInput('tax_rate', v)} suffix="%" /></div>}

          <div className="dcf-section-title"><div><span>03</span><h3>Valuation assumptions</h3></div><small>WACC ±1% creates scenarios</small></div>
          <div className="dcf-fields-grid compact">
            <NumericField label="Base discount rate (WACC)" value={inputs.discount_rate_base} onChange={(v) => updateInput('discount_rate_base', v)} suffix="%" step="0.1" />
            <NumericField label="Perpetual growth" value={inputs.terminal_growth} onChange={(v) => updateInput('terminal_growth', v)} suffix="%" step="0.1" />
          </div>
          <button className="btn-primary dcf-run" onClick={handleCalculate} disabled={loading || !numberValue(inputs.shares_outstanding)}>{loading ? 'Calculating…' : 'Calculate intrinsic value'}</button>
        </section>

        <aside className="glass-panel dcf-result-panel">
          {!base ? <div className="dcf-empty"><span>DCF</span><h3>Load a company, refine assumptions, calculate.</h3><p>Results will include scenario range, margin of safety and sensitivity.</p></div> : <>
            <span className="dcf-eyebrow">Base case fair value</span>
            <div className="dcf-fair-value">${base.per_share.toFixed(2)}</div>
            <div className={`dcf-mos ${base.upside >= 0 ? 'positive' : 'negative'}`}><span>Margin of safety</span><strong>{percent(base.upside)}</strong></div>
            <div className="dcf-value-scale"><i style={{ left: `${Math.max(2, Math.min(98, 50 + (base.upside || 0) * 50))}%` }} /><span>Overvalued</span><span>Fair value</span><span>Undervalued</span></div>
            <div className="dcf-result-stats"><div><span>Enterprise value</span><strong>{money(base.ev)}</strong></div><div><span>Equity value</span><strong>{money(base.equity)}</strong></div><div><span>Terminal value weight</span><strong>{percent(base.terminal_share)}</strong></div><div><span>Market price</span><strong>${numberValue(inputs.current_price).toFixed(2)}</strong></div></div>
            <div className="dcf-value-mix"><div className="dcf-donut"><ResponsiveContainer width="100%" height="100%"><PieChart><Pie data={valueMix} dataKey="value" innerRadius={42} outerRadius={62} paddingAngle={3} stroke="none">{valueMix.map((item, index) => <Cell key={item.name} fill={index === 0 ? '#32d6c5' : '#5f7cff'} />)}</Pie><Tooltip formatter={(value) => money(value)} contentStyle={{ background: '#111a2b', border: '1px solid #24324a' }} /></PieChart></ResponsiveContainer><strong>{percent(base.terminal_share)}</strong></div><div><span><i className="explicit" />5-year cash flows</span><span><i className="terminal" />Terminal value</span></div></div>
            {results.warnings?.map((warning) => <div className="dcf-alert" key={warning}>⚠ {warning}</div>)}
          </>}
        </aside>
      </div>

      {results && <>
        <section className="dcf-scenarios">
          {['Bear', 'Base', 'Bull'].map((name) => { const scenario = results.scenarios[name]; return <article className={`glass-panel ${name === 'Base' ? 'featured' : ''}`} key={name}><span>{name} case · {percent(scenario.discount_rate)} WACC</span><strong>${scenario.per_share.toFixed(2)}</strong><small className={scenario.upside >= 0 ? 'positive' : 'negative'}>{percent(scenario.upside)} vs market</small></article>; })}
        </section>
        <section className="grid-2 dcf-analysis-grid">
          <div className="glass-panel"><div className="dcf-section-title"><div><span>04</span><h3>5-year cash-flow path</h3></div></div><div className="dcf-chart"><ResponsiveContainer width="100%" height="100%"><ComposedChart data={chartData}><defs><linearGradient id="fcfGradient" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#32d6c5" stopOpacity=".45"/><stop offset="100%" stopColor="#32d6c5" stopOpacity=".02"/></linearGradient></defs><CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,.08)" /><XAxis dataKey="name" stroke="#8291a8" /><YAxis stroke="#8291a8" tickFormatter={(v) => `${(v / 1e9).toFixed(1)}B`} /><Tooltip formatter={(v) => money(v)} contentStyle={{ background: '#111a2b', border: '1px solid #24324a' }} /><Area type="monotone" dataKey="FCF" fill="url(#fcfGradient)" stroke="#32d6c5" strokeWidth={3} /><Bar dataKey="PV" fill="#5f7cff" fillOpacity={0.75} radius={[5,5,0,0]} maxBarSize={38} /></ComposedChart></ResponsiveContainer></div><div className="dcf-chart-legend"><span><i className="fcf" />Projected FCF</span><span><i className="pv" />Discounted value</span></div></div>
          <div className="glass-panel"><div className="dcf-section-title"><div><span>05</span><h3>Forecast detail</h3></div></div><div className="dcf-table-wrap"><table className="dcf-table"><thead><tr><th>Year</th><th>Growth</th>{modelType === 'Revenue' && <th>Revenue</th>}{modelType === 'Revenue' && <th>Margin</th>}<th>FCF</th><th>Present value</th></tr></thead><tbody>{results.forecast.map((row, index) => <tr key={row.year}><td>Y{row.year}</td><td>{percent(row.growth_rate)}</td>{modelType === 'Revenue' && <td>{money(row.revenue)}</td>}{modelType === 'Revenue' && <td>{percent(row.margin)}</td>}<td>{money(row.fcf)}</td><td>{money(base.pv_years[index])}</td></tr>)}</tbody></table></div></div>
        </section>
        {results.sensitivity && <section className="glass-panel"><div className="dcf-section-title"><div><span>06</span><h3>Fair-value sensitivity</h3></div><small>Rows: WACC · Columns: perpetual growth</small></div><div className="dcf-table-wrap"><table className="dcf-table sensitivity"><thead><tr><th>WACC \ g</th>{results.sensitivity.terminal_growth_rates.map((g) => <th key={g}>{percent(g)}</th>)}</tr></thead><tbody>{results.sensitivity.discount_rates.map((rate, rowIndex) => <tr key={rate}><th>{percent(rate)}</th>{results.sensitivity.values[rowIndex].map((value, columnIndex) => <td className={rate === numberValue(inputs.discount_rate_base) / 100 && results.sensitivity.terminal_growth_rates[columnIndex] === numberValue(inputs.terminal_growth) / 100 ? 'selected' : ''} key={columnIndex}>{value == null ? '—' : `$${value.toFixed(2)}`}</td>)}</tr>)}</tbody></table></div></section>}
      </>}
    </div>
  );
}
