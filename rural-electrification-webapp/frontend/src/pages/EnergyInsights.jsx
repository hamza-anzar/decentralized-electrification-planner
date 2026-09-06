import { useMemo, useState } from "react";
import { TrendingUp, Gauge, Sigma } from "lucide-react";
import { Card, SectionHeader, PageHeader } from "../components/Card";
import { Field, Slider, Select } from "../components/Field";
import Tabs from "../components/Tabs";
import KpiCard from "../components/KpiCard";
import EChart from "../components/EChart";
import Alert from "../components/Alert";
import { useApiGet } from "../hooks/useApi";
import { stepByPath } from "../lib/steps";
import { fmtNumber } from "../lib/format";
import {
  loadStats,
  hourlyProfileChart,
  dailyProfileChart,
  weeklyProfileChart,
  monthlyTotalsChart,
  yearlyOverviewChart,
  demandGrowthProjectionChart,
} from "../lib/charts";

const step = stepByPath("/energy-insights");
const GRANULARITIES = ["Hourly", "Daily", "Weekly", "Monthly", "Annual", "Multi-Year Growth"];
const UNITS = ["kWh", "MWh", "TWh"];
const SCALED_KEYS = ["total_wh", "A_wh", "B_wh", "C_wh", "Misc_wh"];

export default function EnergyInsights() {
  const { data, loading, error } = useApiGet("/api/demand-profile/hourly");
  const [granularity, setGranularity] = useState("Annual");
  const [unit, setUnit] = useState("MWh");
  const [day, setDay] = useState(1);
  const [month, setMonth] = useState("All");
  const [weekStart, setWeekStart] = useState(1);
  const [projectionYear, setProjectionYear] = useState(1);

  const settings = data?.settings;
  const durationYears = settings?.projectDurationYears ?? 30;
  const growthPct = settings?.annualLoadGrowthPct ?? 3.0;

  // Scale every hourly value by (1+g)^(year-1) so the existing 5 granularity charts can preview any
  // future project year without any change to their own chart-building logic.
  const hourlyProfile = useMemo(() => {
    if (!data?.hourlyProfile) return null;
    if (projectionYear <= 1) return data.hourlyProfile;
    const factor = Math.pow(1 + growthPct / 100, projectionYear - 1);
    return data.hourlyProfile.map((r) => {
      const scaled = { ...r };
      for (const k of SCALED_KEYS) if (k in scaled) scaled[k] = scaled[k] * factor;
      return scaled;
    });
  }, [data, projectionYear, growthPct]);

  const isMultiYear = granularity === "Multi-Year Growth";

  const { option, window } = useMemo(() => {
    if (!hourlyProfile) return { option: null, window: [] };
    if (isMultiYear) {
      return { option: demandGrowthProjectionChart(data.annualWh, settings?.projectStartYear ?? 2026, durationYears, growthPct), window: [] };
    }
    if (granularity === "Hourly") {
      const rows = hourlyProfile.filter((r) => r.day === day);
      return { option: hourlyProfileChart(hourlyProfile, day, unit), window: rows.map((r) => r.total_wh) };
    }
    if (granularity === "Daily") {
      const monthArg = month === "All" ? null : Number(month);
      const rows = monthArg ? hourlyProfile.filter((r) => new Date(r.date).getUTCMonth() + 1 === monthArg) : hourlyProfile;
      return { option: dailyProfileChart(hourlyProfile, unit, monthArg), window: rows.map((r) => r.total_wh) };
    }
    if (granularity === "Weekly") {
      const rows = hourlyProfile.filter((r) => r.day >= weekStart && r.day < weekStart + 7);
      return { option: weeklyProfileChart(hourlyProfile, weekStart, unit), window: rows.map((r) => r.total_wh) };
    }
    if (granularity === "Monthly") {
      return { option: monthlyTotalsChart(hourlyProfile, unit), window: hourlyProfile.map((r) => r.total_wh) };
    }
    return { option: yearlyOverviewChart(hourlyProfile, unit), window: hourlyProfile.map((r) => r.total_wh) };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hourlyProfile, granularity, unit, day, month, weekStart, isMultiYear, data, settings, durationYears, growthPct]);

  const stats = useMemo(() => loadStats(window, unit), [window, unit]);

  return (
    <div className="space-y-6">
      <PageHeader image={step.image} title={step.title} subtitle={step.description} color={step.color} />

      {error && (
        <Alert type="error">{typeof error === "string" ? error : "Could not load the saved demand profile. Visit Demand Profile and save one first."}</Alert>
      )}

      {loading ? (
        <Card className="py-16 text-center text-sm text-ink-400">Loading energy insights…</Card>
      ) : !hourlyProfile ? null : (
        <>
          <Card>
            <SectionHeader icon={TrendingUp} title="Explore the Demand Profile" subtitle="Hourly, daily, weekly, monthly and annual views of the saved 8,760-hour calendar" color={step.color} />
            <div className="flex flex-wrap items-center gap-4">
              <Tabs options={GRANULARITIES} value={granularity} onChange={setGranularity} />
              {!isMultiYear && <Tabs options={UNITS} value={unit} onChange={setUnit} />}

              {!isMultiYear && (
                <Field label={`Projection year: ${projectionYear} of ${durationYears} (${growthPct}%/yr growth)`} className="min-w-[260px] flex-1">
                  <Slider min={1} max={durationYears} value={projectionYear} onChange={(e) => setProjectionYear(Number(e.target.value))} />
                </Field>
              )}

              {!isMultiYear && granularity === "Hourly" && (
                <Field label={`Day of year: ${day}`} className="min-w-[220px] flex-1">
                  <Slider min={1} max={365} value={day} onChange={(e) => setDay(Number(e.target.value))} />
                </Field>
              )}
              {granularity === "Daily" && (
                <Field label="Month" className="w-40">
                  <Select value={month} onChange={(e) => setMonth(e.target.value)}>
                    <option value="All">All months</option>
                    {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => (
                      <option key={m} value={m}>
                        {new Date(2026, m - 1, 1).toLocaleString("default", { month: "long" })}
                      </option>
                    ))}
                  </Select>
                </Field>
              )}
              {granularity === "Weekly" && (
                <Field label={`Week starting day ${weekStart}`} className="min-w-[220px] flex-1">
                  <Slider min={1} max={359} value={weekStart} onChange={(e) => setWeekStart(Number(e.target.value))} />
                </Field>
              )}
            </div>
          </Card>

          {isMultiYear ? (
            <div key="multi-year" className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <KpiCard icon={Gauge} label="Year 1 Annual Demand" value={data.annualWh / 1e9} decimals={4} suffix=" GWh" color="#eb6834" />
              <KpiCard
                icon={TrendingUp}
                label={`Year ${durationYears} Annual Demand`}
                value={(data.annualWh * Math.pow(1 + growthPct / 100, durationYears - 1)) / 1e9}
                decimals={4}
                suffix=" GWh"
                color="#7a5cd6"
              />
              <KpiCard icon={Sigma} label="Annual Growth Rate" value={growthPct} decimals={1} suffix="%/yr" color={step.color} />
            </div>
          ) : (
            <div key="granular" className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <KpiCard icon={Gauge} label="Peak Load" value={stats.peak} decimals={3} suffix={` ${unit}`} color="#eb6834" />
              <KpiCard icon={TrendingUp} label="Average Load" value={stats.average} decimals={3} suffix={` ${unit}`} color="#7a5cd6" />
              <KpiCard icon={Sigma} label="Total (this view)" value={stats.total} decimals={3} suffix={` ${unit}`} color={step.color} />
            </div>
          )}

          <Card padded={false} className="overflow-hidden">
            <EChart option={option || {}} height={440} />
          </Card>

          <p className="text-xs text-ink-400">
            {isMultiYear
              ? `Growth-projected demand, per year, from ${settings?.projectStartYear ?? 2026} — settings are edited on the Demand Profile step.`
              : `Values shown reflect the demand profile last saved on the Demand Profile step${projectionYear > 1 ? `, scaled to project year ${projectionYear}` : ""}. Total annual demand: ${fmtNumber(data.annualWh / 1e9, 4)} GWh.`}
          </p>
        </>
      )}
    </div>
  );
}
