import clsx from "clsx";

const CURRENCIES = ["EUR", "PKR", "USD"];

// EUR is the app's base/default currency; PKR/USD are display-only conversions.
export default function CurrencyToggle({ value, onChange, className }) {
  return (
    <div className={clsx("inline-flex rounded-xl border border-ink-200 bg-ink-50 p-1", className)}>
      {CURRENCIES.map((c) => (
        <button
          key={c}
          type="button"
          onClick={() => onChange(c)}
          className={clsx(
            "rounded-lg px-3 py-1.5 text-xs font-bold tracking-wide transition-all",
            value === c ? "bg-white text-brand-600 shadow-sm" : "text-ink-400 hover:text-ink-600"
          )}
        >
          {c}
        </button>
      ))}
    </div>
  );
}
