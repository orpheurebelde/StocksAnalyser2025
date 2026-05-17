import React, { useEffect, useState } from 'react';
import api from '../api';
import { PieChart, Pie, Cell, ResponsiveContainer } from 'recharts';

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [sentiment, setSentiment] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    // Fetch both simultaneously
    Promise.all([
      api.get('/api/market/analysis'),
      api.get('/api/market/sentiment').catch(() => ({ data: null }))
    ])
      .then(([marketRes, sentimentRes]) => {
        setData(marketRes.data);
        if (sentimentRes.data) setSentiment(sentimentRes.data);
        setLoading(false);
      })
      .catch(err => {
        console.error(err);
        setError(err.response?.data?.detail || err.message);
        setLoading(false);
      });
  }, []);

  const formatPct = (val) => {
    if (val === null || val === undefined) return 'N/A';
    return (val > 0 ? '+' : '') + val.toFixed(2) + '%';
  };

  const getColor = (val) => {
    if (val === null || val === undefined) return 'white';
    return val > 0 ? 'var(--status-green)' : 'var(--status-red)';
  };

  return (
    <div>
      <h2 style={{ marginBottom: '2rem' }}>📈 Market Analysis | Buy Signals</h2>
      
      {loading ? <p>Loading Market Data...</p> : error ? <p style={{ color: 'var(--status-red)' }}>Error: {error}</p> : data && (
        <>
          <div className="grid-3" style={{ marginBottom: '2rem', gap: '2rem' }}>
            {/* VIX Card */}
            {(() => {
              const val = data?.vix || 0;
              let statusClass = 'glow-orange';
              let fill = 'var(--accent-orange)';
              let label = 'Neutral Zone';
              if (val > 28) { statusClass = 'glow-red'; fill = 'var(--status-red)'; label = 'Fear Zone'; }
              else if (val < 15) { statusClass = 'glow-green'; fill = 'var(--status-green)'; label = 'Greed Zone'; }
              
              const gaugeData = [
                { name: 'Value', value: val },
                { name: 'Empty', value: Math.max(0, 50 - val) }
              ];

              return (
                <div className={`glass-panel ${statusClass}`} style={{ textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                  <h3 className="metric-label" style={{ marginBottom: '1rem' }}>Volatility Index (VIX)</h3>
                  <div style={{ width: '100%', height: '150px', position: 'relative' }}>
                    <ResponsiveContainer width="100%" height="100%">
                      <PieChart>
                        <Pie data={gaugeData} cx="50%" cy="100%" startAngle={180} endAngle={0} innerRadius={60} outerRadius={80} paddingAngle={0} dataKey="value" stroke="none">
                          <Cell fill={fill} />
                          <Cell fill="rgba(255,255,255,0.1)" />
                        </Pie>
                      </PieChart>
                    </ResponsiveContainer>
                    <div style={{ position: 'absolute', bottom: '10px', left: '50%', transform: 'translateX(-50%)', fontSize: '2.5rem', fontWeight: 'bold', color: fill }}>
                      {data.vix ? data.vix.toFixed(2) : 'N/A'}
                    </div>
                  </div>
                  <p className="metric-label" style={{ marginTop: '0.5rem', fontSize: '1.2rem' }}>{label}</p>
                </div>
              );
            })()}

            {/* S&P 500 RSI Card */}
            {(() => {
              const spData = data?.indices?.['S&P 500'];
              const val = spData?.rsi || 0;
              let statusClass = 'glow-orange';
              let fill = 'var(--accent-orange)';
              let label = 'Neutral';
              if (val > 70) { statusClass = 'glow-red'; fill = 'var(--status-red)'; label = 'Overbought / Bearish'; }
              else if (val < 30) { statusClass = 'glow-green'; fill = 'var(--status-green)'; label = 'Oversold / Bullish'; }
              
              const gaugeData = [
                { name: 'Value', value: val },
                { name: 'Empty', value: Math.max(0, 100 - val) }
              ];

              return (
                <div className={`glass-panel ${statusClass}`} style={{ textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                  <h3 className="metric-label" style={{ marginBottom: '1rem' }}>S&P 500 RSI</h3>
                  <div style={{ width: '100%', height: '150px', position: 'relative' }}>
                    <ResponsiveContainer width="100%" height="100%">
                      <PieChart>
                        <Pie data={gaugeData} cx="50%" cy="100%" startAngle={180} endAngle={0} innerRadius={60} outerRadius={80} paddingAngle={0} dataKey="value" stroke="none">
                          <Cell fill={fill} />
                          <Cell fill="rgba(255,255,255,0.1)" />
                        </Pie>
                      </PieChart>
                    </ResponsiveContainer>
                    <div style={{ position: 'absolute', bottom: '10px', left: '50%', transform: 'translateX(-50%)', fontSize: '2.5rem', fontWeight: 'bold', color: fill }}>
                      {spData?.rsi ? spData.rsi.toFixed(2) : 'N/A'}
                    </div>
                  </div>
                  <p className="metric-label" style={{ marginTop: '0.5rem', fontSize: '1.2rem' }}>{label}</p>
                </div>
              );
            })()}

            {/* Nasdaq 100 RSI Card */}
            {(() => {
              const ndxData = data?.indices?.['Nasdaq 100'];
              const val = ndxData?.rsi || 0;
              let statusClass = 'glow-orange';
              let fill = 'var(--accent-orange)';
              let label = 'Neutral';
              if (val > 70) { statusClass = 'glow-red'; fill = 'var(--status-red)'; label = 'Overbought / Bearish'; }
              else if (val < 30) { statusClass = 'glow-green'; fill = 'var(--status-green)'; label = 'Oversold / Bullish'; }
              
              const gaugeData = [
                { name: 'Value', value: val },
                { name: 'Empty', value: Math.max(0, 100 - val) }
              ];

              return (
                <div className={`glass-panel ${statusClass}`} style={{ textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                  <h3 className="metric-label" style={{ marginBottom: '1rem' }}>Nasdaq 100 RSI</h3>
                  <div style={{ width: '100%', height: '150px', position: 'relative' }}>
                    <ResponsiveContainer width="100%" height="100%">
                      <PieChart>
                        <Pie data={gaugeData} cx="50%" cy="100%" startAngle={180} endAngle={0} innerRadius={60} outerRadius={80} paddingAngle={0} dataKey="value" stroke="none">
                          <Cell fill={fill} />
                          <Cell fill="rgba(255,255,255,0.1)" />
                        </Pie>
                      </PieChart>
                    </ResponsiveContainer>
                    <div style={{ position: 'absolute', bottom: '10px', left: '50%', transform: 'translateX(-50%)', fontSize: '2.5rem', fontWeight: 'bold', color: fill }}>
                      {ndxData?.rsi ? ndxData.rsi.toFixed(2) : 'N/A'}
                    </div>
                  </div>
                  <p className="metric-label" style={{ marginTop: '0.5rem', fontSize: '1.2rem' }}>{label}</p>
                </div>
              );
            })()}
          </div>

          {sentiment && (
            <div className="glass-panel" style={{ marginBottom: '2rem' }}>
              <h3 className="metric-label" style={{ marginBottom: '1rem' }}>AAII Investor Sentiment Survey</h3>
              <p style={{ color: 'var(--text-secondary)', marginBottom: '1rem' }}>Data for week of {sentiment.date.substring(0,10)}</p>
              <div style={{ display: 'flex', alignItems: 'center', width: '100%', height: '40px', borderRadius: '20px', overflow: 'hidden', marginBottom: '1rem' }}>
                <div style={{ width: `${sentiment.bullish}%`, height: '100%', backgroundColor: 'var(--status-green)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 'bold' }}>
                  {sentiment.bullish > 10 ? `${sentiment.bullish}%` : ''}
                </div>
                <div style={{ width: `${sentiment.neutral}%`, height: '100%', backgroundColor: 'var(--accent-orange)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 'bold' }}>
                  {sentiment.neutral > 10 ? `${sentiment.neutral}%` : ''}
                </div>
                <div style={{ width: `${sentiment.bearish}%`, height: '100%', backgroundColor: 'var(--status-red)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 'bold' }}>
                  {sentiment.bearish > 10 ? `${sentiment.bearish}%` : ''}
                </div>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', padding: '0 1rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <div style={{ width: '12px', height: '12px', borderRadius: '50%', backgroundColor: 'var(--status-green)' }}></div>
                  <span>Bullish</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <div style={{ width: '12px', height: '12px', borderRadius: '50%', backgroundColor: 'var(--accent-orange)' }}></div>
                  <span>Neutral</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <div style={{ width: '12px', height: '12px', borderRadius: '50%', backgroundColor: 'var(--status-red)' }}></div>
                  <span>Bearish</span>
                </div>
              </div>
            </div>
          )}

          <div style={{ display: 'flex', gap: '2rem', flexWrap: 'wrap' }}>
            {Object.entries(data.indices).map(([name, info]) => {
              
              // RSI Class
              let rsiColor = 'white';
              let rsiText = 'Neutral';
              if (info.rsi > 70) { rsiColor = 'var(--status-red)'; rsiText = 'Bearish'; }
              else if (info.rsi < 30) { rsiColor = 'var(--status-green)'; rsiText = 'Bullish'; }
              else { rsiColor = 'var(--accent-orange)'; rsiText = 'Neutral'; }

              // Trend
              let trendColor = 'var(--accent-orange)';
              let trendText = 'Sideways';
              if (info.price > info.sma_50 && info.price > info.sma_200) { trendColor = 'var(--status-green)'; trendText = 'Uptrend'; }
              else if (info.price < info.sma_50 && info.price < info.sma_200) { trendColor = 'var(--status-red)'; trendText = 'Downtrend'; }

              // YTD class
              let ytdColor = 'var(--status-green)';
              let ytdText = 'Bull Market';
              if (info.ytd <= 0 && info.ytd > -20) { ytdColor = 'var(--accent-orange)'; ytdText = 'Correction'; }
              else if (info.ytd <= -20 && info.ytd > -30) { ytdColor = 'var(--status-red)'; ytdText = 'Bear Market'; }
              else if (info.ytd <= -30) { ytdColor = '#8b0000'; ytdText = 'Crash'; }

              // 52W Class
              const rangePos = (info.price - info.low_52w) / (info.high_52w - info.low_52w);
              let rangeColor = 'var(--accent-orange)';
              let rangeText = 'Mid Range';
              if (rangePos > 0.85) { rangeColor = 'var(--status-green)'; rangeText = 'Near 52-Week High'; }
              else if (rangePos < 0.15) { rangeColor = 'var(--status-red)'; rangeText = 'Near 52-Week Low'; }

              return (
                <div key={name} className="glass-panel" style={{ flex: '1 1 400px' }}>
                  <h3 style={{ fontSize: '1.8rem', marginBottom: '1rem' }}>{name}</h3>
                  <div style={{ fontSize: '1.2rem', marginBottom: '1rem' }}>
                    <strong>Current Price:</strong> ${info.price.toLocaleString(undefined, {minimumFractionDigits: 2})}
                    <span style={{ color: rangeColor, marginLeft: '1rem' }}>({rangeText})</span>
                  </div>
                  <div style={{ marginBottom: '1.5rem', display: 'flex', justifyContent: 'space-between' }}>
                    <span><strong>52W High:</strong> ${info.high_52w.toFixed(2)}</span>
                    <span><strong>52W Low:</strong> ${info.low_52w.toFixed(2)}</span>
                  </div>

                  <hr style={{ borderColor: 'rgba(255,255,255,0.1)', marginBottom: '1.5rem' }} />

                  <h4 style={{ color: 'var(--accent-cyan)', marginBottom: '1rem' }}>Returns & Momentum</h4>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '1rem', marginBottom: '1.5rem' }}>
                    <div><div className="metric-label">1D</div><div style={{ color: getColor(info.p1d), fontWeight: 'bold' }}>{formatPct(info.p1d)}</div></div>
                    <div><div className="metric-label">5D</div><div style={{ color: getColor(info.p5d), fontWeight: 'bold' }}>{formatPct(info.p5d)}</div></div>
                    <div><div className="metric-label">1M</div><div style={{ color: getColor(info.p1m), fontWeight: 'bold' }}>{formatPct(info.p1m)}</div></div>
                    <div><div className="metric-label">6M</div><div style={{ color: getColor(info.p6m), fontWeight: 'bold' }}>{formatPct(info.p6m)}</div></div>
                    <div><div className="metric-label">1Y</div><div style={{ color: getColor(info.p1y), fontWeight: 'bold' }}>{formatPct(info.p1y)}</div></div>
                    <div><div className="metric-label">5Y</div><div style={{ color: getColor(info.p5y), fontWeight: 'bold' }}>{formatPct(info.p5y)}</div></div>
                  </div>

                  <hr style={{ borderColor: 'rgba(255,255,255,0.1)', marginBottom: '1.5rem' }} />

                  <h4 style={{ color: 'var(--accent-cyan)', marginBottom: '1rem' }}>Technical Indicators</h4>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1.5rem' }}>
                    <div>
                      <div className="metric-label">RSI (14)</div>
                      <div style={{ fontSize: '1.2rem' }}>
                        {info.rsi?.toFixed(2)} <span style={{ color: rsiColor, fontWeight: 'bold' }}>({rsiText})</span>
                      </div>
                    </div>
                    <div>
                      <div className="metric-label">MACD Signal</div>
                      <div style={{ fontSize: '1.2rem', color: info.macd_signal === 'Bullish' ? 'var(--status-green)' : 'var(--status-red)', fontWeight: 'bold' }}>
                        {info.macd_signal}
                      </div>
                    </div>
                    <div>
                      <div className="metric-label">YTD Market State</div>
                      <div style={{ fontSize: '1.2rem' }}>
                        {formatPct(info.ytd)} <span style={{ color: ytdColor, fontWeight: 'bold' }}>({ytdText})</span>
                      </div>
                    </div>
                    <div>
                      <div className="metric-label">Trend (SMA50/200)</div>
                      <div style={{ fontSize: '1.2rem', color: trendColor, fontWeight: 'bold' }}>
                        {trendText}
                      </div>
                    </div>
                  </div>

                  <hr style={{ borderColor: 'rgba(255,255,255,0.1)', marginBottom: '1.5rem' }} />

                  <h4 style={{ color: 'var(--accent-cyan)', marginBottom: '1rem' }}>Fibonacci Context</h4>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span className="metric-label">3Y Position</span>
                      <span>{info.fib_3y?.toFixed(2)}% ({info.fib_3y > 61.8 ? 'Breakout' : info.fib_3y < 38.2 ? 'Support' : 'Consolidating'})</span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span className="metric-label">5Y Position</span>
                      <span>{info.fib_5y?.toFixed(2)}%</span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span className="metric-label">10Y Position</span>
                      <span>{info.fib_10y?.toFixed(2)}%</span>
                    </div>
                  </div>

                </div>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
