import { useEffect, useRef, useState } from "react";
import { Wind, Fuel, TimerOff, Settings2, Satellite, Zap, Wand2, BarChart3 } from "lucide-react";
import { Card, SectionHeader } from "../../components/Card";
import { Field, NumberInput, Select } from "../../components/Field";
import EditableTable from "../../components/Table";
import KpiCard from "../../components/KpiCard";
import Button from "../../components/Button";
import Alert from "../../components/Alert";
import EChart from "../../components/EChart";
import Formula from "../../components/Formula";
import FileUpload from "../../components/FileUpload";
import { useApiGet } from "../../hooks/useApi";
import { useProgress } from "../../context/ProgressContext";
import { api } from "../../api/client";
import { humanizeParam } from "../../lib/labels";
import { fmtNumber } from "../../lib/format";
import { windSpeedVsDemandChart, windSpeedHistogramChart, duckCurveChart, generatorDispatchChart, deficitLoadDurationChart } from "../../lib/charts";

const CUSTOM = "custom";

export default function WindDiesel({ color }) {
  // Wind speed & turbine library are site/catalogue data, shared with Wind+Battery — same endpoints, independent client state.
  const { data: windDefaults, error: windLoadError } = useApiGet("/api/wind-design/defaults");
  const { data: dieselDefaults, error: loadError } = useApiGet("/api/wind-diesel-design/defaults");
  const { refetchProgress } = useProgress();

  const [lat, setLat] = useState(null);
  const [lon, setLon] = useState(null);
  const [source, setSource] = useState("default");
  const [windSpeed, setWindSpeed] = useState(null);
  const [windSpeedSource, setWindSpeedSource] = useState("default (bundled)");
  const [fetching, setFetching] = useState(false);
  const [fetchWarnings, setFetchWarnings] = useState([]);

  const [turbineLibrary, setTurbineLibrary] = useState(null);
  const [windParameters, setWindParameters] = useState(null);
  const [generatorParameters, setGeneratorParameters] = useState(null);
  const [powerCurve, setPowerCurve] = useState(null);

  const [result, setResult] = useState(null);
  const [computing, setComputing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [saved, setSaved] = useState(false);

  const [weekStart, setWeekStart] = useState(1);
  const [windDays, setWindDays] = useState(7);

  const [recommended, setRecommended] = useState(null);

  const initialized = useRef(false);
  useEffect(() => {
    if (initialized.current || !windDefaults || !dieselDefaults) return;
    initialized.current = true;
    setLat(windDefaults.lat);
    setLon(windDefaults.lon);
    setWindSpeed(windDefaults.windSpeed);
    setTurbineLibrary(dieselDefaults.turbineLibrary || windDefaults.turbineLibrary);
    setWindParameters(dieselDefaults.windParameters);
    setGeneratorParameters(dieselDefaults.generatorParameters);
  }, [windDefaults, dieselDefaults]);

  const selectedModel = windParameters?.find((r) => r.parameter === "turbine_model")?.value ?? null;
  const isCustom = selectedModel === CUSTOM;

  function handleModelChange(model) {
    setWindParameters(windParameters.map((r) => (r.parameter === "turbine_model" ? { ...r, value: model } : r)));
    if (model !== CUSTOM) setPowerCurve(null);
  }

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

  function handleUseRecommendedGenerator() {
    if (!result?.results || !generatorParameters) return;
    const recKw = result.results.recommended_generator_kw;
    setGeneratorParameters(
      generatorParameters.map((row) => {
        if (row.parameter === "generator_unit_size_kw") return { ...row, value: recKw };
        if (row.parameter === "generator_count") return { ...row, value: 1 };
        return row;
      })
    );
  }

  const readyToCompute = windParameters && generatorParameters && windSpeed && (!isCustom || powerCurve);

  useEffect(() => {
    if (!readyToCompute) return;
    setComputing(true);
    const handle = setTimeout(() => {
      api
        .post("/api/wind-diesel-design/compute", { windParameters, generatorParameters, windSpeed, powerCurve: isCustom ? powerCurve : null })
        .then((r) => {
          setResult(r);
          setError(null);
        })
        .catch((e) => setError(e.detail?.errors?.join(" ") || e.message))
        .finally(() => setComputing(false));
    }, 400);
    return () => clearTimeout(handle);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [readyToCompute, windParameters, generatorParameters, windSpeed, powerCurve]);

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
      const r = await api.post("/api/wind-diesel-design/save", { windParameters, generatorParameters, windSpeed, powerCurve: isCustom ? powerCurve : null });
      setResult(r);
      setSaved(true);
      refetchProgress();
    } catch (e) {
      setError(e.detail?.errors?.join(" ") || e.message || String(e));
    } finally {
      setSaving(false);
    }
  }

  const ready = windParameters && generatorParameters && windSpeed && turbineLibrary;
  const r = result?.results;
  const loadError_ = loadError || windLoadError;
  const installedBelowRequired = r && r.installed_capacity_kw < r.recommended_generator_kw;
  const numericParamRows = windParameters ? windParameters.filter((row) => row.parameter !== "turbine_model") : null;

  function updateNumericRows(updatedRows) {
    const turbineRow = windParameters.find((row) => row.parameter === "turbine_model");
    setWindParameters([turbineRow, ...updatedRows]);
  }

  return (
    <div className="space-y-6">
      {error && <Alert type="error" onDismiss={() => setError(null)}>{error}</Alert>}
      {saved && <Alert type="success" onDismiss={() => setSaved(false)}>Wind+Diesel design saved — Financials and Results now use this turbine/generator sizing.</Alert>}
      {loadError_ && <Alert type="error">Couldn't load Wind+Diesel data from the server: {loadError_}. Is the backend running at {import.meta.env.VITE_API_URL || "http://localhost:8000"}?</Alert>}
      {fetchWarnings.map((w, i) => (
        <Alert key={i} type="error">{w}</Alert>
      ))}

      {!ready ? (
        <Card className="py-16 text-center text-sm text-ink-400">{loadError_ ? "Couldn't load — see the error above." : "Loading wind+diesel design…"}</Card>
      ) : (
        <>
          <Card>
            <SectionHeader icon={Satellite} title="1. Wind Resource (Site Wind Speed, 10m Reference Height)" subtitle="Shared with Wind+Battery — same site data" color={color} />
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <Field label="Latitude">
                <NumberInput step="0.001" value={lat} onChange={(e) => setLat(e.target.value)} />
              </Field>
              <Field label="Longitude">
                <NumberInput step="0.001" value={lon} onChange={(e) => setLon(e.target.value)} />
              </Field>
              <Field label="Source">
                <Select value={source} onChange={(e) => setSource(e.target.value)}>
                  <option value="default">Default (bundled dataset)</option>
                  <option value="nasa_power">NASA POWER (live, needs internet)</option>
                </Select>
              </Field>
            </div>
            <div className="mt-4 flex items-center gap-3">
              <Button variant="secondary" onClick={handleFetch} loading={fetching}>
                Fetch / Use This Source
              </Button>
              <p className="text-xs text-ink-400">
                Current source: <span className="font-semibold text-ink-600">{windSpeedSource}</span>.
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
                  annual demand ({fmtNumber(recommended.annual_demand_wh / 1e9, 4)} GWh/year). Any shortfall is covered by
                  the diesel generator below.
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
            <SectionHeader icon={Fuel} title="3. Diesel Generator Sizing" subtitle="Sized to cover the hours where wind alone can't meet demand" color={color} />
            {r && (
              <div className="mb-4 rounded-xl border border-brand-100 bg-brand-50/50 px-4 py-3">
                <p className="text-sm text-ink-700">
                  <strong>Recommended: {fmtNumber(r.recommended_generator_kw, 0)} kW total</strong> — your worst single-hour
                  shortfall was {fmtNumber(r.peak_deficit_w / 1000, 0)} kW, grossed up by a{" "}
                  {fmtNumber(generatorParameters.find((p) => p.parameter === "capacity_margin_pct")?.value, 0)}% safety margin
                  (for motor-starting inrush and to avoid running at 100% load continuously) and rounded up to the nearest{" "}
                  {fmtNumber(generatorParameters.find((p) => p.parameter === "rounding_increment_kw")?.value, 0)} kW.
                </p>
                <div className="mt-2 flex items-center justify-between gap-3">
                  <p className="text-xs text-ink-500">
                    Currently configured: {fmtNumber(r.generator_unit_size_kw, 0)} kW × {fmtNumber(r.generator_count, 0)} unit(s) ={" "}
                    <strong>{fmtNumber(r.installed_capacity_kw, 0)} kW installed</strong>.
                  </p>
                  <Button variant="secondary" icon={Wand2} onClick={handleUseRecommendedGenerator}>
                    Use Recommended (1 unit)
                  </Button>
                </div>
                {installedBelowRequired && (
                  <p className="mt-2 text-xs font-semibold text-coral">
                    Installed capacity is below the recommendation — {fmtNumber(r.unmet_hours, 0)} hour(s)/year of demand go
                    unserved at this configuration. Increase unit size or count below to close the gap, or accept the
                    unserved hours if that's an intentional trade-off.
                  </p>
                )}
              </div>
            )}
            <EditableTable
              columns={[
                { key: "parameter", label: "Parameter", type: "readonly", format: (v) => humanizeParam(v) },
                { key: "value", label: "Value", type: "number", width: 130 },
                { key: "unit", label: "Unit", type: "readonly", width: 140 },
                { key: "description", label: "Description", type: "readonly" },
              ]}
              rows={generatorParameters}
              onChange={setGeneratorParameters}
            />
            <p className="mt-3 text-xs text-ink-400">
              E.g. set "Generator Unit Size" to 1,000 and "Number of Generators" to 2 instead of one 2,000 kW unit.
            </p>
          </Card>

          <Card>
            <SectionHeader title="Formulas Used for Wind Generation & Generator Sizing" color={color} />
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
              <Formula
                title="Wind shear (hub-height correction)"
                expression="v(hub) = v(ref) × (h_hub / h_ref) ^ α"
                legend="v(ref) = wind speed at the reference height (10m) · h_hub = turbine hub height · α = wind shear exponent."
                color={color}
              />
              <Formula
                title="Hourly wind shortfall (deficit)"
                expression="Deficitₕ = max(0, Demandₕ − Eɡₑₙ,ₕ)"
                legend="Zero in any hour where wind generation already meets or exceeds demand."
                color="#eb6834"
              />
              <Formula
                title="Recommended generator size, rounded"
                expression="Recommended = CEIL( max(Deficitₕ) × (1+Margin%) / Step ) × Step"
                legend="Sized for the single worst hour of the year — same generator-sizing methodology as Solar+Diesel."
                color="#7a5cd6"
              />
            </div>
          </Card>

          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <KpiCard icon={Wind} label="Annual Wind Generation" value={r ? r.annual_egen_wh / 1e9 : null} decimals={4} suffix=" GWh" color="#eda100" />
            <KpiCard icon={Wind} label="Installed Turbine Capacity" value={r ? r.wind_installed_capacity_kw : null} decimals={0} suffix=" kW" color="#7a5cd6" />
            <KpiCard icon={Zap} label="Installed Generator Capacity" value={r ? r.installed_capacity_kw : null} decimals={0} suffix=" kW" color="#2a78d6" />
            <KpiCard icon={TimerOff} label="Unmet-Demand Hours" value={r ? r.unmet_hours : null} decimals={0} suffix=" h/yr" color="#eb6834" />
          </div>

          <Card>
            <SectionHeader icon={BarChart3} title="Wind Speed Frequency Distribution" subtitle="Hours per year at each wind speed (0.5 m/s bins, at hub height)" color={color} />
            <EChart option={result ? windSpeedHistogramChart(result.simulation) : {}} height={340} loading={!result} />
          </Card>

          <Card>
            <SectionHeader icon={Fuel} title="Deficit Load Duration Curve" subtitle="Hours of the year sorted by how much generator capacity they need — the standard genset-sizing view" color={color} />
            <EChart option={result ? deficitLoadDurationChart(result.loadDurationCurve, r.installed_capacity_kw, r.recommended_generator_kw, "Wind") : {}} height={380} loading={!result} />
          </Card>

          <Card>
            <SectionHeader title="Demand vs. Wind Generation vs. Generator Output (One Week)" color={color} />
            <Field label={`Week starting day ${weekStart}`} className="mb-3 max-w-md">
              <input type="range" min={1} max={359} value={weekStart} onChange={(e) => setWeekStart(Number(e.target.value))} className="h-2 w-full cursor-pointer appearance-none rounded-full bg-ink-100 accent-brand-500" />
            </Field>
            <EChart option={result ? generatorDispatchChart(result.simulation, weekStart, "Wind Generation") : {}} height={380} loading={!result} />
          </Card>

          <Card>
            <SectionHeader title="Hourly Wind Speed vs. Demand Profile" color={color} />
            <Field label={`Number of days shown: ${windDays}`} className="mb-3 max-w-md">
              <input type="range" min={1} max={14} value={windDays} onChange={(e) => setWindDays(Number(e.target.value))} className="h-2 w-full cursor-pointer appearance-none rounded-full bg-ink-100 accent-brand-500" />
            </Field>
            <EChart option={result ? windSpeedVsDemandChart(result.simulation, weekStart, windDays) : {}} height={380} loading={!result} />
          </Card>

          <Card>
            <SectionHeader title="Duck Curve" subtitle="Net load = Demand − Wind Generation" color={color} />
            <EChart option={result ? duckCurveChart(result.simulation, null, "Wind Generation") : {}} height={380} loading={!result} />
          </Card>

          <div className="flex items-center justify-end gap-3 pb-4">
            {computing && <span className="text-xs text-ink-400">Recalculating…</span>}
            <Button onClick={handleSave} loading={saving}>
              Save Wind+Diesel Design
            </Button>
          </div>
        </>
      )}
    </div>
  );
}
