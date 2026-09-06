import useCountUp from "../hooks/useCountUp";

// Animated KPI tile: number counts up whenever `value` changes. `value` must be a plain number;
// `suffix`/`prefix` carry the unit so the animated portion stays purely numeric.
export default function KpiCard({ icon: Icon, label, value, decimals = 0, prefix = "", suffix = "", color = "#2a78d6", sublabel, compact = false, compactWords = false }) {
  const display = useCountUp(value, { decimals, compact, compactWords });
  return (
    <div className="group relative overflow-hidden rounded-2xl border border-ink-100 bg-white p-4 shadow-card transition-all duration-300 hover:-translate-y-0.5 hover:shadow-card-hover animate-fade-up">
      <div
        className="absolute -right-6 -top-6 h-20 w-20 rounded-full opacity-[0.10] transition-transform duration-500 group-hover:scale-125"
        style={{ background: color }}
      />
      <div className="relative flex items-start gap-3">
        {Icon && (
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl" style={{ background: `${color}1a` }}>
            <Icon size={20} color={color} strokeWidth={2.2} />
          </div>
        )}
        <div className="min-w-0 flex-1">
          <p className="leading-snug text-xs font-medium uppercase tracking-wide text-ink-400">{label}</p>
          <p className="mt-0.5 truncate font-display text-xl font-extrabold tabular-nums text-ink-900" title={`${prefix}${display}${suffix}`}>
            {prefix}
            {display}
            {suffix && <span className="ml-1 text-sm font-bold text-ink-400">{suffix.trim()}</span>}
          </p>
          {sublabel && <p className="mt-0.5 text-xs text-ink-400">{sublabel}</p>}
        </div>
      </div>
    </div>
  );
}
