import { Link } from "react-router-dom";
import { Sun } from "lucide-react";
import Stepper from "./Stepper";
import Disclaimer from "./Disclaimer";

export default function Layout({ children }) {
  return (
    <div className="min-h-screen bg-[#f6f7f9] bg-dot-grid">
      <header className="sticky top-0 z-20 border-b border-ink-100/80 bg-white/85 backdrop-blur-md">
        <div className="mx-auto flex max-w-7xl flex-col gap-3 px-4 py-3 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between gap-4">
            <Link to="/" className="flex shrink-0 items-center gap-2.5">
              <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-brand-500 shadow-glow">
                <Sun size={18} className="text-white" strokeWidth={2.4} />
              </span>
              <span className="hidden font-display text-base font-extrabold tracking-tight text-ink-900 sm:block">
                Rural Electrification Planner
              </span>
            </Link>
            <Stepper />
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">{children}</main>

      <footer className="mx-auto max-w-7xl px-4 pb-8 sm:px-6 lg:px-8">
        <Disclaimer compact />
      </footer>
    </div>
  );
}
