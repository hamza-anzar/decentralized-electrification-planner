import clsx from "clsx";
import { Loader2 } from "lucide-react";

const VARIANTS = {
  primary: "bg-brand-500 text-white hover:bg-brand-600 shadow-sm hover:shadow-md",
  secondary: "bg-ink-50 text-ink-800 hover:bg-ink-100 border border-ink-200",
  ghost: "text-brand-600 hover:bg-brand-50",
  danger: "bg-coral text-white hover:brightness-95",
};

export default function Button({ children, variant = "primary", icon: Icon, loading, className, ...props }) {
  return (
    <button
      className={clsx(
        "inline-flex items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold transition-all duration-150 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50",
        VARIANTS[variant],
        className
      )}
      disabled={loading || props.disabled}
      {...props}
    >
      {loading ? <Loader2 size={16} className="animate-spin" /> : Icon ? <Icon size={16} /> : null}
      {children}
    </button>
  );
}
