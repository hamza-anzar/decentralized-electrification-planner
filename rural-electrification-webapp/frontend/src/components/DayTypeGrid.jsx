import { useMemo } from "react";
import { CATEGORY_COLORS } from "../lib/charts";

// Pivots the flat day-type-profile rows (day_type, hour_of_day, category, item, qty_active) into a
// 24-hour x N-item grid for one selected day type — far more usable than a raw 432-row table, and
// the direct replacement for the old Streamlit page's read-only st.dataframe of all 8,208 rows.
export default function DayTypeGrid({ rows, dayType, onChange }) {
  const columns = useMemo(() => {
    const seen = new Set();
    const cols = [];
    for (const r of rows) {
      if (r.day_type !== dayType) continue;
      const key = `${r.category}|${r.item}`;
      if (!seen.has(key)) {
        seen.add(key);
        cols.push({ category: r.category, item: r.item, key });
      }
    }
    return cols;
  }, [rows, dayType]);

  const lookup = useMemo(() => {
    const map = new Map();
    rows.forEach((r, idx) => {
      if (r.day_type === dayType) map.set(`${r.hour_of_day}|${r.category}|${r.item}`, idx);
    });
    return map;
  }, [rows, dayType]);

  function updateCell(hour, col, value) {
    const idx = lookup.get(`${hour}|${col.category}|${col.item}`);
    if (idx === undefined) return;
    const next = rows.slice();
    next[idx] = { ...next[idx], qty_active: value };
    onChange(next);
  }

  return (
    <div className="overflow-auto rounded-xl border border-ink-100" style={{ maxHeight: 480 }}>
      <table className="w-full min-w-[900px] border-collapse text-xs">
        <thead className="sticky top-0 z-10 bg-ink-50">
          <tr>
            <th className="sticky left-0 z-20 whitespace-nowrap border-b border-r border-ink-100 bg-ink-50 px-2 py-2 text-left font-semibold uppercase tracking-wide text-ink-500">
              Hour
            </th>
            {columns.map((c) => (
              <th key={c.key} className="whitespace-nowrap border-b border-ink-100 px-2 py-2 text-center font-semibold text-ink-500">
                <span className="mr-1 inline-block h-1.5 w-1.5 rounded-full align-middle" style={{ background: CATEGORY_COLORS[c.category] || "#c9c8bd" }} />
                {c.category} · {c.item}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {Array.from({ length: 24 }, (_, h) => h).map((h) => (
            <tr key={h} className="odd:bg-white even:bg-ink-50/30">
              <td className="sticky left-0 z-10 border-b border-r border-ink-50 bg-inherit px-2 py-1 font-semibold tabular-nums text-ink-600">{h}:00</td>
              {columns.map((c) => {
                const idx = lookup.get(`${h}|${c.category}|${c.item}`);
                const value = idx !== undefined ? rows[idx].qty_active : 0;
                return (
                  <td key={c.key} className="border-b border-ink-50 px-1 py-0.5 text-center">
                    <input
                      type="number"
                      step="0.05"
                      value={value}
                      onChange={(e) => updateCell(h, c, e.target.value === "" ? 0 : Number(e.target.value))}
                      className="w-14 rounded-md border border-transparent bg-transparent px-1 py-1 text-center tabular-nums transition focus:border-brand-300 focus:bg-white focus:outline-none focus:ring-2 focus:ring-brand-100"
                    />
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
