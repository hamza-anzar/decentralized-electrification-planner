import clsx from "clsx";

const baseInput =
  "w-full rounded-xl border border-ink-200 bg-white px-3 py-2 text-sm text-ink-900 shadow-sm transition focus:border-brand-400 focus:outline-none focus:ring-4 focus:ring-brand-100 disabled:bg-ink-50 disabled:text-ink-400";

export function Field({ label, hint, children, className }) {
  return (
    <label className={clsx("block", className)}>
      {label && <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-500">{label}</span>}
      {children}
      {hint && <span className="mt-1 block text-xs text-ink-400">{hint}</span>}
    </label>
  );
}

export function TextInput({ className, ...props }) {
  return <input type="text" className={clsx(baseInput, className)} {...props} />;
}

export function NumberInput({ className, ...props }) {
  return <input type="number" className={clsx(baseInput, "tabular-nums", className)} {...props} />;
}

export function Select({ className, children, ...props }) {
  return (
    <select className={clsx(baseInput, "cursor-pointer appearance-none bg-[url('data:image/svg+xml;utf8,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 24 24%22 fill=%22none%22 stroke=%22%238b8a80%22 stroke-width=%222%22><polyline points=%226 9 12 15 18 9%22/></svg>')] bg-[length:16px] bg-[right_10px_center] bg-no-repeat pr-9", className)} {...props}>
      {children}
    </select>
  );
}

export function Slider({ className, ...props }) {
  return (
    <input
      type="range"
      className={clsx("h-2 w-full cursor-pointer appearance-none rounded-full bg-ink-100 accent-brand-500", className)}
      {...props}
    />
  );
}
