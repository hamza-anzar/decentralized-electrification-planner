import { Link, useLocation } from "react-router-dom";
import { Check } from "lucide-react";
import clsx from "clsx";
import { STEPS } from "../lib/steps";
import { useProgress } from "../context/ProgressContext";

// The persistent top progress rail: "LOAD SETUP -> DEMAND -> INSIGHTS -> SOLAR DESIGN -> FINANCIALS -> RESULTS"
// with a checkmark for completed steps (per /api/progress) and a highlighted dot for the current route.
export default function Stepper() {
  const { pathname } = useLocation();
  const { progress } = useProgress();
  const activeIndex = STEPS.findIndex((s) => s.path === pathname);

  return (
    <nav aria-label="Progress" className="w-full overflow-x-auto">
      <ol className="flex min-w-max items-center gap-1.5 sm:gap-2">
        {STEPS.map((step, i) => {
          const isActive = i === activeIndex;
          const isDone = !!progress?.[step.key] && !isActive;
          return (
            <li key={step.key} className="flex items-center gap-1.5 sm:gap-2">
              <Link
                to={step.path}
                className={clsx(
                  "group flex items-center gap-2 rounded-full border px-2.5 py-1.5 text-[11px] font-bold tracking-wide transition-all sm:px-3.5 sm:py-2 sm:text-xs",
                  isActive
                    ? "border-transparent text-white shadow-sm"
                    : isDone
                    ? "border-ink-200 bg-white text-ink-600 hover:border-brand-300 hover:text-brand-600"
                    : "border-dashed border-ink-200 bg-white/60 text-ink-400 hover:border-ink-300 hover:text-ink-600"
                )}
                style={isActive ? { background: step.color } : undefined}
              >
                <span
                  className={clsx(
                    "flex h-4 w-4 shrink-0 items-center justify-center rounded-full text-[9px] sm:h-4.5 sm:w-4.5",
                    isActive ? "bg-white/25 text-white" : isDone ? "bg-brand-500 text-white" : "bg-ink-100 text-ink-400"
                  )}
                >
                  {isDone ? <Check size={10} strokeWidth={3} /> : isActive ? <span className="h-1.5 w-1.5 rounded-full bg-white" /> : step.index}
                </span>
                <span className="hidden sm:inline">{step.stepperLabel}</span>
              </Link>
              {i < STEPS.length - 1 && <span className="text-ink-300">{"→"}</span>}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
