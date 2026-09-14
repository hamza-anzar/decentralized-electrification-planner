import { useEffect, useMemo, useRef, useState } from "react";
import {
  MapPin, Home, Users, Sun, Wind, BatteryCharging, TimerOff, CalendarClock, Zap,
  Coins, Receipt, TrendingUp, Hourglass, Wallet, Download,
} from "lucide-react";
import { Card, SectionHeader } from "../../components/Card";
import KpiCard from "../../components/KpiCard";
import Button from "../../components/Button";
import Alert from "../../components/Alert";
import EChart from "../../components/EChart";
import CurrencyToggle from "../../components/CurrencyToggle";
import EditableTable from "../../components/Table";
import { Field, Slider } from "../../components/Field";
import { useApiGet } from "../../hooks/useApi";
import { useProgress } from "../../context/ProgressContext";
import { api } from "../../api/client";
import { humanizeParam } from "../../lib/labels";
import { convertCurrency, fmtNumber } from "../../lib/format";
import { gaugeChart, cumulativeCashflowChart } from "../../lib/charts";

const SCENARIO_LABELS = { battery: "Solar+Battery", diesel: "Solar+Diesel", wind_battery: "Wind+Battery", wind_diesel: "Wind+Diesel" };

export default function ResultsScenario({ systemType, color }) {
  const isDiesel = systemType === "diesel" || systemType === "wind_diesel";
  const isWind = systemType === "wind_battery" || systemType === "wind_diesel";
  const scenarioLabel = SCENARIO_LABELS[systemType] || systemType;
  const { data: ctx, loading: ctxLoading, error: ctxError } = useApiGet(`/api/results/context?system_type=${systemType}`);
  const { refetchProgress } = useProgress();

  const [roiParameters, setRoiParameters] = useState(null);
  const [currency, setCurrency] = useState("EUR");
  const [showComparison, setShowComparison] = useState(true);
  const [comparePct, setComparePct] = useState(150);

  const [result, setResult] = useState(null);
  const [computing, setComputing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [saved, setSaved] = useState(false);

  const [tariffMarkupPct, setTariffMarkupPct] = useState(20);
  const [billing, setBilling] = useState(null);
  const [billingError, setBillingError] = useState(null);
  const [showCashflow, setShowCashflow] = useState(false);
  const [exporting, setExporting] = useState(false);

  async function handleExport() {
    setExporting(true);
    try {
      await api.download(`/api/results/export?system_type=${systemType}`, `Results_Export_${systemType}.xlsx`);
    } catch (e) {
      setError(e.detail?.errors?.join(" ") || e.message || String(e));
    } finally {
      setExporting(false);
    }
  }

  // Separate from the ROI cash-flow tariff below — a quick "what would category X pay" estimate at
  // tariff = LCOE x (1 + markup%). Only available once the computed (day-type-based) demand profile exists.
  useEffect(() => {
    if (!ctx) return;
    const handle = setTimeout(() => {
      api
        .post(`/api/results/billing?system_type=${systemType}`, { tariffMarkupPct })
        .then((r) => {
          setBilling(r);
          setBillingError(null);
        })
        .catch((e) => {
          setBilling(null);
          setBillingError(e.detail?.errors?.join(" ") || e.message);
        });
    }, 400);
    return () => clearTimeout(handle);
  }, [ctx, tariffMarkupPct, systemType]);

  const initialized = useRef(false);
  useEffect(() => {
    if (initialized.current || !ctx) return;
    initialized.current = true;
    setRoiParameters(ctx.roiParameters);
  }, [ctx]);

  useEffect(() => {
    if (!roiParameters) return;
    setComputing(true);
    const handle = setTimeout(() => {
      api
        .post(`/api/results/compute?system_type=${systemType}`, { roiParameters, comparePct: showComparison ? comparePct : null })
        .then((r) => {
          setResult(r);
          setError(null);
        })
        .catch((e) => setError(e.detail?.errors?.join(" ") || e.message))
        .finally(() => setComputing(false));
    }, 400);
    return () => clearTimeout(handle);
  }, [roiParameters, showComparison, comparePct, systemType]);

  async function handleSave() {
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      const r = await api.post(`/api/results/save?system_type=${systemType}`, { roiParameters, comparePct: showComparison ? comparePct : null });
      setResult(r);
      setSaved(true);
      refetchProgress();
    } catch (e) {
      setError(e.detail?.errors?.join(" ") || e.message || String(e));
    } finally {
      setSaving(false);
    }
  }

  const conv = (eur) => (eur == null ? null : convertCurrency(eur, currency, ctx?.costParameters ? getParam(ctx.costParameters, "eur_to_pkr_rate") : null, ctx?.costParameters ? getParam(ctx.costParameters, "eur_to_usd_rate") : null));

  const chartScenarios = useMemo(() => {
    if (!result) return [];
    const tariff = getParam(roiParameters, "electricity_tariff_eur_per_kwh");
    const scenarios = [
      { label: `${fmtNumber(tariff, 3)} EUR/kWh`, color: "#2a78d6", yearly: result.cashflow.yearly, discountedPaybackYears: result.cashflow.discounted_payback_years },
    ];
    if (result.compareCashflow) {
      scenarios.push({
        label: `${fmtNumber(result.compareTariffEur, 3)} EUR/kWh (${comparePct}%)`,
        color: "#eb6834",
        yearly: result.compareCashflow.yearly,
        discountedPaybackYears: result.compareCashflow.discounted_payback_years,
      });
    }
    return scenarios;
  }, [result, roiParameters, comparePct]);

  if (ctxLoading) {
    return <Card className="py-16 text-center text-sm text-ink-400">Loading results…</Card>;
  }

  if (ctxError || !ctx) {
    return (
      <Alert type="error">
        Missing results from earlier steps — visit and save Load Setup, Demand Profile, System Design's{" "}
        {scenarioLabel} tab, and Financials' {scenarioLabel} tab first.
      </Alert>
    );
  }

  const site = ctx.siteInfo;
  const roiPct = result?.cashflow.roi_pct;
  const gaugeMax = roiPct != null ? Math.max(50, Math.abs(roiPct) * 1.2) : 50;
  const gaugeColor = roiPct >= 0 ? "#1baf7a" : "#eb6834";

  const sections = result ? groupBy(result.masterSummary, (r) => r.section) : {};

  return (
    <div className="space-y-6">
      {error && <Alert type="error" onDismiss={() => setError(null)}>{error}</Alert>}
      {saved && <Alert type="success" onDismiss={() => setSaved(false)}>Results saved — ROI parameters and the master summary are now on record for this project.</Alert>}

      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-xs text-ink-400">Cost figures below use EUR (base currency) unless converted.</p>
        <div className="flex items-center gap-3">
          <Button variant="secondary" icon={Download} onClick={handleExport} loading={exporting}>
            Export Results (Excel)
          </Button>
          <CurrencyToggle value={currency} onChange={setCurrency} />
        </div>
      </div>

      <Card>
        <SectionHeader icon={MapPin} title="Project Overview" color="#7a5cd6" />
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <KpiTile icon={MapPin} label="Project" value={site.project_name || "—"} color="#7a5cd6" />
          <KpiTile icon={MapPin} label="Location" value={`${site.region_city_village || "—"}, ${site.country || "—"}`} color="#2a78d6" />
          <KpiCard icon={Home} label="Houses" value={ctx.totalHouses} decimals={0} color="#eda100" />
          <KpiCard icon={Users} label="Population" value={Number(site.population) || 0} decimals={0} color="#1baf7a" />
        </div>
        <p className="mt-3 text-xs text-ink-400">
          Lat/Lon: {site.latitude}, {site.longitude} · Area: {site.area_km2} km² · Climate: {site.weather_type} · Socio-economic
          class: {site.socioeconomic_class} · Pre-project electrification: {site.electrification_pct}%
        </p>
      </Card>

      <Card>
        <SectionHeader title="System & Cost Summary" color={color} />
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {isWind ? (
            <KpiCard icon={Wind} label="Installed Turbine Capacity" value={isDiesel ? ctx.pvResults.wind_installed_capacity_kw : ctx.pvResults.installed_capacity_kw} decimals={0} suffix=" kW" color="#eda100" />
          ) : (
            <KpiCard icon={Sun} label="System Size (Ppeak)" value={ctx.pvParameters.ppeak_w / 1e6} decimals={3} suffix=" MW" color="#eda100" />
          )}
          {isDiesel ? (
            <KpiCard icon={Zap} label="Generator Capacity" value={ctx.pvResults.installed_capacity_kw} decimals={0} suffix=" kW" color="#2a78d6" />
          ) : (
            <KpiCard icon={BatteryCharging} label="Battery Size" value={ctx.pvResults.battery_capacity_kwh} decimals={0} suffix=" kWh" color="#2a78d6" />
          )}
          <KpiCard icon={TimerOff} label="No-Electricity Hours" value={isDiesel ? ctx.pvResults.unmet_hours : ctx.pvResults.zero_yield_hours} decimals={0} suffix=" h/yr" color="#eb6834" />
          <KpiCard icon={CalendarClock} label="Project Lifetime" value={ctx.projectLifetimeYears} decimals={0} suffix=" yrs" color="#7a5cd6" />
          <KpiCard icon={Zap} label="Annual Demand" value={ctx.annualDemandWh / 1e9} decimals={4} suffix=" GWh" color="#2a78d6" />
          <KpiCard icon={isWind ? Wind : Sun} label={isWind ? "Annual Wind Generation" : "Annual Generation"} value={ctx.pvResults.annual_egen_wh / 1e9} decimals={4} suffix=" GWh" color="#eda100" />
          <KpiCard icon={Coins} label="Investment Cost" value={conv(ctx.costLcoeResults.capital_cost_eur)} compactWords suffix={` ${currency}`} color="#1baf7a" />
          <KpiCard icon={Receipt} label="LCOE" value={conv(ctx.costLcoeResults.lcoe_eur_per_kwh)} decimals={4} suffix={` ${currency}/kWh`} color="#d65c9e" />
        </div>
      </Card>

      {roiParameters && (
        <>
          <Card>
            <SectionHeader
              icon={Wallet}
              title="Estimated Monthly Bills"
              subtitle="Average monthly bill per customer type, at tariff = LCOE x (1 + markup%) — a separate, simpler estimate from the ROI tariff below"
              color="#1baf7a"
            />
            <Field label={`Tariff markup over LCOE: ${tariffMarkupPct}%`} className="mb-4 max-w-md">
              <Slider min={0} max={50} step={1} value={tariffMarkupPct} onChange={(e) => setTariffMarkupPct(Number(e.target.value))} />
            </Field>
            {billingError ? (
              <Alert type="error">{billingError}</Alert>
            ) : billing ? (
              <>
                <p className="mb-3 text-xs text-ink-400">
                  Tariff used: <strong>{fmtNumber(conv(billing.tariff_eur_per_kwh), 4)} {currency}/kWh</strong> (LCOE +{tariffMarkupPct}%).
                  Household categories show the average bill per household; community loads (hospital, school,
                  street lighting, etc.) show one total bill for the whole shared load.
                </p>
                <EditableTable
                  columns={[
                    { key: "label", label: "Customer / Load Type", type: "readonly" },
                    { key: "avg_monthly_kwh", label: "Avg. Monthly Consumption (kWh)", type: "readonly", format: (v) => fmtNumber(v, 1) },
                    { key: "avg_monthly_bill_eur", label: `Avg. Monthly Bill (${currency})`, type: "readonly", format: (v) => fmtNumber(conv(v), 2) },
                  ]}
                  rows={billing.rows}
                  onChange={() => {}}
                />
              </>
            ) : (
              <p className="py-6 text-center text-sm text-ink-400">Calculating…</p>
            )}
          </Card>

          <Card>
            <SectionHeader title="ROI Assumptions" color="#eb6834" />
            <Alert type="error" className="mb-4">
              The source workbook has no revenue model at all — only cost (LCOE). <strong>electricity_tariff_eur_per_kwh</strong>{" "}
              below defaults to an explicit break-even placeholder (= the computed LCOE), not a researched market rate. Replace it
              with a real planned tariff, subsidy, or avoided-cost figure for a meaningful ROI — everything below (payback, NPV,
              ROI) moves directly off of it.
            </Alert>
            <EditableTable
              columns={[
                { key: "parameter", label: "Parameter", type: "readonly", format: (v) => humanizeParam(v) },
                { key: "value", label: "Value", type: "number", width: 130 },
                { key: "unit", label: "Unit", type: "readonly", width: 130 },
                { key: "description", label: "Description", type: "readonly" },
              ]}
              rows={roiParameters}
              onChange={setRoiParameters}
            />

            <div className="mt-4 flex flex-wrap items-center gap-4">
              <label className="flex items-center gap-2 text-sm font-medium text-ink-700">
                <input type="checkbox" checked={showComparison} onChange={(e) => setShowComparison(e.target.checked)} className="h-4 w-4 rounded accent-brand-500" />
                Show a comparison scenario at a different tariff
              </label>
              {showComparison && (
                <Field label={`Comparison tariff: ${comparePct}% of current`} className="max-w-md flex-1">
                  <Slider min={50} max={200} step={10} value={comparePct} onChange={(e) => setComparePct(Number(e.target.value))} />
                </Field>
              )}
            </div>
          </Card>

          <Card>
            <SectionHeader icon={TrendingUp} title="ROI, Payback & Investment Results" color={color} />
            <div className="mb-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
              <KpiCard icon={Receipt} label="Year-1 Operating Cost" value={result ? conv(result.yearlyOpexEur) : null} compactWords suffix={` ${currency}`} color="#eb6834" />
              <KpiCard icon={Coins} label="NPV" value={result ? conv(result.cashflow.npv_eur) : null} compactWords suffix={` ${currency}`} color="#7a5cd6" />
              <KpiCard
                icon={Hourglass}
                label="Simple Payback"
                value={result?.cashflow.simple_payback_years ?? null}
                decimals={1}
                suffix=" yr"
                sublabel={result && result.cashflow.simple_payback_years == null ? `never within ${ctx.projectLifetimeYears}yr` : undefined}
                color="#1baf7a"
              />
              <KpiCard
                icon={Hourglass}
                label="Discounted Payback"
                value={result?.cashflow.discounted_payback_years ?? null}
                decimals={1}
                suffix=" yr"
                sublabel={result && result.cashflow.discounted_payback_years == null ? `never within ${ctx.projectLifetimeYears}yr` : undefined}
                color="#2a78d6"
              />
            </div>

            <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
              <div className="lg:col-span-1">
                <EChart option={roiPct != null ? gaugeChart(roiPct, "Lifetime ROI", { unit: "%", maxValue: gaugeMax, color: gaugeColor }) : {}} height={280} loading={!result} />
                <p className="px-2 text-center text-xs text-ink-400">
                  Off-grid rural electrification projects like this one are usually <strong>not</strong> profitable on tariff
                  revenue alone — a negative ROI here is the expected, typical result, not a bug.
                </p>
              </div>
              <div className="lg:col-span-2">
                <EChart option={chartScenarios.length ? cumulativeCashflowChart(chartScenarios) : {}} height={360} loading={!result} />
              </div>
            </div>

            <details className="mt-4 rounded-xl border border-ink-100 p-4 text-sm text-ink-600">
              <summary className="cursor-pointer font-semibold text-ink-800">Why might "tariff = LCOE" not show NPV = 0?</summary>
              <p className="mt-2 leading-relaxed text-ink-500">
                Financials' LCOE is a blended figure — it discounts O&amp;M (and, for Solar+Diesel, fuel) to a present value but
                leaves capex, replacement costs, and land undiscounted, then divides by energy served. This cash-flow model uses
                the full nominal (escalating) cost series and earns revenue on total demand. Both are legitimate views, they just
                don't coincide by default — don't read too much into a negative NPV at the break-even placeholder tariff; it's an
                artifact of using LCOE as a stand-in price, not a statement the project loses money. Replace the tariff with your
                real assumption for a meaningful answer.
              </p>
            </details>

            {result && (
              <div className="mt-4">
                <Button variant="secondary" icon={CalendarClock} onClick={() => setShowCashflow((v) => !v)}>
                  {showCashflow ? "Hide" : "View"} Annual Cash Flow
                </Button>
                {showCashflow && (
                  <div className="mt-3 rounded-xl border border-ink-100 p-4 text-sm">
                    <p className="mb-3 text-xs text-ink-400">
                      Year-by-year cash flow for the primary scenario, in EUR. Revenue grows with both the tariff escalation
                      and the load-growth rate set above (see the annual_load_growth_pct row).
                    </p>
                    <EditableTable
                      dense
                      columns={[
                        { key: "year", label: "Year", type: "readonly", width: 60 },
                        { key: "revenue_eur", label: "Revenue", type: "readonly", format: (v) => fmtNumber(v, 0) },
                        { key: "om_cost_eur", label: "O&M Cost", type: "readonly", format: (v) => fmtNumber(v, 0) },
                        { key: "land_cost_eur", label: "Land Cost", type: "readonly", format: (v) => fmtNumber(v, 0) },
                        { key: "replacement_cost_eur", label: "Replacement", type: "readonly", format: (v) => fmtNumber(v, 0) },
                        { key: "net_cash_flow_eur", label: "Net Cash Flow", type: "readonly", format: (v) => fmtNumber(v, 0) },
                        { key: "cumulative_discounted_eur", label: "Cumulative (Disc.)", type: "readonly", format: (v) => fmtNumber(v, 0) },
                      ]}
                      rows={result.cashflow.yearly}
                      onChange={() => {}}
                    />
                  </div>
                )}
              </div>
            )}
          </Card>

          <Card>
            <SectionHeader title="Master Summary — Every Step's Key Result" color="#767468" />
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {Object.entries(sections).map(([sectionName, rows]) => (
                <div key={sectionName} className="rounded-xl border border-ink-100 bg-ink-50/40 p-4">
                  <p className="mb-2 text-xs font-bold uppercase tracking-wide text-ink-500">{sectionName}</p>
                  <dl className="space-y-1.5">
                    {rows.map((r, i) => (
                      <div key={i} className="flex items-baseline justify-between gap-2 text-sm">
                        <dt className="text-ink-500">{r.metric}</dt>
                        <dd className="whitespace-nowrap font-semibold tabular-nums text-ink-800">
                          {fmtNumber(r.value, r.unit === "%" || r.unit?.includes("kWh") ? 4 : 2)} {r.unit}
                        </dd>
                      </div>
                    ))}
                  </dl>
                </div>
              ))}
            </div>
          </Card>

          <div className="flex items-center justify-end gap-3 pb-4">
            {computing && <span className="text-xs text-ink-400">Recalculating…</span>}
            <Button onClick={handleSave} loading={saving}>
              Save Results
            </Button>
          </div>
        </>
      )}
    </div>
  );
}

function KpiTile({ icon: Icon, label, value, color }) {
  return (
    <div className="relative overflow-hidden rounded-2xl border border-ink-100 bg-white p-4 shadow-card">
      <div className="flex items-start gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl" style={{ background: `${color}1a` }}>
          <Icon size={20} color={color} strokeWidth={2.2} />
        </div>
        <div className="min-w-0">
          <p className="text-xs font-medium uppercase tracking-wide text-ink-400">{label}</p>
          <p className="mt-0.5 truncate font-display text-base font-bold text-ink-900" title={value}>
            {value}
          </p>
        </div>
      </div>
    </div>
  );
}

function getParam(rows, name) {
  const row = rows.find((r) => r.parameter === name);
  return row ? row.value : null;
}

function groupBy(rows, keyFn) {
  const out = {};
  for (const r of rows) {
    const k = keyFn(r);
    (out[k] ||= []).push(r);
  }
  return out;
}
