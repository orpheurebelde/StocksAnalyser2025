import React, { useState } from 'react';
import api from '../api';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

export default function DCFCalculator() {
  const [ticker, setTicker] = useState('AAPL');
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [fetching, setFetching] = useState(false);
  const [modelType, setModelType] = useState('Standard');
  const [infoData, setInfoData] = useState(null);

  const [inputs, setInputs] = useState({
    // Shared
    net_cash: 50000000,
    shares_outstanding: 15000000,
    terminal_growth: 2.5,
    discount_rate_base: 9,

    // Standard specific
    starting_cf: 100000000,
    fcf_growth: 10,

    // Revenue specific
    current_revenue: 1000000000,
    revenue_growth: 15,
    current_margin: -5,
    target_margin: 15,
    tax_rate: 21,
  });

  const fetchStockData = async () => {
    if (!ticker.trim()) return;
    setFetching(true);
    setResults(null);
    try {
      const res = await api.get(`/api/stock/${ticker.toUpperCase()}/full-analysis`);
      const info = res.data.info;
      setInfoData(info);
      
      const fcf = info.freeCashflow || 0;
      const tCash = info.totalCash || 0;
      const tDebt = info.totalDebt || 0;
      const shares = info.sharesOutstanding || info.impliedSharesOutstanding || 0;
      const rev = info.totalRevenue || 0;
      const revGrowth = info.revenueGrowth || 0.10;
      const margin = info.operatingMargins || 0;

      const newModelType = fcf > 0 ? 'Standard' : 'Revenue';
      setModelType(newModelType);
      
      setInputs({
        ...inputs,
        starting_cf: fcf,
        net_cash: tCash - tDebt,
        shares_outstanding: shares,
        current_revenue: rev,
        revenue_growth: (revGrowth > 0 ? revGrowth : 0.10) * 100,
        current_margin: margin * 100,
        fcf_growth: (revGrowth > 0 ? revGrowth : 0.10) * 100,
      });
    } catch (err) {
      console.error("Failed to preload:", err);
      alert("Failed to preload stock data. Ensure the ticker is valid.");
    }
    setFetching(false);
  };

  const handleCalculate = async () => {
    setLoading(true);
    try {
      const baseDiscount = Number(inputs.discount_rate_base) / 100;
      const payload = {
        ticker,
        model_type: modelType,
        starting_cf: Number(inputs.starting_cf),
        net_cash: Number(inputs.net_cash),
        shares_outstanding: Number(inputs.shares_outstanding),
        growth_rates: Array(5).fill(Number(inputs.fcf_growth) / 100), // simple 5 yr projection
        discount_rates: { Bull: baseDiscount - 0.01, Base: baseDiscount, Bear: baseDiscount + 0.01 },
        terminal_growth: Number(inputs.terminal_growth) / 100,
        
        // Revenue Model Specific
        current_revenue: Number(inputs.current_revenue),
        revenue_growth: Number(inputs.revenue_growth) / 100,
        current_margin: Number(inputs.current_margin) / 100,
        target_margin: Number(inputs.target_margin) / 100,
        tax_rate: Number(inputs.tax_rate) / 100
      };

      const res = await api.post(`/api/dcf/calculate`, payload);
      setResults(res.data);
    } catch (err) {
      console.error(err);
      alert("Error calculating DCF: " + (err.response?.data?.detail || err.message));
    }
    setLoading(false);
  };

  const getChartData = () => {
    if (!results || !results.Base) return [];
    const base = results.Base;
    const data = base.pv_years.map((val, idx) => ({
      name: `Year ${idx + 1}`,
      PV: val
    }));
    data.push({ name: 'Terminal', PV: base.pv_terminal });
    return data;
  };

  const formatBil = (val) => val != null ? `$${(val / 1e9).toFixed(2)}B` : 'N/A';
  const formatPct = (val) => val != null ? `${(val * 100).toFixed(2)}%` : 'N/A';

  return (
    <div>
      <h2 style={{ marginBottom: '2rem' }}>📉 Dual-Model DCF Valuation</h2>
      
      <div className="glass-panel" style={{ display: 'flex', gap: '1rem', marginBottom: '2rem', alignItems: 'center' }}>
        <input 
          type="text" 
          value={ticker} 
          onChange={(e) => setTicker(e.target.value)}
          placeholder="Enter Ticker (e.g. AAPL)"
          style={{ maxWidth: '300px' }}
        />
        <button className="btn-primary" onClick={fetchStockData} disabled={fetching}>
          {fetching ? 'Preloading...' : 'Preload Ticker Data'}
        </button>
        {infoData && (
          <div style={{ marginLeft: 'auto', display: 'flex', gap: '1rem', alignItems: 'center' }}>
             <span className="metric-label">Auto-Selected Model:</span>
             <span style={{ 
               padding: '0.4rem 1rem', 
               background: modelType === 'Standard' ? 'var(--status-green)' : 'var(--accent-purple)', 
               borderRadius: '20px', 
               fontWeight: 'bold',
               color: 'white'
             }}>
               {modelType} {modelType === 'Standard' ? '(FCF)' : '(Revenue Convergence)'}
             </span>
          </div>
        )}
      </div>

      <div className="grid-2" style={{ gap: '2rem', marginBottom: '2rem' }}>
        {/* Core Metrics (Read-only reference) */}
        <div className="glass-panel" style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <h3 className="metric-label" style={{ color: 'var(--accent-cyan)' }}>Fundamental Data (Auto-Filled)</h3>
          
          <div className="grid-2">
            <div>
              <label className="metric-label">Net Cash (Cash - Debt)</label>
              <div style={{ fontSize: '1.2rem', fontWeight: 'bold' }}>{formatBil(inputs.net_cash)}</div>
            </div>
            <div>
              <label className="metric-label">Shares Outstanding</label>
              <div style={{ fontSize: '1.2rem', fontWeight: 'bold' }}>{(inputs.shares_outstanding / 1e6).toFixed(2)}M</div>
            </div>
            
            {modelType === 'Standard' ? (
              <div>
                <label className="metric-label">Starting FCF (TTM)</label>
                <div style={{ fontSize: '1.2rem', fontWeight: 'bold', color: 'var(--status-green)' }}>{formatBil(inputs.starting_cf)}</div>
              </div>
            ) : (
              <>
                <div>
                  <label className="metric-label">TTM Revenue</label>
                  <div style={{ fontSize: '1.2rem', fontWeight: 'bold' }}>{formatBil(inputs.current_revenue)}</div>
                </div>
                <div>
                  <label className="metric-label">Current Operating Margin</label>
                  <div style={{ fontSize: '1.2rem', fontWeight: 'bold', color: inputs.current_margin < 0 ? 'var(--status-red)' : 'var(--status-green)' }}>
                    {formatPct(inputs.current_margin / 100)}
                  </div>
                </div>
              </>
            )}
          </div>
        </div>

        {/* Projection Inputs (Editable) */}
        <div className="glass-panel" style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <h3 className="metric-label" style={{ color: 'var(--accent-blue)' }}>User Assumptions (Editable)</h3>
          
          <div className="grid-2">
            {modelType === 'Standard' ? (
              <div>
                <label className="metric-label">Year 1-5 FCF Growth Rate (%)</label>
                <input type="number" step="0.1" value={inputs.fcf_growth} onChange={e => setInputs({...inputs, fcf_growth: e.target.value})} />
              </div>
            ) : (
              <>
                <div>
                  <label className="metric-label">Year 1-5 Rev Growth Rate (%)</label>
                  <input type="number" step="0.1" value={inputs.revenue_growth} onChange={e => setInputs({...inputs, revenue_growth: e.target.value})} />
                </div>
                <div>
                  <label className="metric-label">Target Margin Year 5 (%)</label>
                  <input type="number" step="0.1" value={inputs.target_margin} onChange={e => setInputs({...inputs, target_margin: e.target.value})} />
                </div>
                <div>
                  <label className="metric-label">Tax Rate (%)</label>
                  <input type="number" step="0.1" value={inputs.tax_rate} onChange={e => setInputs({...inputs, tax_rate: e.target.value})} />
                </div>
              </>
            )}
            <div>
              <label className="metric-label">Discount Rate Base (%)</label>
              <input type="number" step="0.1" value={inputs.discount_rate_base} onChange={e => setInputs({...inputs, discount_rate_base: e.target.value})} />
            </div>
            <div>
              <label className="metric-label">Terminal Growth Rate (%)</label>
              <input type="number" step="0.1" value={inputs.terminal_growth} onChange={e => setInputs({...inputs, terminal_growth: e.target.value})} />
            </div>
          </div>
        </div>
      </div>

      <button className="btn-primary" onClick={handleCalculate} disabled={loading} style={{ marginBottom: '2rem', width: '100%', fontSize: '1.2rem', padding: '1rem' }}>
        {loading ? 'Calculating Valuation...' : 'Run Valuation'}
      </button>

      {results && (
        <>
          <div className="grid-3" style={{ marginBottom: '2rem' }}>
            {Object.entries(results).map(([scenario, data]) => {
               // Assuming inputs.currentPrice is not tracked here natively, we can use infoData if available to show upside/downside
               const currentPrice = infoData?.currentPrice || 0;
               const impliedPrice = data.per_share || 0;
               const upside = currentPrice > 0 ? ((impliedPrice - currentPrice) / currentPrice) * 100 : 0;
               const isUpside = upside > 0;

               return (
                <div key={scenario} className="glass-panel" style={{ borderTop: `4px solid ${scenario === 'Base' ? 'var(--accent-cyan)' : 'transparent'}` }}>
                  <h3 className="metric-label">{scenario} Scenario</h3>
                  <div className="metric-value" style={{ color: scenario === 'Base' ? 'var(--accent-cyan)' : 'white' }}>
                    ${impliedPrice.toFixed(2)}
                  </div>
                  <p className="metric-label" style={{ marginTop: '0.2rem' }}>Implied Share Price</p>
                  
                  {currentPrice > 0 && (
                    <div style={{ marginTop: '0.5rem', fontWeight: 'bold', color: isUpside ? 'var(--status-green)' : 'var(--status-red)' }}>
                      {isUpside ? '▲' : '▼'} {Math.abs(upside).toFixed(2)}% vs Current (${currentPrice.toFixed(2)})
                    </div>
                  )}

                  <div style={{ marginTop: '1.5rem', borderTop: '1px solid rgba(255,255,255,0.1)', paddingTop: '1rem' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.9rem', marginBottom: '0.5rem' }}>
                      <span className="metric-label">Enterprise Value:</span>
                      <span style={{ fontWeight: 'bold' }}>{formatBil(data.ev)}</span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.9rem' }}>
                      <span className="metric-label">Equity Value:</span>
                      <span style={{ fontWeight: 'bold' }}>{formatBil(data.equity)}</span>
                    </div>
                  </div>
                </div>
               );
            })}
          </div>

          <div className="glass-panel">
            <h3 className="metric-label" style={{ marginBottom: '1rem' }}>Present Value of Cash Flows (Base Scenario)</h3>
            <div style={{ height: '400px', width: '100%' }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={getChartData()} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                  <XAxis dataKey="name" stroke="rgba(255,255,255,0.5)" />
                  <YAxis stroke="rgba(255,255,255,0.5)" tickFormatter={(val) => `$${(val/1e9).toFixed(1)}B`} />
                  <Tooltip 
                    contentStyle={{ backgroundColor: 'rgba(0,0,0,0.8)', border: '1px solid var(--border-color)', borderRadius: '8px' }}
                    formatter={(val) => [`$${(val/1e9).toFixed(2)}B`, 'Present Value']}
                  />
                  <Bar dataKey="PV" fill="var(--accent-blue)" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
