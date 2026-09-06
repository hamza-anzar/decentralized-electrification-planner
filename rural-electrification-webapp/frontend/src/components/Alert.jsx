import { AlertCircle, CheckCircle2, X } from "lucide-react";
import clsx from "clsx";

// Error/success banner — replaces st.error / st.success.
export default function Alert({ type = "error", children, onDismiss, className }) {
  const isError = type === "error";
  return (
    <div
      className={clsx(
        "flex items-start gap-2.5 rounded-xl border px-4 py-3 text-sm animate-fade-up",
        isError ? "border-coral/30 bg-coral/10 text-coral" : "border-leaf/30 bg-leaf/10 text-leaf",
        className
      )}
    >
      {isError ? <AlertCircle size={18} className="mt-0.5 shrink-0" /> : <CheckCircle2 size={18} className="mt-0.5 shrink-0" />}
      <div className="min-w-0 flex-1 break-words">{children}</div>
      {onDismiss && (
        <button onClick={onDismiss} className="shrink-0 rounded-md p-0.5 opacity-60 transition hover:opacity-100">
          <X size={14} />
        </button>
      )}
    </div>
  );
}
