import { useEffect, useMemo, useState } from "react";
import { Coins, Receipt, TimerOff, TrendingUp, Wallet } from "lucide-react";
import { Card, SectionHeader } from "../../components/Card";
import { Field, Slider } from "../../components/Field";
import KpiCard from "../../components/KpiCard";
import Alert from "../../components/Alert";
import EChart from "../../components/EChart";
import { api } from "../../api/client";
import { scenarioComparisonBarChart } from "../../lib/charts";

const ROWS = [
  { key: "lcoeEurPerKwh", label: "LCOE (EUR/kWh)", decimals: 4 },
  { key: "capitalCostEur", label: "Capital Cost (EUR)", decimals: 0 },
  { key: "totalOpexEur", label: "Total Opex, Lifetime (EUR)", decimals: 0 },
  { key: "unmetOrZeroYieldHours", label: "No-Electricity Hours (h/yr)", decimals: 0 },
  { key: "roiPct", label: "Lifetime ROI (%)", decimals: 1 },
  { key: "npvEur", label: "NPV (EUR)", decimals: 0 },
  { key: "simplePaybackYears", label: "Simple Payback (years)", decimals: 1 },
];

function avgHouseholdBill(billing) {
  if (!billing) return null;
  const hh = billing.rows.filter((r) => r.kind === "per_household");
  if (!hh.length) return null;
  return hh.reduce((a, r) => a + (r.avg_monthly_bill_eur || 0), 0) / hh.length;
}

export default function ResultsOverview() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [tariffMarkupPct, setTariffMarkupPct] = useState(20);
  const [billing, setBilling] = useState({ battery: null, diesel: null });

  useEffect(() => {
    api
      .get("/api/results/overview")
      .then(setData)
      .catch((e) => setError(e.message || String(e)));
  }, []);

  useEffect(() => {
    if (!data) return;
    const handle = setTimeout(() => {
      const load = (systemType) =>
        data[systemType]
          ? api.post(`/api/results/billing?system_type=${systemType}`, { tariffMarkupPct }).catch(() => null)
          : Promise.resolve(null);
      Promise.all([load("battery"), load("diesel")]).then(([battery, diesel]) => setBilling({ battery, diesel }));
    }, 400);
    return () => clearTimeout(handle);
  }, [data, tariffMarkupPct]);

  const recommendedTariff = useMemo(
    () => ({
      battery: data?.battery ? data.battery.lcoeEurPerKwh * (1 + tariffMarkupPct / 100) : null,
      diesel: data?.diesel ? data.diesel.lcoeEurPerKwh * (1 + tariffMarkupPct / 100) : null,
    }),
    [data, tariffMarkupPct]
  );

  if (error) return <Alert type="error">{error}</Alert>;
  if (!data) return <Card className="py-16 text-center text-sm text-ink-400">Loading overview…</Card>;

  const { battery, diesel } = data;
  const neitherConfigured = !battery && !diesel;

  return (
    <div className="space-y-6">
      {neitherConfigured && (
        <Alert type="error">
          Neither scenario has been saved yet — visit Solar Design and Financials (Battery and/or Diesel tabs) and save
          results first, then come back here to compare them.
        </Alert>
      )}
      {!battery && !neitherConfigured && <Alert type="error">Solar+Battery hasn't been fully saved yet — visit its Solar Design and Financials tabs.</Alert>}
      {!diesel && !neitherConfigured && <Alert type="error">Solar+Diesel hasn't been fully saved yet — visit its Solar Design and Financials tabs.</Alert>}

      <Card>
        <SectionHeader icon={TrendingUp} title="Battery vs. Diesel — Key Results" color="#7a5cd6" />
        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {ROWS.map((row) => (
            <Card key={row.key} padded={false} className="overflow-hidden">
              <EChart
                option={scenarioComparisonBarChart(
                  row.label,
                  "",
                  battery ? battery[row.key] : null,
                  diesel ? diesel[row.key] : null,
                  row.decimals
                )}
                height={260}
              />
            </Card>
          ))}
        </div>
      </Card>

      <Card>
        <SectionHeader
          icon={Wallet}
          title="Recommended Tariff & Billing"
          subtitle="Recommended tariff = LCOE x (1 + markup%) — default +20%, editable below; feeds an average household monthly bill estimate for each scenario"
          color="#1baf7a"
        />
        <Field label={`Tariff markup over LCOE: ${tariffMarkupPct}%`} className="mb-5 max-w-md">
          <Slider min={0} max={50} step={1} value={tariffMarkupPct} onChange={(e) => setTariffMarkupPct(Number(e.target.value))} />
        </Field>
        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
          <div className="grid grid-cols-2 gap-3">
            <KpiCard icon={Receipt} label="Battery — Recommended Tariff" value={recommendedTariff.battery} decimals={4} suffix=" EUR/kWh" color="#2a78d6" />
            <KpiCard icon={Coins} label="Battery — Avg. Household Bill" value={avgHouseholdBill(billing.battery)} decimals={2} suffix=" EUR/mo" color="#1baf7a" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <KpiCard icon={Receipt} label="Diesel — Recommended Tariff" value={recommendedTariff.diesel} decimals={4} suffix=" EUR/kWh" color="#eb6834" />
            <KpiCard icon={Coins} label="Diesel — Avg. Household Bill" value={avgHouseholdBill(billing.diesel)} decimals={2} suffix=" EUR/mo" color="#eda100" />
          </div>
        </div>
      </Card>

      <p className="flex items-center gap-2 text-xs text-ink-400">
        <Coins size={14} /> Capital &amp; Opex in EUR · <Receipt size={14} /> LCOE per kWh served ·{" "}
        <TimerOff size={14} /> No-electricity hours = zero-yield hours (Battery) or unmet-demand hours (Diesel) — the same
        underlying concept for each technology.
      </p>
    </div>
  );
}
