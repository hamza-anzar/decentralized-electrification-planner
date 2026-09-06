import { useEffect, useRef, useState } from "react";
import { Sun, BatteryCharging, TimerOff, Settings2, Satellite, Waves, Wand2, SlidersHorizontal } from "lucide-react";
import { Card, SectionHeader } from "../../components/Card";
import { Field, NumberInput, Select } from "../../components/Field";
import EditableTable from "../../components/Table";
import KpiCard from "../../components/KpiCard";
import Button from "../../components/Button";
import Alert from "../../components/Alert";
import EChart from "../../components/EChart";
import Formula from "../../components/Formula";
import Tabs from "../../components/Tabs";
import FileUpload from "../../components/FileUpload";
import { useApiGet } from "../../hooks/useApi";
import { useProgress } from "../../context/ProgressContext";
import { api } from "../../api/client";
import { humanizeParam } from "../../lib/labels";
import { fmtNumber } from "../../lib/format";
import { batterySensitivityChart, egenVsDemandChart, irradianceVsDemandChart, duckCurveChart } from "../../lib/charts";

const SOURCES = [
  { value: "default", label: "Default (bundled dataset)" },
  { value: "pvgis", label: "PVGIS (live, needs internet)" },
  { value: "nasa_power", label: "NASA POWER (live, needs internet)" },
  { value: "upload", label: "Upload your own (.xlsx)" },
];

export default function SolarBattery({ color }) {
  const { data: defaults, error: loadError } = useApiGet("/api/solar-design/defaults");
  const { refetchProgress } = useProgress();

  const [lat, setLat] = useState(null);
  const [lon, setLon] = useState(null);
  const [source, setSource] = useState("default");
  const [irradiance, setIrradiance] = useState(null);
  const [irradianceSource, setIrradianceSource] = useState("default (bundled)");
  const [pvParameters, setPvParameters] = useState(null);
  const [fetching, setFetching] = useState(false);
  const [fetchWarnings, setFetchWarnings] = useState([]);

  const [useManualBattery, setUseManualBattery] = useState(false);
  const [manualBatteryKwh, setManualBatteryKwh] = useState(null);

  const [result, setResult] = useState(null);
  const [computing, setComputing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [saved, setSaved] = useState(false);

  const [weekStart, setWeekStart] = useState(1);
  const [irrDays, setIrrDays] = useState(7);
  const [duckMode, setDuckMode] = useState("Annual average");
  const [duckDay, setDuckDay] = useState(172);

  const [recommended, setRecommended] = useState(null);

  const initialized = useRef(false);
  useEffect(() => {
    if (initialized.current || !defaults) return;
    initialized.current = true;
    setLat(defaults.lat);
    setLon(defaults.lon);
    setIrradiance(defaults.irradiance);
    setPvParameters(defaults.pvParameters);
  }, [defaults]);

  // Best-effort: only available once Load Setup + Demand Profile have been saved. Silently skipped otherwise.
  useEffect(() => {
    api.get("/api/solar-design/recommended-size").then(setRecommended).catch(() => setRecommended(null));
  }, []);

  function handleUseRecommended() {
    if (!recommended || !pvParameters) return;
    setPvParameters(pvParameters.map((r) => (r.parameter === "ppeak_w" ? { ...r, value: recommended.recommended_ppeak_w } : r)));
  }

  useEffect(() => {
    if (!irradiance || !pvParameters) return;
    setComputing(true);
    const handle = setTimeout(() => {
      api
        .post("/api/solar-design/compute", { pvParameters, irradiance, manualBatteryKwh: useManualBattery ? manualBatteryKwh : null })
        .then((r) => {
          setResult(r);
          setError(null);
          if (!useManualBattery) setManualBatteryKwh(r.results.battery_capacity_kwh);
        })
        .catch((e) => setError(e.detail?.errors?.join(" ") || e.message))
        .finally(() => setComputing(false));
    }, 400);
    return () => clearTimeout(handle);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [irradiance, pvParameters, useManualBattery, manualBatteryKwh]);

  async function handleFetch() {
    setFetching(true);
    setFetchWarnings([]);
    try {
      const r = await api.post("/api/solar-design/fetch-resource", { lat: Number(lat), lon: Number(lon), source });
      setIrradiance(r.irradiance);
      setIrradianceSource(r.sourceUsed);
      setFetchWarnings(r.errors || []);
    } catch (e) {
      setError(e.message || String(e));
    } finally {
      setFetching(false);
    }
  }

  async function handleSave() {
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      const r = await api.post("/api/solar-design/save", { pvParameters, irradiance, manualBatteryKwh: useManualBattery ? manualBatteryKwh : null });
      setResult(r);
      setSaved(true);
      refetchProgress();
    } catch (e) {
      setError(e.detail?.errors?.join(" ") || e.message || String(e));
    } finally {
      setSaving(false);
    }
  }

  const ready = pvParameters && irradiance;
  const r = result?.results;

  return (
    <div className="space-y-6">
      {error && <Alert type="error" onDismiss={() => setError(null)}>{error}</Alert>}
      {saved && <Alert type="success" onDismiss={() => setSaved(false)}>Solar+Battery design saved — Financials and Results now use this PV/battery sizing.</Alert>}
      {loadError && <Alert type="error">Couldn't load Solar Design data from the server: {loadError}. Is the backend running at {import.meta.env.VITE_API_URL || "http://localhost:8000"}?</Alert>}
      {fetchWarnings.map((w, i) => (
        <Alert key={i} type="error">{w}</Alert>
      ))}

      {!ready ? (
        <Card className="py-16 text-center text-sm text-ink-400">{loadError ? "Couldn't load — see the error above." : "Loading solar design…"}</Card>
      ) : (
        <>
          <Card>
            <SectionHeader icon={Satellite} title="1. Solar Resource (Site Irradiance)" color={color} />
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <Field label="Latitude">
                <NumberInput step="0.001" value={lat} onChange={(e) => setLat(e.target.value)} />
              </Field>
              <Field label="Longitude">
                <NumberInput step="0.001" value={lon} onChange={(e) => setLon(e.target.value)} />
              </Field>
              <Field label="Source">
                <Select value={source} onChange={(e) => setSource(e.target.value)}>
                  {SOURCES.map((s) => (
                    <option key={s.value} value={s.value}>
                      {s.label}
                    </option>
                  ))}
                </Select>
              </Field>
            </div>
            {source === "upload" ? (
              <div className="mt-4">
                <FileUpload
                  downloadPath="/api/solar-design/irradiance-template"
                  downloadFilename="Irradiance_Template.xlsx"
                  uploadPath="/api/solar-design/irradiance-upload"
                  uploadLabel="Upload & Use"
                  onUploaded={(r) => {
                    setIrradiance(r.irradiance);
                    setIrradianceSource(r.sourceUsed);
                  }}
                />
                <p className="mt-2 text-xs text-ink-400">
                  Current source: <span className="font-semibold text-ink-600">{irradianceSource}</span>.
                </p>
              </div>
            ) : (
              <div className="mt-4 flex items-center gap-3">
                <Button variant="secondary" onClick={handleFetch} loading={fetching}>
                  Fetch / Use This Source
                </Button>
                <p className="text-xs text-ink-400">
                  Current source: <span className="font-semibold text-ink-600">{irradianceSource}</span>. PVGIS/NASA POWER need
                  outbound internet access — this falls back to the bundled dataset if unreachable.
                </p>
              </div>
            )}
          </Card>

          <Card>
            <SectionHeader icon={Settings2} title="2. PV System Parameters" color={color} />
            {recommended && (
              <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-brand-100 bg-brand-50/50 px-4 py-3">
                <p className="text-sm text-ink-700">
                  <strong>Recommended size: {fmtNumber(recommended.recommended_ppeak_w / 1e6, 3)} MW</strong> — sized to
                  cover your highest recorded hourly demand ({fmtNumber(recommended.peak_demand_w / 1e6, 3)} MW) at peak
                  sun, derated by the performance ratio. Your theoretical max connected load
                  ({fmtNumber(recommended.connected_load_w / 1e6, 3)} MW, everything running at once) is shown for
                  reference only — it isn't used for sizing.
                </p>
                <Button variant="secondary" icon={Wand2} onClick={handleUseRecommended}>
                  Use Recommended Size
                </Button>
              </div>
            )}
            <EditableTable
              columns={[
                { key: "parameter", label: "Parameter", type: "readonly", format: (v) => humanizeParam(v) },
                { key: "value", label: "Value", type: "number", width: 130 },
                { key: "unit", label: "Unit", type: "readonly", width: 140 },
                { key: "description", label: "Description", type: "readonly" },
              ]}
              rows={pvParameters}
              onChange={setPvParameters}
            />
          </Card>

          <Card>
            <SectionHeader icon={SlidersHorizontal} title="3. Battery Size" subtitle="Auto-sized from the worst deficit block by default — or enter your own" color={color} />
            <div className="flex flex-wrap items-end gap-4">
              <label className="flex items-center gap-2 text-sm font-medium text-ink-700">
                <input
                  type="checkbox"
                  checked={useManualBattery}
                  onChange={(e) => {
                    setUseManualBattery(e.target.checked);
                    if (e.target.checked && r) setManualBatteryKwh(r.battery_capacity_kwh);
                  }}
                  className="h-4 w-4 rounded accent-brand-500"
                />
                Use a custom battery size
              </label>
              {useManualBattery && (
                <Field label="Battery capacity (kWh)" className="w-52">
                  <NumberInput step="100" value={manualBatteryKwh ?? ""} onChange={(e) => setManualBatteryKwh(e.target.value === "" ? "" : Number(e.target.value))} />
                </Field>
              )}
              {r && (
                <p className="text-xs text-ink-400">
                  Auto-calculated size: <strong>{fmtNumber(r.auto_battery_capacity_kwh, 0)} kWh</strong>
                  {useManualBattery ? " (currently overridden above)" : " (currently in use)"}.
                </p>
              )}
            </div>
          </Card>

          <Card>
            <SectionHeader title="Formulas Used for PV Generation & Battery Sizing" color={color} />
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
              <Formula
                title="PV hourly generation (Egen)"
                expression="Eɡₑₙ = Pₚₑₐₖ × [G(i) / 1000] × Q / Iqc"
                legend="Ppeak = PV array nameplate capacity (W) · G(i) = hourly global irradiance (W/m²) · Q = performance ratio · Iqc = reference (STC) irradiance (kW/m²)."
                color={color}
              />
              <Formula
                title="Hourly generation-minus-demand imbalance"
                expression="ΔEₕ = Eɡₑₙ,ₕ − Demandₕ"
                legend="Consecutive hours with the same sign of ΔE are grouped into one block; the block with the most negative sum is the worst (longest/deepest) deficit run of the year."
                color="#eb6834"
              />
              <Formula
                title="Battery capacity from the worst deficit block"
                expression="Battery(kWh) = MROUND( (−SDEworst/1000) / DoD × QF, 1000 )"
                legend="SDEworst = worst block's summed deficit (Wh, negative) · DoD = max depth of discharge · QF = battery quality/derating factor · MROUND rounds to the nearest 1,000 kWh. Overridden entirely if you enter a custom size above."
                color="#7a5cd6"
              />
            </div>
          </Card>

          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            <KpiCard icon={Sun} label="Annual Generation" value={r ? r.annual_egen_wh / 1e9 : null} decimals={4} suffix=" GWh" color="#eda100" />
            <KpiCard icon={BatteryCharging} label="Battery Capacity" value={r ? r.battery_capacity_kwh : null} decimals={0} suffix=" kWh" color="#2a78d6" />
            <KpiCard icon={TimerOff} label="Zero-Yield Hours" value={r ? r.zero_yield_hours : null} decimals={0} suffix=" h/yr" color="#eb6834" />
          </div>

          <Card>
            <SectionHeader icon={BatteryCharging} title="Battery Size Sensitivity" subtitle="Zero-yield hours for candidate battery sizes, with the currently sized battery marked" color={color} />
            <EChart option={result ? batterySensitivityChart(result.sensitivity, r.battery_capacity_kwh, r.zero_yield_hours) : {}} height={380} loading={!result} />
          </Card>

          <Card>
            <SectionHeader title="Demand vs. Generation vs. Battery SOC (One Week)" color={color} />
            <Field label={`Week starting day ${weekStart}`} className="mb-3 max-w-md">
              <input type="range" min={1} max={359} value={weekStart} onChange={(e) => setWeekStart(Number(e.target.value))} className="h-2 w-full cursor-pointer appearance-none rounded-full bg-ink-100 accent-brand-500" />
            </Field>
            <EChart option={result ? egenVsDemandChart(result.simulation, weekStart) : {}} height={380} loading={!result} />
          </Card>

          <Card>
            <SectionHeader title="Hourly Irradiance vs. Demand Profile" color={color} />
            <Field label={`Number of days shown: ${irrDays}`} className="mb-3 max-w-md">
              <input type="range" min={1} max={14} value={irrDays} onChange={(e) => setIrrDays(Number(e.target.value))} className="h-2 w-full cursor-pointer appearance-none rounded-full bg-ink-100 accent-brand-500" />
            </Field>
            <EChart option={result ? irradianceVsDemandChart(result.simulation, weekStart, irrDays) : {}} height={380} loading={!result} />
          </Card>

          <Card>
            <SectionHeader icon={Waves} title="Duck Curve" subtitle="Net load = Demand − PV Generation" color={color} />
            <div className="mb-3 flex flex-wrap items-center gap-4">
              <Tabs options={["Annual average", "A specific day"]} value={duckMode} onChange={setDuckMode} />
              {duckMode === "A specific day" && (
                <Field label={`Day of year: ${duckDay}`} className="max-w-md flex-1">
                  <input type="range" min={1} max={365} value={duckDay} onChange={(e) => setDuckDay(Number(e.target.value))} className="h-2 w-full cursor-pointer appearance-none rounded-full bg-ink-100 accent-brand-500" />
                </Field>
              )}
            </div>
            <EChart option={result ? duckCurveChart(result.simulation, duckMode === "A specific day" ? duckDay : null) : {}} height={380} loading={!result} />
            <p className="mt-2 text-xs text-ink-400">
              The midday dip is PV generation offsetting demand; the steep evening ramp is demand staying up while the sun sets — the
              classic "duck curve" shape that drives battery-sizing needs.
            </p>
          </Card>

          <div className="flex items-center justify-end gap-3 pb-4">
            {computing && <span className="text-xs text-ink-400">Recalculating…</span>}
            <Button onClick={handleSave} loading={saving}>
              Save Solar+Battery Design
            </Button>
          </div>
        </>
      )}
    </div>
  );
}
