import clsx from "clsx";

export function Card({ children, className, padded = true }) {
  return (
    <div className={clsx("rounded-2xl border border-ink-100 bg-white shadow-card", padded && "p-5 md:p-6", className)}>
      {children}
    </div>
  );
}

export function SectionHeader({ icon: Icon, title, subtitle, color = "#2a78d6", className }) {
  return (
    <div className={clsx("mb-4 flex items-center gap-3", className)}>
      {Icon && (
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl" style={{ background: `${color}1a` }}>
          <Icon size={18} color={color} strokeWidth={2.2} />
        </div>
      )}
      <div>
        <h3 className="font-display text-base font-bold text-ink-900">{title}</h3>
        {subtitle && <p className="text-sm text-ink-400">{subtitle}</p>}
      </div>
    </div>
  );
}

export function PageHeader({ image, title, subtitle, color }) {
  return (
    <div className="mb-6 flex flex-col items-start gap-4 sm:flex-row sm:items-center">
      {image && (
        <img
          src={image}
          alt=""
          className="h-16 w-16 shrink-0 rounded-2xl object-cover shadow-card ring-4"
          style={{ "--tw-ring-color": `${color}22` }}
        />
      )}
      <div>
        <h1 className="font-display text-2xl font-extrabold text-ink-900 md:text-3xl">{title}</h1>
        {subtitle && <p className="mt-1 max-w-2xl text-sm text-ink-500">{subtitle}</p>}
      </div>
    </div>
  );
}
