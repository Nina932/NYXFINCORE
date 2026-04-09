/**
 * Client-side Excel export via backend API.
 * Sends data to /api/agent/agents/export/excel and triggers download.
 */

const safeName = (name: string) =>
  name.replace(/[^\x20-\x7E]/g, '').replace(/\s+/g, '_').replace(/_+/g, '_').trim() || 'FinAI';

export async function downloadExcel(
  data: Record<string, unknown>,
  filename?: string,
): Promise<void> {
  try {
    const token = localStorage.getItem('token') || '';
    const res = await fetch('/api/agent/agents/export/excel', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token && { Authorization: `Bearer ${token}` }),
      },
      body: JSON.stringify(data),
    });

    const contentType = res.headers.get('content-type') || '';
    if (contentType.includes('json')) {
      const err = await res.json();
      throw new Error(err.error || 'Excel generation failed');
    }

    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename || `${safeName(String(data.company || 'FinAI'))}_report.xlsx`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  } catch (e) {
    console.error('Excel export failed:', e);
    throw e;
  }
}

/**
 * Simple client-side Excel-like export (CSV with .xlsx hint for Excel to open).
 * For when backend export isn't needed — just a quick data dump.
 */
export function downloadQuickExcel(
  rows: Record<string, unknown>[],
  filename: string,
  sheetTitle?: string,
): void {
  if (!rows.length) return;

  const headers = Object.keys(rows[0]);
  const csvRows = [
    ...(sheetTitle ? [sheetTitle, ''] : []),
    headers.join('\t'),
    ...rows.map(row =>
      headers.map(h => {
        const val = row[h];
        return val === null || val === undefined ? '' : String(val);
      }).join('\t')
    ),
  ];

  const blob = new Blob(['\uFEFF' + csvRows.join('\n')], { type: 'application/vnd.ms-excel;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename.endsWith('.xlsx') ? filename : `${filename}.xlsx`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
