import clsx from "clsx";

// Custom segmented control — the replacement for st.tabs (e.g. hourly/daily/weekly/monthly/annual views).
export default function Tabs({ options, value, onChange, className }) {
  return (
    <div className={clsx("inline-flex flex-wrap gap-1 rounded-xl border border-ink-200 bg-ink-50 p-1", className)}>
      {options.map((opt) => {
        const optValue = typeof opt === "string" ? opt : opt.value;
        const optLabel = typeof opt === "string" ? opt : opt.label;
        const active = value === optValue;
        return (
          <button
            key={optValue}
            type="button"
            onClick={() => onChange(optValue)}
            className={clsx(
              "rounded-lg px-3.5 py-1.5 text-sm font-semibold transition-all",
              active ? "bg-white text-brand-600 shadow-sm" : "text-ink-500 hover:text-ink-800"
            )}
          >
            {optLabel}
          </button>
        );
      })}
    </div>
  );
}
