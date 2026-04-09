/**
 * FinAI Utility: Standardized Industrial Formatters (v2026)
 * Enforces consistency across all dashboard, logic, and analytics components.
 */

export function fmtCompact(n: number | undefined | null): string {
  if (n == null || isNaN(n)) return '\u2014';
  const abs = Math.abs(n);
  const sign = n < 0 ? '-' : '';
  
  if (abs >= 1e9) return `${sign}\u20BE${(abs / 1e9).toFixed(1)}B`;
  if (abs >= 1e6) return `${sign}\u20BE${(abs / 1e6).toFixed(1)}M`;
  if (abs >= 1e3) return `${sign}\u20BE${(abs / 1e3).toFixed(1)}K`;
  return `${sign}\u20BE${abs.toLocaleString('en-US', { maximumFractionDigits: 0 })}`;
}

export function fmtFull(n: number | undefined | null): string {
  if (n == null || isNaN(n) || n === 0) return '\u2014';
  const sign = n < 0 ? '-' : '';
  const abs = Math.abs(n);
  return `${sign}\u10BE${abs.toLocaleString('en-US', { maximumFractionDigits: 0 })}`;
}

export function fmtPct(n: number | undefined | null, decimals = 1): string {
  if (n == null || isNaN(n)) return '\u2014';
  return `${n > 0 ? '+' : ''}${n.toFixed(decimals)}%`;
}

export function fmtCurrency(n: number | undefined | null): string {
  if (n == null || isNaN(n)) return '\u2014';
  return new Intl.NumberFormat('en-GE', {
    style: 'currency',
    currency: 'GEL',
    maximumFractionDigits: 0,
  }).format(n).replace('GEL', '\u10BE');
}
