import clsx from "clsx";
import { Trash2, Plus } from "lucide-react";

// A styled, editable data table — the custom replacement for st.data_editor / st.dataframe.
// columns: [{ key, label, type: "text"|"number"|"select"|"readonly", width, step, options, disabled, format }]
// `disabled` may be a plain boolean (every row) or a `(row) => boolean` predicate (per-row) — used e.g.
// so a BOQ's system-scaled rows (Solar Panels, Battery System, ...) grey out qty/unit-cost while every
// other row greys out system-unit/lumpsum instead.
// Pass onAddRow/newRow to show a trailing "Add row" button; pass onRemoveRow to show a delete icon per row.
export default function EditableTable({ columns, rows, onChange, dense = false, onRemoveRow, onAddRow, addLabel = "Add row" }) {
  function updateCell(rowIdx, key, value) {
    const next = rows.map((r, i) => (i === rowIdx ? { ...r, [key]: value } : r));
    onChange(next);
  }

  function isDisabled(col, row) {
    return typeof col.disabled === "function" ? col.disabled(row) : !!col.disabled;
  }

  return (
    <div className="rounded-xl border border-ink-100">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[560px] border-collapse text-sm">
          <thead>
            <tr className="bg-ink-50/80">
              {columns.map((col) => (
                <th
                  key={col.key}
                  className="whitespace-nowrap border-b border-ink-100 px-3 py-2.5 text-left text-xs font-semibold uppercase tracking-wide text-ink-500"
                  style={{ width: col.width }}
                >
                  {col.label}
                </th>
              ))}
              {onRemoveRow && <th className="w-10 border-b border-ink-100" />}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr key={row.__key ?? i} className={clsx("group transition-colors hover:bg-brand-50/40", i % 2 === 1 && "bg-ink-50/30")}>
                {columns.map((col) => (
                  <td key={col.key} className={clsx("border-b border-ink-50 px-3", dense ? "py-1.5" : "py-2")}>
                    {col.type === "readonly" || isDisabled(col, row) ? (
                      <span className={clsx(isDisabled(col, row) && col.type !== "readonly" ? "text-ink-300" : "text-ink-700")}>
                        {col.format ? col.format(row[col.key], row) : row[col.key]}
                      </span>
                    ) : col.type === "number" ? (
                      <input
                        type="number"
                        step={col.step ?? "any"}
                        value={row[col.key] ?? ""}
                        onChange={(e) => updateCell(i, col.key, e.target.value === "" ? "" : Number(e.target.value))}
                        className="w-full rounded-lg border border-transparent bg-transparent px-2 py-1 text-right tabular-nums transition focus:border-brand-300 focus:bg-white focus:outline-none focus:ring-2 focus:ring-brand-100"
                      />
                    ) : col.type === "select" ? (
                      <select
                        value={row[col.key] ?? ""}
                        onChange={(e) => updateCell(i, col.key, e.target.value)}
                        className="w-full cursor-pointer rounded-lg border border-transparent bg-transparent px-2 py-1 transition focus:border-brand-300 focus:bg-white focus:outline-none focus:ring-2 focus:ring-brand-100"
                      >
                        {col.options.map((opt) => (
                          <option key={opt} value={opt}>
                            {opt}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <input
                        type="text"
                        value={row[col.key] ?? ""}
                        onChange={(e) => updateCell(i, col.key, e.target.value)}
                        className="w-full rounded-lg border border-transparent bg-transparent px-2 py-1 transition focus:border-brand-300 focus:bg-white focus:outline-none focus:ring-2 focus:ring-brand-100"
                      />
                    )}
                  </td>
                ))}
                {onRemoveRow && (
                  <td className="border-b border-ink-50 px-2 text-center">
                    <button
                      type="button"
                      onClick={() => onRemoveRow(i)}
                      className="rounded-lg p-1.5 text-ink-300 opacity-0 transition hover:bg-coral/10 hover:text-coral group-hover:opacity-100"
                      aria-label="Remove row"
                    >
                      <Trash2 size={14} />
                    </button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {onAddRow && (
        <button
          type="button"
          onClick={onAddRow}
          className="flex w-full items-center gap-1.5 border-t border-ink-100 px-3 py-2 text-xs font-semibold text-brand-600 transition hover:bg-brand-50/60"
        >
          <Plus size={14} />
          {addLabel}
        </button>
      )}
    </div>
  );
}
