import { useEffect, useRef, useState } from "react";
import { Wind, BatteryCharging, TimerOff, Settings2, Satellite, Waves, Wand2, SlidersHorizontal, BarChart3 } from "lucide-react";
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
import { batterySensitivityChart, egenVsDemandChart, windSpeedVsDemandChart, windSpeedHistogramChart, duckCurveChart } from "../../lib/charts";

const SOURCES = [
  { value: "default", label: "Default (bundled dataset)" },
  { value: "nasa_power", label: "NASA POWER (live, needs internet)" },
  { value: "upload", label: "Upload your own power curve" },
];

const CUSTOM = "custom";

export default function WindBattery({ color }) {
  const { data: defaults, error: loadError } = useApiGet("/api/wind-design/defaults");
  const { refetchProgress } = useProgress();

  const [lat, setLat] = useState(null);
  const [lon, setLon] = useState(null);
  const [source, setSource] = useState("default");
  const [windSpeed, setWindSpeed] = useState(null);
  const [windSpeedSource, setWindSpeedSource] = useState("default (bundled)");
  const [turbineLibrary, setTurbineLibrary] = useState(null);
  const [windParameters, setWindParameters] = useState(null);
  const [powerCurve, setPowerCurve] = useState(null); // only set when the selected model is "custom"
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
  const [windDays, setWindDays] = useState(7);
  const [duckMode, setDuckMode] = useState("Annual average");
  const [duckDay, setDuckDay] = useState(172);

  const [recommended, setRecommended] = useState(null);

  const initialized = useRef(false);
  useEffect(() => {
    if (initialized.current || !defaults) return;
    initialized.current = true;
    setLat(defaults.lat);
    setLon(defaults.lon);
    setWindSpeed(defaults.windSpeed);
    setTurbineLibrary(defaults.turbineLibrary);
    setWindParameters(defaults.windParameters);
  }, [defaults]);

  const selectedModel = windParameters?.find((r) => r.parameter === "turbine_model")?.value ?? null;
  const isCustom = selectedModel === CUSTOM;

  function handleModelChange(model) {
    setWindParameters(windParameters.map((r) => (r.parameter === "turbine_model" ? { ...r, value: model } : r)));
    if (model !== CUSTOM) setPowerCurve(null);
  }

  // Best-effort: only available once Load Setup + Demand Profile have been saved. Silently skipped otherwise.
  useEffect(() => {
    if (!windParameters || (isCustom && !powerCurve)) return;
    api
      .post("/api/wind-design/recommended-turbine-count", { windParameters, powerCurve: isCustom ? powerCurve : null, windSpeed })
      .then(setRecommended)
      .catch(() => setRecommended(null));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [windParameters, windSpeed]);

  function handleUseRecommended() {
    if (!recommended || !windParameters) return;
    setWindParameters(windParameters.map((r) => (r.parameter === "turbine_count" ? { ...r, value: recommended.recommended_count } : r)));
  }

  const readyToCompute = windParameters && windSpeed && (!isCustom || powerCurve);

  useEffect(() => {
    if (!readyToCompute) return;
    setComputing(true);
    const handle = setTimeout(() => {
      api
        .post("/api/wind-design/compute", {
          windParameters, windSpeed, powerCurve: isCustom ? powerCurve : null,
          manualBatteryKwh: useManualBattery ? manualBatteryKwh : null,
        })
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
  }, [readyToCompute, windParameters, windSpeed, powerCurve, useManualBattery, manualBatteryKwh]);

  async function handleFetch() {
    setFetching(true);
    setFetchWarnings([]);
    try {
      const r = await api.post("/api/wind-design/fetch-resource", { lat: Number(lat), lon: Number(lon), source });
      setWindSpeed(r.windSpeed);
      setWindSpeedSource(r.sourceUsed);
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
      const r = await api.post("/api/wind-design/save", {
        windParameters, windSpeed, powerCurve: isCustom ? powerCurve : null,
        manualBatteryKwh: useManualBattery ? manualBatteryKwh : null,
      });
      setResult(r);
      setSaved(true);
      refetchProgress();
    } catch (e) {
      setError(e.detail?.errors?.join(" ") || e.message || String(e));
    } finally {
      setSaving(false);
    }
  }

  const ready = windParameters && windSpeed && turbineLibrary;
  const r = result?.results;
  const numericParamRows = windParameters ? windParameters.filter((row) => row.parameter !== "turbine_model") : null;

  function updateNumericRows(updatedRows) {
    const turbineRow = windParameters.find((row) => row.parameter === "turbine_model");
    setWindParameters([turbineRow, ...updatedRows]);
  }

  return (
    <div className="space-y-6">
      {error && <Alert type="error" onDismiss={() => setError(null)}>{error}</Alert>}
      {saved && <Alert type="success" onDismiss={() => setSaved(false)}>Wind+Battery design saved — Financials and Results now use this turbine/battery sizing.</Alert>}
      {loadError && <Alert type="error">Couldn't load Wind Design data from the server: {loadError}. Is the backend running at {import.meta.env.VITE_API_URL || "http://localhost:8000"}?</Alert>}
      {fetchWarnings.map((w, i) => (
        <Alert key={i} type="error">{w}</Alert>
      ))}

      {!ready ? (
        <Card className="py-16 text-center text-sm text-ink-400">{loadError ? "Couldn't load — see the error above." : "Loading wind design…"}</Card>
      ) : (
        <>
          <Card>
            <SectionHeader icon={Satellite} title="1. Wind Resource (Site Wind Speed, 10m Reference Height)" color={color} />
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <Field label="Latitude">
                <NumberInput step="0.001" value={lat} onChange={(e) => setLat(e.target.value)} />
              </Field>
              <Field label="Longitude">
                <NumberInput step="0.001" value={lon} onChange={(e) => setLon(e.target.value)} />
              </Field>
              <Field label="Source">
                <Select value={source} onChange={(e) => setSource(e.target.value)}>
                  {SOURCES.filter((s) => s.value !== "upload").map((s) => (
                    <option key={s.value} value={s.value}>{s.label}</option>
                  ))}
                </Select>
              </Field>
            </div>
            <div className="mt-4 flex items-center gap-3">
              <Button variant="secondary" onClick={handleFetch} loading={fetching}>
                Fetch / Use This Source
              </Button>
              <p className="text-xs text-ink-400">
                Current source: <span className="font-semibold text-ink-600">{windSpeedSource}</span>. The bundled default is
                extracted directly from your workbook's Annex-V. NASA POWER needs outbound internet access — this falls back
                to the bundled dataset if unreachable.
              </p>
            </div>
          </Card>

          <Card>
            <SectionHeader icon={Settings2} title="2. Turbine Selection & Wind Parameters" color={color} />
            {recommended && (
              <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-brand-100 bg-brand-50/50 px-4 py-3">
                <p className="text-sm text-ink-700">
                  <strong>Recommended: {recommended.recommended_count} turbine(s)</strong> — the smallest count whose annual
                  generation ({fmtNumber(recommended.annual_single_turbine_wh / 1e9, 4)} GWh/turbine/year) meets or exceeds
                  annual demand ({fmtNumber(recommended.annual_demand_wh / 1e9, 4)} GWh/year). Always manually overridable.
                </p>
                <Button variant="secondary" icon={Wand2} onClick={handleUseRecommended}>
                  Use Recommended Count
                </Button>
              </div>
            )}
            <div className="mb-4">
              <Field label="Turbine Model" className="max-w-lg">
                <Select value={selectedModel ?? ""} onChange={(e) => handleModelChange(e.target.value)}>
                  {turbineLibrary.map((t) => (
                    <option key={t.model} value={t.model}>
                      {t.company} {t.model} — {fmtNumber(t.rated_power_kw, 0)} kW, {fmtNumber(t.hub_height_m, 0)} m hub, IEC {t.iec_class}
                    </option>
                  ))}
                  <option value={CUSTOM}>Custom — upload your own power curve</option>
                </Select>
              </Field>
            </div>
            {isCustom && (
              <div className="mb-4">
                <FileUpload
                  downloadPath="/api/wind-design/curve-template"
                  downloadFilename="Custom_Wind_Turbine_Curve_Template.xlsx"
                  uploadPath="/api/wind-design/curve-upload"
                  uploadLabel="Upload & Use"
                  onUploaded={(res) => setPowerCurve(res.powerCurve)}
                />
                <p className="mt-2 text-xs text-ink-400">
                  {powerCurve
                    ? `Custom curve loaded: ${powerCurve.length} points, rated ${fmtNumber(Math.max(...powerCurve.map((p) => p.power_kw)), 0)} kW.`
                    : "Upload a filled-in power curve (m/s vs kW) to use a turbine that isn't in the library."}
                </p>
              </div>
            )}
            <EditableTable
              columns={[
                { key: "parameter", label: "Parameter", type: "readonly", format: (v) => humanizeParam(v) },
                { key: "value", label: "Value", type: "number", width: 130 },
                { key: "unit", label: "Unit", type: "readonly", width: 140 },
                { key: "description", label: "Description", type: "readonly" },
              ]}
              rows={numericParamRows}
              onChange={updateNumericRows}
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
            <SectionHeader title="Formulas Used for Wind Generation & Battery Sizing" color={color} />
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
              <Formula
                title="Wind shear (hub-height correction)"
                expression="v(hub) = v(ref) × (h_hub / h_ref) ^ α"
                legend="v(ref) = wind speed at the reference height (10m) · h_hub = turbine hub height · α = wind shear exponent (0.14 typical for open/coastal terrain). Raw reference-height wind speed against the hub understates real yield."
                color={color}
              />
              <Formula
                title="Turbine hourly generation (Egen)"
                expression="Eɡₑₙ = PowerCurve( v(hub) ) × TurbineCount"
                legend="Linear interpolation of the selected turbine's own power curve (0.5 m/s bins) at each hour's shear-corrected wind speed. Zero below cut-in and above cut-out."
                color="#7a5cd6"
              />
              <Formula
                title="Battery capacity from the worst deficit block"
                expression="Battery(kWh) = MROUND( (−SDEworst/1000) / DoD × QF, 1000 )"
                legend="Same battery-sizing methodology as Solar+Battery — SDEworst = worst deficit block's summed shortfall (Wh) · DoD = max depth of discharge · QF = battery quality/derating factor. Overridden entirely if you enter a custom size above."
                color="#eb6834"
              />
            </div>
          </Card>

          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <KpiCard icon={Wind} label="Annual Generation" value={r ? r.annual_egen_wh / 1e9 : null} decimals={4} suffix=" GWh" color="#eda100" />
            <KpiCard icon={Wind} label="Installed Turbine Capacity" value={r ? r.installed_capacity_kw : null} decimals={0} suffix=" kW" color="#7a5cd6" />
            <KpiCard icon={BatteryCharging} label="Battery Capacity" value={r ? r.battery_capacity_kwh : null} decimals={0} suffix=" kWh" color="#2a78d6" />
            <KpiCard icon={TimerOff} label="Zero-Yield Hours" value={r ? r.zero_yield_hours : null} decimals={0} suffix=" h/yr" color="#eb6834" />
          </div>

          <Card>
            <SectionHeader icon={BarChart3} title="Wind Speed Frequency Distribution" subtitle="Hours per year at each wind speed (0.5 m/s bins, at hub height) — the Weibull-style histogram used for turbine-selection decision making" color={color} />
            <EChart option={result ? windSpeedHistogramChart(result.simulation) : {}} height={340} loading={!result} />
          </Card>

          <Card>
            <SectionHeader icon={BatteryCharging} title="Battery Size Sensitivity" subtitle="Zero-yield hours for candidate battery sizes, with the currently sized battery marked" color={color} />
            <EChart option={result ? batterySensitivityChart(result.sensitivity, r.battery_capacity_kwh, r.zero_yield_hours) : {}} height={380} loading={!result} />
          </Card>

          <Card>
            <SectionHeader title="Demand vs. Generation vs. Battery SOC (One Week)" color={color} />
            <Field label={`Week starting day ${weekStart}`} className="mb-3 max-w-md">
              <input type="range" min={1} max={359} value={weekStart} onChange={(e) => setWeekStart(Number(e.target.value))} className="h-2 w-full cursor-pointer appearance-none rounded-full bg-ink-100 accent-brand-500" />
            </Field>
            <EChart option={result ? egenVsDemandChart(result.simulation, weekStart, "Wind Generation") : {}} height={380} loading={!result} />
          </Card>

          <Card>
            <SectionHeader title="Hourly Wind Speed vs. Demand Profile" color={color} />
            <Field label={`Number of days shown: ${windDays}`} className="mb-3 max-w-md">
              <input type="range" min={1} max={14} value={windDays} onChange={(e) => setWindDays(Number(e.target.value))} className="h-2 w-full cursor-pointer appearance-none rounded-full bg-ink-100 accent-brand-500" />
            </Field>
            <EChart option={result ? windSpeedVsDemandChart(result.simulation, weekStart, windDays) : {}} height={380} loading={!result} />
          </Card>

          <Card>
            <SectionHeader icon={Waves} title="Duck Curve" subtitle="Net load = Demand − Wind Generation" color={color} />
            <div className="mb-3 flex flex-wrap items-center gap-4">
              <Tabs options={["Annual average", "A specific day"]} value={duckMode} onChange={setDuckMode} />
              {duckMode === "A specific day" && (
                <Field label={`Day of year: ${duckDay}`} className="max-w-md flex-1">
                  <input type="range" min={1} max={365} value={duckDay} onChange={(e) => setDuckDay(Number(e.target.value))} className="h-2 w-full cursor-pointer appearance-none rounded-full bg-ink-100 accent-brand-500" />
                </Field>
              )}
            </div>
            <EChart option={result ? duckCurveChart(result.simulation, duckMode === "A specific day" ? duckDay : null, "Wind Generation") : {}} height={380} loading={!result} />
          </Card>

          <div className="flex items-center justify-end gap-3 pb-4">
            {computing && <span className="text-xs text-ink-400">Recalculating…</span>}
            <Button onClick={handleSave} loading={saving}>
              Save Wind+Battery Design
            </Button>
          </div>
        </>
      )}
    </div>
  );
}
