import { useEffect, useMemo, useRef, useState } from "react";
import { Coins, Receipt, MapPinned, Sliders } from "lucide-react";
import { Card, SectionHeader } from "../../components/Card";
import EditableTable from "../../components/Table";
import KpiCard from "../../components/KpiCard";
import Button from "../../components/Button";
import Alert from "../../components/Alert";
import EChart from "../../components/EChart";
import CurrencyToggle from "../../components/CurrencyToggle";
import FileUpload from "../../components/FileUpload";
import { useApiGet } from "../../hooks/useApi";
import { useProgress } from "../../context/ProgressContext";
import { api } from "../../api/client";
import { humanizeParam } from "../../lib/labels";
import { convertCurrency, fmtNumber } from "../../lib/format";
import { boqCostBreakdownPieChart } from "../../lib/charts";

const LAND_APPROACHES = ["buy", "private_lease", "govt_lease", "none"];
const SYSTEM_SCALED = new Set(["Wind Turbine(s)", "Battery System"]);
const blankDash = (v) => (v === null || v === undefined || v === "" ? "—" : v);

export default function FinancialsWindBattery({ color }) {
  const { data: defaults, error: loadError } = useApiGet("/api/financials-wind-battery/defaults");
  const { refetchProgress } = useProgress();

  const [boqItems, setBoqItems] = useState(null);
  const [landCostOptions, setLandCostOptions] = useState(null);
  const [costParameters, setCostParameters] = useState(null);
  const [currency, setCurrency] = useState("EUR");

  const [result, setResult] = useState(null);
  const [computing, setComputing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [saved, setSaved] = useState(false);

  const initialized = useRef(false);
  useEffect(() => {
    if (initialized.current || !defaults) return;
    initialized.current = true;
    const round2 = (v) => (typeof v === "number" ? Math.round(v * 100) / 100 : v);
    setBoqItems(defaults.boqItems);
    setLandCostOptions(defaults.landCostOptions.map((r) => ({ ...r, total_cost_eur: round2(r.total_cost_eur) })));
    setCostParameters(defaults.costParameters);
  }, [defaults]);

  useEffect(() => {
    if (!boqItems || !landCostOptions || !costParameters) return;
    setComputing(true);
    const handle = setTimeout(() => {
      api
        .post("/api/financials-wind-battery/compute", { boqItems, landCostOptions, costParameters })
        .then((r) => {
          setResult(r);
          setError(null);
        })
        .catch((e) => setError(e.detail?.errors?.join(" ") || e.message))
        .finally(() => setComputing(false));
    }, 400);
    return () => clearTimeout(handle);
  }, [boqItems, landCostOptions, costParameters]);

  async function handleSave() {
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      const r = await api.post("/api/financials-wind-battery/save", { boqItems, landCostOptions, costParameters });
      setResult(r);
      setSaved(true);
      refetchProgress();
    } catch (e) {
      setError(e.detail?.errors?.join(" ") || e.message || String(e));
    } finally {
      setSaving(false);
    }
  }

  function updateParam(paramName, value) {
    setCostParameters(costParameters.map((r) => (r.parameter === paramName ? { ...r, value } : r)));
  }

  const ready = boqItems && landCostOptions && costParameters;
  const eurToPkr = result?.eurToPkr;
  const eurToUsd = result?.eurToUsd;
  const conv = (eur) => (eur == null ? null : convertCurrency(eur, currency, eurToPkr, eurToUsd));
  const convertedBoqItems = result ? result.boq.items.map((r) => ({ ...r, total_cost_eur: conv(r.total_cost_eur) })) : null;

  // total_cost_eur is always server-computed (qty x unit_cost, or system-size x lumpsum rate for the
  // system-scaled rows) — merge the latest computed value onto the editable rows for display only.
  const displayBoqRows = useMemo(() => {
    if (!boqItems) return boqItems;
    const computed = new Map((result?.boq.items || []).map((r) => [r.item_no, r.total_cost_eur]));
    return boqItems.map((r) => ({ ...r, total_cost_eur: computed.has(r.item_no) ? computed.get(r.item_no) : r.total_cost_eur }));
  }, [boqItems, result]);

  return (
    <div className="space-y-6">
      {error && <Alert type="error" onDismiss={() => setError(null)}>{error}</Alert>}
      {saved && <Alert type="success" onDismiss={() => setSaved(false)}>Financials saved — the Results step now uses this capital cost and LCOE.</Alert>}
      {loadError && <Alert type="error">Couldn't load Financials data from the server: {loadError}. Is the backend running at {import.meta.env.VITE_API_URL || "http://localhost:8000"}?</Alert>}

      {!ready ? (
        <Card className="py-16 text-center text-sm text-ink-400">{loadError ? "Couldn't load — see the error above." : "Loading financials…"}</Card>
      ) : (
        <>
          <div className="flex items-center justify-between">
            <p className="text-xs text-ink-400">EUR is this project's base currency. PKR/USD below are display-only.</p>
            <CurrencyToggle value={currency} onChange={setCurrency} />
          </div>

          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <KpiCard icon={Coins} label="Capital Cost" value={result ? conv(result.capital_cost_eur) : null} compact suffix={` ${currency}`} color={color} />
            <KpiCard icon={Receipt} label="Total Opex (Lifetime)" value={result ? conv(result.opex.total_opex_eur) : null} compact suffix={` ${currency}`} color="#7a5cd6" />
            <KpiCard icon={Sliders} label="Total Cost" value={result ? conv(result.lcoe.total_cost_eur) : null} compact suffix={` ${currency}`} color="#2a78d6" />
            <KpiCard icon={MapPinned} label="LCOE" value={result ? conv(result.lcoe.lcoe_eur_per_kwh) : null} decimals={4} suffix={` ${currency}/kWh`} color="#eda100" />
          </div>

          <Card>
            <SectionHeader
              icon={Receipt}
              title="Bill of Quantities (BOQ)"
              subtitle="Costs in EUR, sourced from the workbook's Annex-VII wind economics. Standard rows: qty x unit cost. Wind Turbine(s) & Battery System: system size (from System Design's Wind+Battery tab) x lumpsum rate — edit that rate directly on the row."
              color={color}
            />
            <div className="mb-4">
              <FileUpload
                downloadPath="/api/financials-wind-battery/template"
                downloadFilename="Wind_Battery_Cost_BOQ_Template.xlsx"
                uploadPath="/api/financials-wind-battery/upload"
                uploadLabel="Upload Filled Template"
                onUploaded={(r) => {
                  setBoqItems(r.boqItems);
                  setLandCostOptions(r.landCostOptions);
                  setCostParameters(r.costParameters);
                }}
              />
            </div>
            <EditableTable
              columns={[
                { key: "item_no", label: "S No.", type: "readonly", width: 55 },
                { key: "description", label: "Description", type: "readonly" },
                { key: "qty", label: "Qty", type: "number", width: 90, disabled: (row) => SYSTEM_SCALED.has(row.description), format: blankDash },
                { key: "unit", label: "Unit", type: "text", width: 80, disabled: (row) => SYSTEM_SCALED.has(row.description), format: blankDash },
                { key: "unit_cost_eur", label: "Unit Cost (EUR)", type: "number", width: 120, disabled: (row) => SYSTEM_SCALED.has(row.description), format: blankDash },
                { key: "system_unit", label: "System Unit", type: "text", width: 100, disabled: (row) => !SYSTEM_SCALED.has(row.description), format: blankDash },
                { key: "lumpsum_unit_cost_eur", label: "Lumpsum Cost / Unit (EUR)", type: "number", width: 150, disabled: (row) => !SYSTEM_SCALED.has(row.description), format: blankDash },
                { key: "total_cost_eur", label: "Total Cost (EUR)", type: "readonly", width: 140, format: (v) => fmtNumber(v, 2) },
              ]}
              rows={displayBoqRows}
              onChange={setBoqItems}
            />
          </Card>

          <Card>
            <SectionHeader icon={MapPinned} title="Land Cost Options" subtitle="Which approach is actually used is chosen by the land_cost_approach parameter below — shared with the other scenarios" color={color} />
            <EditableTable
              columns={[
                { key: "approach", label: "Approach", type: "readonly", width: 140 },
                { key: "description", label: "Description", type: "text" },
                { key: "acres", label: "Acres", type: "number", width: 90 },
                { key: "total_cost_eur", label: "Total Cost (EUR)", type: "number", width: 150 },
              ]}
              rows={landCostOptions}
              onChange={setLandCostOptions}
            />
          </Card>

          <Card>
            <SectionHeader icon={Sliders} title="Cost Parameters" color={color} />
            <div className="overflow-x-auto rounded-xl border border-ink-100">
              <table className="w-full min-w-[640px] border-collapse text-sm">
                <thead>
                  <tr className="bg-ink-50/80">
                    <th className="whitespace-nowrap border-b border-ink-100 px-3 py-2.5 text-left text-xs font-semibold uppercase tracking-wide text-ink-500">Parameter</th>
                    <th className="whitespace-nowrap border-b border-ink-100 px-3 py-2.5 text-left text-xs font-semibold uppercase tracking-wide text-ink-500" style={{ width: 190 }}>Value</th>
                    <th className="whitespace-nowrap border-b border-ink-100 px-3 py-2.5 text-left text-xs font-semibold uppercase tracking-wide text-ink-500" style={{ width: 140 }}>Unit</th>
                    <th className="whitespace-nowrap border-b border-ink-100 px-3 py-2.5 text-left text-xs font-semibold uppercase tracking-wide text-ink-500">Description</th>
                  </tr>
                </thead>
                <tbody>
                  {costParameters.map((row, i) => (
                    <tr key={row.parameter} className={i % 2 === 1 ? "bg-ink-50/30" : ""}>
                      <td className="border-b border-ink-50 px-3 py-2 font-medium text-ink-700">{humanizeParam(row.parameter)}</td>
                      <td className="border-b border-ink-50 px-3 py-2">
                        {row.parameter === "land_cost_approach" ? (
                          <select
                            value={row.value}
                            onChange={(e) => updateParam(row.parameter, e.target.value)}
                            className="w-full cursor-pointer rounded-lg border border-ink-200 bg-white px-2 py-1"
                          >
                            {LAND_APPROACHES.map((a) => (
                              <option key={a} value={a}>
                                {a}
                              </option>
                            ))}
                          </select>
                        ) : row.parameter === "use_lump_sum_capex" ? (
                          <select
                            value={row.value}
                            onChange={(e) => updateParam(row.parameter, Number(e.target.value))}
                            className="w-full cursor-pointer rounded-lg border border-ink-200 bg-white px-2 py-1"
                          >
                            <option value={0}>0 — use itemized BOQ</option>
                            <option value={1}>1 — use lump sum below</option>
                          </select>
                        ) : (
                          <input
                            type="number"
                            step="any"
                            value={row.value}
                            onChange={(e) => updateParam(row.parameter, e.target.value === "" ? "" : Number(e.target.value))}
                            className="w-full rounded-lg border border-ink-200 bg-white px-2 py-1 text-right text-xs tabular-nums"
                          />
                        )}
                      </td>
                      <td className="border-b border-ink-50 px-3 py-2 text-ink-500">{row.unit}</td>
                      <td className="border-b border-ink-50 px-3 py-2 text-ink-500">{row.description}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          <Card padded={false} className="overflow-hidden">
            <EChart option={convertedBoqItems ? boqCostBreakdownPieChart(convertedBoqItems, currency) : {}} height={400} loading={!result} />
          </Card>

          <div className="flex items-center justify-end gap-3 pb-4">
            {computing && <span className="text-xs text-ink-400">Recalculating…</span>}
            <Button onClick={handleSave} loading={saving}>
              Save Financials
            </Button>
          </div>
        </>
      )}
    </div>
  );
}
