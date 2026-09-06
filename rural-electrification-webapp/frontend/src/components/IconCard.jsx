import { Link } from "react-router-dom";
import { ArrowRight, Check } from "lucide-react";
import clsx from "clsx";

// One of the landing page's six illustrated step cards.
export default function IconCard({ step, done, style }) {
  return (
    <Link
      to={step.path}
      style={style}
      className={clsx(
        "group relative flex animate-fade-up flex-col overflow-hidden rounded-3xl border border-ink-100 bg-white p-6",
        "shadow-card transition-all duration-300 hover:-translate-y-1 hover:shadow-card-hover"
      )}
    >
      <div
        className="absolute -right-10 -top-10 h-32 w-32 rounded-full opacity-[0.08] transition-transform duration-500 group-hover:scale-125"
        style={{ background: step.color }}
      />
      <div className="relative flex items-start justify-between">
        <div
          className="flex h-16 w-16 shrink-0 items-center justify-center overflow-hidden rounded-2xl shadow-sm"
          style={{ background: step.colorSoft }}
        >
          <img src={step.image} alt="" className="h-11 w-11 object-contain" />
        </div>
        <div className="flex items-center gap-2">
          {done && (
            <span className="flex h-6 w-6 items-center justify-center rounded-full bg-leaf/15 text-leaf">
              <Check size={13} strokeWidth={3} />
            </span>
          )}
          <span
            className="flex h-6 w-6 items-center justify-center rounded-full text-[11px] font-bold text-white"
            style={{ background: step.color }}
          >
            {step.index}
          </span>
        </div>
      </div>

      <h3 className="relative mt-5 font-display text-lg font-bold text-ink-900">{step.title}</h3>
      <p className="relative mt-1 text-sm font-semibold" style={{ color: step.color }}>
        {step.tagline}
      </p>
      <p className="relative mt-2 text-sm leading-relaxed text-ink-500">{step.description}</p>

      <div className="relative mt-5 flex items-center gap-1.5 text-sm font-semibold text-ink-400 transition group-hover:gap-2.5" style={{ color: step.color }}>
        {done ? "Review" : "Start"}
        <ArrowRight size={15} />
      </div>
    </Link>
  );
}
