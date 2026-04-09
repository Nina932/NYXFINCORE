import { X, Plus, Filter } from 'lucide-react';

/* ─── Types ─── */
interface FilterPill {
  key: string;
  label: string;
  value: string;
  operator?: string;
  color?: string;
}

interface FilterPillsWidgetProps {
  filters: FilterPill[];
  onRemove: (key: string) => void;
  onClearAll: () => void;
  onAdd?: () => void;
  mode?: 'read-only' | 'remove-only' | 'add-update-remove';
}

/* ─── Default pill colors ─── */
const DEFAULT_COLORS = [
  'var(--sky)', 'var(--violet)', 'var(--emerald)',
  'var(--amber)', 'var(--rose)', 'var(--teal)',
];

function getPillColor(pill: FilterPill, idx: number): string {
  return pill.color || DEFAULT_COLORS[idx % DEFAULT_COLORS.length];
}

/* ─── Component ─── */
export default function FilterPillsWidget({
  filters, onRemove, onClearAll, onAdd, mode = 'remove-only',
}: FilterPillsWidgetProps) {
  if (filters.length === 0 && mode !== 'add-update-remove') return null;

  const canRemove = mode === 'remove-only' || mode === 'add-update-remove';
  const canAdd = mode === 'add-update-remove' && onAdd;

  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 8,
      flexWrap: 'wrap', padding: '8px 0',
    }}>
      {/* Filter icon */}
      {filters.length > 0 && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: 4,
          fontSize: 10, color: 'var(--muted)', fontWeight: 600,
          textTransform: 'uppercase', letterSpacing: '0.5px',
          marginRight: 4,
        }}>
          <Filter size={12} />
          <span>Filters</span>
        </div>
      )}

      {/* Pills */}
      {filters.map((pill, idx) => {
        const color = getPillColor(pill, idx);
        return (
          <div
            key={pill.key}
            style={{
              display: 'inline-flex', alignItems: 'center', gap: 6,
              padding: '4px 10px', borderRadius: 20,
              background: `color-mix(in srgb, ${color} 10%, transparent)`,
              border: `1px solid color-mix(in srgb, ${color} 25%, transparent)`,
              fontSize: 11, fontFamily: 'var(--mono)',
              animation: `fade-in .3s ease ${idx * 0.05}s both`,
              transition: 'all .2s ease',
            }}
          >
            {/* Label */}
            <span style={{ color: 'var(--muted)', fontWeight: 500 }}>
              {pill.label}
            </span>

            {/* Operator */}
            {pill.operator && (
              <span style={{ color, fontWeight: 600, fontSize: 10 }}>
                {pill.operator}
              </span>
            )}

            {/* Value */}
            <span style={{ color, fontWeight: 700 }}>
              {pill.value}
            </span>

            {/* Remove button */}
            {canRemove && (
              <button
                onClick={(e) => { e.stopPropagation(); onRemove(pill.key); }}
                style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  width: 16, height: 16, borderRadius: '50%',
                  background: `color-mix(in srgb, ${color} 15%, transparent)`,
                  border: 'none', cursor: 'pointer',
                  color, padding: 0,
                  transition: 'background .2s',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = `color-mix(in srgb, ${color} 30%, transparent)`;
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = `color-mix(in srgb, ${color} 15%, transparent)`;
                }}
              >
                <X size={10} />
              </button>
            )}
          </div>
        );
      })}

      {/* Add filter button */}
      {canAdd && (
        <button
          onClick={onAdd}
          style={{
            display: 'inline-flex', alignItems: 'center', gap: 4,
            padding: '4px 10px', borderRadius: 20,
            background: 'transparent',
            border: '1px dashed var(--b2)',
            fontSize: 11, color: 'var(--muted)',
            cursor: 'pointer', transition: 'all .2s',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.borderColor = 'var(--sky)';
            e.currentTarget.style.color = 'var(--sky)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.borderColor = 'var(--b2)';
            e.currentTarget.style.color = 'var(--muted)';
          }}
        >
          <Plus size={12} /> Add filter
        </button>
      )}

      {/* Clear all */}
      {canRemove && filters.length > 1 && (
        <button
          onClick={onClearAll}
          style={{
            fontSize: 10, color: 'var(--dim)',
            background: 'transparent', border: 'none',
            cursor: 'pointer', padding: '4px 8px',
            borderRadius: 4, transition: 'color .2s',
            marginLeft: 4,
          }}
          onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--rose)'; }}
          onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--dim)'; }}
        >
          Clear all
        </button>
      )}
    </div>
  );
}
