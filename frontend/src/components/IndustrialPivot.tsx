import React, { useState, useMemo } from 'react';
import { ChevronRight, ChevronDown, Filter, Search, Download, Settings2, Columns } from 'lucide-react';
import { fmtFull, fmtPct } from '../utils/formatters';

interface Column {
  key: string;
  label: string;
  align?: 'left' | 'right' | 'center';
  format?: (v: any, row: any) => React.ReactNode;
  width?: string | number;
}

interface PivotProps {
  data: any[];
  columns: Column[];
  rowKey?: string;
  indentKey?: string;
  onRowClick?: (row: any) => void;
  title?: string;
  searchable?: boolean;
}

export default function IndustrialPivot({ 
  data, 
  columns, 
  rowKey = 'c', 
  indentKey = 'lvl', 
  onRowClick,
  title,
  searchable = true
}: PivotProps) {
  const [searchTerm, setSearchTerm] = useState('');
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());

  // Simple hierarchy detection: if next row has larger level, this row is a parent
  const isParent = (index: number) => {
    if (index >= data.length - 1) return false;
    return (data[index + 1][indentKey] || 0) > (data[index][indentKey] || 0);
  };

  const toggleCollapse = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setCollapsed(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const filteredData = useMemo(() => {
    if (!searchTerm) return data;
    const term = searchTerm.toLowerCase();
    return data.filter(row => 
      Object.values(row).some(val => 
        String(val).toLowerCase().includes(term)
      )
    );
  }, [data, searchTerm]);

  // Determine visibility based on collapsed state
  const visibleRows = useMemo(() => {
    if (searchTerm) return filteredData;
    
    const visible: any[] = [];
    const skipUntilLevel: number | null = null;
    let currentSkipLevel: number | null = null;
    
    for (let i = 0; i < data.length; i++) {
        const row = data[i];
        const level = row[indentKey] || 0;
        const id = row[rowKey];

        if (currentSkipLevel !== null && level > currentSkipLevel) {
            continue;
        } else {
            currentSkipLevel = null;
        }

        visible.push(row);
        if (collapsed.has(id)) {
            currentSkipLevel = level;
        }
    }
    return visible;
  }, [data, collapsed, searchTerm, filteredData]);

  return (
    <div className="command-panel flex flex-col overflow-hidden border-b1">
      {/* Pivot Toolbar */}
      <div className="flex items-center justify-between p-3 border-b border-b1 bg-bg2/50">
        <div className="flex items-center gap-3">
          {title && <span className="text-[10px] font-bold text-sky tracking-widest uppercase">{title}</span>}
          {searchable && (
            <div className="relative">
              <Search size={12} className="absolute left-2 top-1/2 -translate-y-1/2 text-dim" />
              <input 
                type="text" 
                placeholder="Search matrix..." 
                className="bg-bg1 border border-b2 rounded pl-8 pr-2 py-1 text-[10px] w-48 focus:border-sky outline-none transition-colors"
                value={searchTerm}
                onChange={e => setSearchTerm(e.target.value)}
              />
            </div>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button className="btn-minimal gap-1"><Filter size={10} /> Filter</button>
          <button className="btn-minimal gap-1"><Columns size={10} /> Pivots</button>
          <button className="btn-minimal gap-1"><Settings2 size={10} /></button>
          <button className="btn-minimal gap-1 border-emerald/50 text-emerald"><Download size={10} /> CSV</button>
        </div>
      </div>

      {/* Grid Container */}
      <div className="flex-1 overflow-auto bg-black/40">
        <table className="data-grid-premium w-full text-left border-collapse">
          <thead className="sticky top-0 z-20 bg-bg1 border-b border-b1 shadow-sm">
            <tr>
              {columns.map(col => (
                <th key={col.key} className={col.align === 'right' ? 'text-right' : col.align === 'center' ? 'text-center' : ''} style={{ width: col.width }}>
                  {col.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {visibleRows.map((row, idx) => {
              const id = row[rowKey];
              const level = row[indentKey] || 0;
              const parent = isParent(data.indexOf(row));
              const isOpen = !collapsed.has(id);

              return (
                <tr 
                  key={id || idx} 
                  className={`group hover:bg-white/5 transition-colors cursor-pointer ${row.bold ? 'font-bold bg-white/[0.02]' : ''}`}
                  onClick={() => onRowClick?.(row)}
                >
                  {columns.map(col => (
                    <td key={col.key} className={col.align === 'right' ? 'text-right font-mono' : col.align === 'center' ? 'text-center' : ''}>
                      {col.key === columns[0].key ? (
                        <div className="flex items-center gap-1" style={{ paddingLeft: level * 16 }}>
                          {parent ? (
                            <button 
                                onClick={(e) => toggleCollapse(id, e)}
                                className="p-1 hover:bg-sky/20 rounded transition-colors text-sky"
                            >
                                {isOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                            </button>
                          ) : (
                            <div className="w-6" />
                          )}
                          <span className={row.bold ? 'text-sky' : 'text-text'}>
                            {col.format ? col.format(row[col.key], row) : row[col.key]}
                          </span>
                        </div>
                      ) : (
                        <span className={row.bold ? 'text-heading' : 'text-muted'}>
                           {col.format ? col.format(row[col.key], row) : row[col.key]}
                        </span>
                      )}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
        
        {visibleRows.length === 0 && (
           <div className="py-20 text-center text-dim text-xs font-mono uppercase tracking-widest">
              No matching records in matrix
           </div>
        )}
      </div>
      
      {/* Grid Footer / Summary Bar */}
      <div className="p-2 border-t border-b1 bg-bg1 flex justify-between items-center px-4">
          <div className="text-[9px] text-dim font-mono">
             TOTAL_ROWS: {data.length} | FILTERED: {visibleRows.length} | DEPTH: {Math.max(...data.map(d => d[indentKey] || 0))}
          </div>
          <div className="flex gap-4 text-[9px] font-mono text-muted">
             <span>SUM(AC): <span className="text-sky font-bold">{fmtFull(data.reduce((acc, r) => acc + (r.lvl === 0 ? r.ac : 0), 0))}</span></span>
          </div>
      </div>
    </div>
  );
}
