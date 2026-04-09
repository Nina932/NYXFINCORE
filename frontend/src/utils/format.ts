export function formatCurrency(value: number, currency = 'GEL'): string {
  const symbol = currency === 'GEL' ? '\u20BE' : '$';
  const abs = Math.abs(value);
  let formatted: string;
  if (abs >= 1_000_000_000) {
    formatted = `${(abs / 1_000_000_000).toFixed(1)}B`;
  } else if (abs >= 1_000_000) {
    formatted = `${(abs / 1_000_000).toFixed(1)}M`;
  } else if (abs >= 1_000) {
    formatted = `${(abs / 1_000).toFixed(0)}K`;
  } else {
    formatted = abs.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 });
  }
  return value < 0 ? `-${symbol}${formatted}` : `${symbol}${formatted}`;
}

export function formatCurrencyFull(value: number, currency = 'GEL'): string {
  const symbol = currency === 'GEL' ? '\u20BE' : '$';
  const formatted = Math.abs(value).toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 });
  return value < 0 ? `-${symbol}${formatted}` : `${symbol}${formatted}`;
}

export function formatPercent(value: number): string {
  return `${value.toFixed(1)}%`;
}

export function formatNumber(value: number): string {
  return value.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 });
}

export function formatChange(value: number): string {
  const sign = value >= 0 ? '+' : '';
  return `${sign}${value.toFixed(1)}%`;
}

export function formatCompact(value: number): string {
  const abs = Math.abs(value);
  if (abs >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (abs >= 1_000) return `${(value / 1_000).toFixed(0)}K`;
  return value.toFixed(0);
}

/** CSS class for JetBrains Mono numbers */
export const monoClass = 'font-mono';
