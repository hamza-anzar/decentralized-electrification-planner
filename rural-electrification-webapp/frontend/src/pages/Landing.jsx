import { Zap, BatteryCharging, Gauge, Coins, TrendingUp, Sun as SunIcon } from "lucide-react";
import { STEPS } from "../lib/steps";
import IconCard from "../components/IconCard";
import KpiCard from "../components/KpiCard";
import Disclaimer from "../components/Disclaimer";
import Alert from "../components/Alert";
import { useApiGet } from "../hooks/useApi";
import { useProgress } from "../context/ProgressContext";
import { fmtNumber } from "../lib/format";

export default function Landing() {
  const { progress } = useProgress();
  const { data: dash, error: dashError } = useApiGet("/api/dashboard");

  const hasResults = dash && dash.connectedLoadMw != null;

  return (
    <div className="space-y-10">
      {dashError && (
        <Alert type="error">
          Couldn't reach the server: {dashError}. Is the backend running at {import.meta.env.VITE_API_URL || "http://localhost:8000"}?
        </Alert>
      )}
      <section className="animate-fade-up rounded-3xl border border-ink-100 bg-gradient-to-br from-brand-500 via-brand-500 to-leaf px-6 py-10 text-white shadow-card sm:px-10 sm:py-14">
        <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-white/80">
          <SunIcon size={14} />
          Rural Electrification Planner
        </div>
        <h1 className="mt-3 max-w-2xl font-display text-3xl font-extrabold leading-tight sm:text-4xl">
          Design and Economic Analysis of Rural Electrification System
        </h1>
        <p className="mt-3 max-w-xl text-sm text-white/85 sm:text-base">
          A six-step approach from load estimation to a fully sized system with economic parameters.
        </p>
        {dash?.siteInfo?.project_name && (
          <p className="mt-5 inline-flex items-center gap-2 rounded-full bg-white/15 px-4 py-1.5 text-xs font-semibold backdrop-blur-sm">
            Current project: {dash.siteInfo.project_name}
            {dash.siteInfo.region_city_village ? ` · ${dash.siteInfo.region_city_village}` : ""}
          </p>
        )}
      </section>

      {hasResults && (
        <section>
          <h2 className="mb-3 font-display text-sm font-bold uppercase tracking-wide text-ink-400">Latest snapshot</h2>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <KpiCard icon={Zap} label="Connected Load" value={dash.connectedLoadMw} decimals={2} suffix=" MW" color="#2a78d6" />
            <KpiCard icon={Gauge} label="Annual Demand" value={dash.annualDemandGwh} decimals={2} suffix=" GWh" color="#1baf7a" />
            <KpiCard icon={BatteryCharging} label="Battery Size" value={dash.batteryKwh} decimals={0} suffix=" kWh" color="#eda100" />
            <KpiCard icon={SunIcon} label="Zero-Yield Hrs" value={dash.zeroYieldHours} decimals={0} suffix=" h/yr" color="#eb6834" />
            <KpiCard icon={Coins} label="Capital Cost" value={dash.capitalCostEur} compact prefix="€" color="#7a5cd6" />
            <KpiCard
              icon={TrendingUp}
              label="Lifetime ROI"
              value={dash.roiPct}
              decimals={1}
              suffix="%"
              color={dash.roiPct >= 0 ? "#1baf7a" : "#d65c9e"}
            />
          </div>
        </section>
      )}

      <section>
        <div className="mb-4 flex items-center justify-between">
          <h2 className="font-display text-sm font-bold uppercase tracking-wide text-ink-400">Six-step workflow</h2>
          {dash?.lcoeEurPerKwh != null && (
            <p className="text-xs text-ink-400">LCOE {fmtNumber(dash.lcoeEurPerKwh, 4)} EUR/kWh</p>
          )}
        </div>
        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {STEPS.map((step, i) => (
            <IconCard key={step.key} step={step} done={!!progress?.[step.key]} style={{ animationDelay: `${i * 60}ms` }} />
          ))}
        </div>
      </section>

      <Disclaimer />
    </div>
  );
}
