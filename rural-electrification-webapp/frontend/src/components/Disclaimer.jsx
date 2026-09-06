import { AlertTriangle } from "lucide-react";

export default function Disclaimer({ compact = false }) {
  if (compact) {
    return (
      <p className="flex items-center gap-1.5 text-[11px] text-ink-400">
        <AlertTriangle size={12} className="shrink-0 text-sun" />
        Academic project — figures are illustrative and not accurate for real-time or investment use.
      </p>
    );
  }
  return (
    <div className="flex items-start gap-3 rounded-2xl border border-sun/30 bg-sun/10 px-4 py-3 text-sm text-ink-700">
      <AlertTriangle size={18} className="mt-0.5 shrink-0 text-sun" />
      <p>
        <span className="font-semibold text-ink-900">Academic project.</span> This tool and its outputs are for
        educational demonstration only, and are not applicable or accurate for real-time or investment-grade
        engineering purposes.
      </p>
    </div>
  );
}
