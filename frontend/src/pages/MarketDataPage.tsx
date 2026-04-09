import { useState, useEffect } from 'react';
import { api } from '../api/client';
import { Globe, RefreshCw, TrendingUp, TrendingDown, Fuel, DollarSign, BarChart3, Building2, Loader2 } from 'lucide-react';

function RateCard({ label, value, change, icon: Icon, color, suffix = '' }: {
  label: string; value: string; change?: number; icon: React.ElementType; color: string; suffix?: string;
}) {
  return (
    <div className="glass" style={{ padding: 16, position: 'relative', overflow: 'hidden' }}>
      <div style={{ position: 'absolute', top: -15, right: -15, width: 50, height: 50, background: color, borderRadius: '50%', opacity: 0.06, filter: 'blur(15px)' }} />
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
        <span style={{ fontFamily: 'var(--mono)', fontSize: 9, textTransform: 'uppercase', letterSpacing: 1.5, color: 'var(--muted)' }}>{label}</span>
        <div style={{ padding: 4, borderRadius: 5, background: `color-mix(in srgb, ${color} 10%, transparent)` }}>
          <Icon size={13} style={{ color }} />
        </div>
      </div>
      <div style={{ fontSize: 20, fontWeight: 800, fontFamily: 'var(--mono)', color: 'var(--heading)' }}>
        {value}{suffix}
      </div>
      {change !== undefined && change !== 0 && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 3, marginTop: 4, fontSize: 10, fontFamily: 'var(--mono)', color: change > 0 ? 'var(--emerald)' : 'var(--rose)' }}>
          {change > 0 ? <TrendingUp size={10} /> : <TrendingDown size={10} />}
          {change > 0 ? '+' : ''}{typeof change === 'number' ? change.toFixed(4) : change}
        </div>
      )}
    </div>
  );
}

function MacroRow({ label, value, year }: { label: string; value: number | null; year: string }) {
  if (value === null || value === undefined) return null;
  return (
    <tr style={{ borderBottom: '1px solid var(--b1)' }}>
      <td style={{ padding: '8px 14px', fontSize: 12, color: 'var(--text)' }}>{label}</td>
      <td style={{ padding: '8px 14px', textAlign: 'right', fontFamily: 'var(--mono)', fontSize: 12, fontWeight: 600, color: 'var(--heading)' }}>
        {typeof value === 'number' ? (Math.abs(value) > 1000 ? `$${(value / 1e9).toFixed(1)}B` : `${value.toFixed(1)}%`) : value}
      </td>
      <td style={{ padding: '8px 14px', textAlign: 'right', fontSize: 10, color: 'var(--dim)' }}>{year}</td>
    </tr>
  );
}

/* ─── Georgia Fuel Prices (placeholder until live feed) ─── */
const FUEL_PRICES_GEL = [
  { fuel: 'Premium Petrol (Super)', price: '3.29', unit: '₾/L', change: +0.02, color: 'var(--rose)' },
  { fuel: 'Regular Petrol (Euro)', price: '3.09', unit: '₾/L', change: -0.01, color: 'var(--amber)' },
  { fuel: 'Diesel (Euro 5)', price: '3.19', unit: '₾/L', change: +0.03, color: 'var(--sky)' },
  { fuel: 'CNG', price: '1.49', unit: '₾/m³', change: 0, color: 'var(--emerald)' },
  { fuel: 'LPG (Auto Gas)', price: '1.69', unit: '₾/L', change: -0.02, color: 'var(--violet)' },
];

export default function MarketDataPage() {
  const [data, setData] = useState<Record<string, any> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const fetchData = async () => {
    setLoading(true); setError('');
    try {
      const json = await api.marketData() as Record<string, any>;
      setData(json);
    } catch (e) { setError(e instanceof Error ? e.message : 'Failed to fetch market data'); }
    finally { setLoading(false); }
  };

  useEffect(() => { fetchData(); }, []);

  const nbg = data?.nbg_rates?.rates || {};
  const oil = data?.oil_prices || {};
  const macro = data?.georgia_macro?.indicators || {};

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 800, color: 'var(--heading)', display: 'flex', alignItems: 'center', gap: 8 }}>
            <Globe size={20} style={{ color: 'var(--sky)' }} /> Market Data — Georgia
          </h1>
          <p style={{ fontSize: 12, color: 'var(--muted)', marginTop: 3 }}>
            Fuel prices, NBG exchange rates, commodities, and macro indicators
          </p>
        </div>
        <button onClick={fetchData} disabled={loading} className="btn btn-ghost">
          {loading ? <Loader2 size={13} style={{ animation: 'spin 1s linear infinite' }} /> : <RefreshCw size={13} />}
          {loading ? 'Loading...' : 'Refresh'}
        </button>
      </div>

      {error && (
        <div className="glass" style={{ padding: 12, borderColor: 'var(--rose)', color: 'var(--rose)', fontSize: 12 }}>
          {error}
        </div>
      )}

      {/* Section 1: Fuel Prices Georgia */}
      <div>
        <h2 style={{ fontSize: 14, fontWeight: 700, color: 'var(--heading)', marginBottom: 12, display: 'flex', alignItems: 'center', gap: 6 }}>
          <Fuel size={16} style={{ color: 'var(--rose)' }} /> Fuel Prices Georgia
          <span style={{ fontSize: 10, color: 'var(--dim)', fontWeight: 400, marginLeft: 8 }}>NYX Core Thinker / Wissol / Gulf indicative</span>
        </h2>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 12 }}>
          {FUEL_PRICES_GEL.map(f => (
            <RateCard key={f.fuel} label={f.fuel} value={`₾${f.price}`} change={f.change || undefined} icon={Fuel} color={f.color} suffix={` ${f.unit.split('/')[1] ? '/' + f.unit.split('/')[1] : ''}`} />
          ))}
        </div>
        <p style={{ fontSize: 10, color: 'var(--dim)', marginTop: 6, fontStyle: 'italic' }}>
          Indicative retail prices. Actual prices may vary by station and region.
        </p>
      </div>

      {/* Section 2: NBG Exchange Rates */}
      <div>
        <h2 style={{ fontSize: 14, fontWeight: 700, color: 'var(--heading)', marginBottom: 12, display: 'flex', alignItems: 'center', gap: 6 }}>
          <DollarSign size={16} style={{ color: 'var(--emerald)' }} /> NBG Exchange Rates (GEL)
          {data?.nbg_rates?.date && <span style={{ fontSize: 10, color: 'var(--dim)', fontWeight: 400, marginLeft: 8 }}>{data.nbg_rates.date}</span>}
        </h2>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 12 }}>
          {nbg.USD && <RateCard label="USD/GEL" value={nbg.USD.rate?.toFixed(4)} change={nbg.USD.change} icon={DollarSign} color="var(--emerald)" />}
          {nbg.EUR && <RateCard label="EUR/GEL" value={nbg.EUR.rate?.toFixed(4)} change={nbg.EUR.change} icon={DollarSign} color="var(--blue)" />}
          {nbg.GBP && <RateCard label="GBP/GEL" value={nbg.GBP.rate?.toFixed(4)} change={nbg.GBP.change} icon={DollarSign} color="var(--violet)" />}
          {nbg.TRY && <RateCard label="TRY/GEL" value={nbg.TRY.rate?.toFixed(4)} change={nbg.TRY.change} icon={DollarSign} color="var(--amber)" />}
          {nbg.RUB && <RateCard label="RUB/GEL" value={nbg.RUB.rate?.toFixed(6)} change={nbg.RUB.change} icon={DollarSign} color="var(--rose)" />}
          {nbg.AZN && <RateCard label="AZN/GEL" value={nbg.AZN.rate?.toFixed(4)} change={nbg.AZN.change} icon={DollarSign} color="var(--sky)" />}
        </div>
        {!data && !loading && !error && (
          <div className="glass" style={{ padding: 16, textAlign: 'center', marginTop: 8 }}>
            <p style={{ color: 'var(--muted)', fontSize: 12 }}>Exchange rates will appear once the backend responds.</p>
          </div>
        )}
      </div>

      {/* Section 3: Brent Crude & Commodities */}
      <div>
        <h2 style={{ fontSize: 14, fontWeight: 700, color: 'var(--heading)', marginBottom: 12, display: 'flex', alignItems: 'center', gap: 6 }}>
          <BarChart3 size={16} style={{ color: 'var(--amber)' }} /> Brent Crude & Commodities
        </h2>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 12 }}>
          <RateCard label="Brent Crude" value={oil.brent_crude_usd ? `$${oil.brent_crude_usd}` : '$--'} icon={Fuel} color="var(--amber)" suffix="/bbl" />
          <RateCard label="WTI Crude" value={oil.wti_crude_usd ? `$${oil.wti_crude_usd}` : '$--'} icon={Fuel} color="var(--rose)" suffix="/bbl" />
          <RateCard label="Natural Gas" value={oil.natural_gas_usd_mmbtu ? `$${oil.natural_gas_usd_mmbtu}` : '$--'} icon={Fuel} color="var(--sky)" suffix="/MMBtu" />
          {oil.brent_crude_gel && <RateCard label="Brent in GEL" value={`₾${oil.brent_crude_gel}`} icon={Fuel} color="var(--violet)" suffix="/bbl" />}
        </div>
        {oil.note && <p style={{ fontSize: 10, color: 'var(--dim)', marginTop: 6, fontStyle: 'italic' }}>{oil.note}</p>}
      </div>

      {/* Section 4: Georgia Macro */}
      <div>
        <h2 style={{ fontSize: 14, fontWeight: 700, color: 'var(--heading)', marginBottom: 12, display: 'flex', alignItems: 'center', gap: 6 }}>
          <Building2 size={16} style={{ color: 'var(--violet)' }} /> Georgia Macro Indicators
        </h2>
        <div className="glass" style={{ overflow: 'hidden' }}>
          <table style={{ width: '100%', fontSize: 12, borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--b2)' }}>
                {['Indicator', 'Value', 'Year'].map(h => (
                  <th key={h} style={{ textAlign: h === 'Indicator' ? 'left' : 'right', padding: '8px 14px', fontFamily: 'var(--mono)', fontSize: 9, textTransform: 'uppercase', letterSpacing: 1.5, color: 'var(--muted)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {macro.gdp_current_usd?.value !== undefined && (
                <MacroRow label="GDP (Current USD)" value={macro.gdp_current_usd.value} year={macro.gdp_current_usd.year ?? ''} />
              )}
              {macro.gdp_growth_pct?.value !== undefined && (
                <MacroRow label="GDP Growth" value={macro.gdp_growth_pct.value} year={macro.gdp_growth_pct.year ?? ''} />
              )}
              {macro.inflation_pct?.value !== undefined && (
                <MacroRow label="Inflation (CPI)" value={macro.inflation_pct.value} year={macro.inflation_pct.year ?? ''} />
              )}
              {macro.unemployment_pct?.value !== undefined && (
                <MacroRow label="Unemployment" value={macro.unemployment_pct.value} year={macro.unemployment_pct.year ?? ''} />
              )}
              {macro.exports_pct_gdp?.value !== undefined && (
                <MacroRow label="Exports (% of GDP)" value={macro.exports_pct_gdp.value} year={macro.exports_pct_gdp.year ?? ''} />
              )}
              {macro.population?.value && (
                <tr style={{ borderBottom: '1px solid var(--b1)' }}>
                  <td style={{ padding: '8px 14px', fontSize: 12, color: 'var(--text)' }}>Population</td>
                  <td style={{ padding: '8px 14px', textAlign: 'right', fontFamily: 'var(--mono)', fontSize: 12, fontWeight: 600, color: 'var(--heading)' }}>
                    {(macro.population.value / 1e6).toFixed(2)}M
                  </td>
                  <td style={{ padding: '8px 14px', textAlign: 'right', fontSize: 10, color: 'var(--dim)' }}>{macro.population.year}</td>
                </tr>
              )}
              {/* Fallback if no API data yet */}
              {!data && !loading && (
                <tr>
                  <td colSpan={3} style={{ padding: 16, textAlign: 'center', color: 'var(--muted)', fontSize: 12 }}>
                    Macro data will load from the backend.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Data source footer */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '4px 0' }}>
        <p style={{ fontSize: 10, color: 'var(--dim)' }}>
          Data source: NBG, World Bank, Platts
        </p>
        {data?.timestamp && (
          <p style={{ fontSize: 10, color: 'var(--dim)' }}>
            Last updated: {new Date(data.timestamp).toLocaleString()}
          </p>
        )}
      </div>
    </div>
  );
}
