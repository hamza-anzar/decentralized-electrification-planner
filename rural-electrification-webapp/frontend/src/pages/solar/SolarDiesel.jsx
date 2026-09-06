import { useEffect, useRef, useState } from "react";
import { Sun, Fuel, TimerOff, Settings2, Satellite, Zap, Wand2 } from "lucide-react";
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
import { irradianceVsDemandChart, duckCurveChart, generatorDispatchChart, deficitLoadDurationChart } from "../../lib/charts";

const SOURCES = [
  { value: "default", label: "Default (bundled dataset)" },
  { value: "pvgis", label: "PVGIS (live, needs internet)" },
  { value: "nasa_power", label: "NASA POWER (live, needs internet)" },
  { value: "upload", label: "Upload your own (.xlsx)" },
];

export default function SolarDiesel({ color }) {
  // Irradiance is site data, shared with Solar+Battery — same endpoints, independent client state.
  const { data: siteDefaults, error: siteLoadError } = useApiGet("/api/solar-design/defaults");
  const { data: dieselDefaults, error: loadError } = useApiGet("/api/solar-diesel/defaults");
  const { refetchProgress } = useProgress();

  const [lat, setLat] = useState(null);
  const [lon, setLon] = useState(null);
  const [source, setSource] = useState("default");
  const [irradiance, setIrradiance] = useState(null);
  const [irradianceSource, setIrradianceSource] = useState("default (bundled)");
  const [fetching, setFetching] = useState(false);
  const [fetchWarnings, setFetchWarnings] = useState([]);

  const [pvParameters, setPvParameters] = useState(null);
  const [generatorParameters, setGeneratorParameters] = useState(null);

  const [result, setResult] = useState(null);
  const [computing, setComputing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [saved, setSaved] = useState(false);

  const [weekStart, setWeekStart] = useState(1);
  const [irrDays, setIrrDays] = useState(7);

  const [recommendedPpeak, setRecommendedPpeak] = useState(null);

  const initialized = useRef(false);
  useEffect(() => {
    if (initialized.current || !siteDefaults || !dieselDefaults) return;
    initialized.current = true;
    setLat(siteDefaults.lat);
    setLon(siteDefaults.lon);
    setIrradiance(siteDefaults.irradiance);
    setPvParameters(dieselDefaults.pvParameters);
    setGeneratorParameters(dieselDefaults.generatorParameters);
  }, [siteDefaults, dieselDefaults]);

  useEffect(() => {
    api.get("/api/solar-diesel/recommended-ppeak").then(setRecommendedPpeak).catch(() => setRecommendedPpeak(null));
  }, []);

  function handleUseRecommendedPpeak() {
    if (!recommendedPpeak || !pvParameters) return;
    setPvParameters(pvParameters.map((row) => (row.parameter === "ppeak_w" ? { ...row, value: recommendedPpeak.recommended_ppeak_w } : row)));
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

  useEffect(() => {
    if (!irradiance || !pvParameters || !generatorParameters) return;
    setComputing(true);
    const handle = setTimeout(() => {
      api
        .post("/api/solar-diesel/compute", { pvParameters, generatorParameters, irradiance })
        .then((r) => {
          setResult(r);
          setError(null);
        })
        .catch((e) => setError(e.detail?.errors?.join(" ") || e.message))
        .finally(() => setComputing(false));
    }, 400);
    return () => clearTimeout(handle);
  }, [irradiance, pvParameters, generatorParameters]);

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
      const r = await api.post("/api/solar-diesel/save", { pvParameters, generatorParameters, irradiance });
      setResult(r);
      setSaved(true);
      refetchProgress();
    } catch (e) {
      setError(e.detail?.errors?.join(" ") || e.message || String(e));
    } finally {
      setSaving(false);
    }
  }

  const ready = pvParameters && generatorParameters && irradiance;
  const r = result?.results;
  const loadError_ = loadError || siteLoadError;
  const installedBelowRequired = r && r.installed_capacity_kw < r.recommended_generator_kw;

  return (
    <div className="space-y-6">
      {error && <Alert type="error" onDismiss={() => setError(null)}>{error}</Alert>}
      {saved && <Alert type="success" onDismiss={() => setSaved(false)}>Solar+Diesel design saved — Financials and Results now use this PV/generator sizing.</Alert>}
      {loadError_ && <Alert type="error">Couldn't load Solar+Diesel data from the server: {loadError_}. Is the backend running at {import.meta.env.VITE_API_URL || "http://localhost:8000"}?</Alert>}
      {fetchWarnings.map((w, i) => (
        <Alert key={i} type="error">{w}</Alert>
      ))}

      {!ready ? (
        <Card className="py-16 text-center text-sm text-ink-400">{loadError_ ? "Couldn't load — see the error above." : "Loading solar+diesel design…"}</Card>
      ) : (
        <>
          <Card>
            <SectionHeader icon={Satellite} title="1. Solar Resource (Site Irradiance)" subtitle="Shared with Solar+Battery — same site data" color={color} />
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
              </div>
            ) : (
              <div className="mt-4 flex items-center gap-3">
                <Button variant="secondary" onClick={handleFetch} loading={fetching}>
                  Fetch / Use This Source
                </Button>
                <p className="text-xs text-ink-400">
                  Current source: <span className="font-semibold text-ink-600">{irradianceSource}</span>.
                </p>
              </div>
            )}
          </Card>

          <Card>
            <SectionHeader icon={Settings2} title="2. PV Array Size (No Battery)" color={color} />
            {recommendedPpeak && (
              <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-brand-100 bg-brand-50/50 px-4 py-3">
                <p className="text-sm text-ink-700">
                  <strong>Recommended size: {fmtNumber(recommendedPpeak.recommended_ppeak_w / 1e6, 3)} MW</strong> — sized to
                  track your average daytime demand ({fmtNumber(recommendedPpeak.avg_daytime_demand_w / 1e6, 3)} MW), since
                  without a battery any PV generation beyond instantaneous demand is curtailed (wasted).
                </p>
                <Button variant="secondary" icon={Wand2} onClick={handleUseRecommendedPpeak}>
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
            <SectionHeader icon={Fuel} title="3. Diesel Generator Sizing" subtitle="Sized to cover the hours where PV alone can't meet demand" color={color} />
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
            <SectionHeader title="Formulas Used for Generator Sizing" color={color} />
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
              <Formula
                title="Hourly PV shortfall (deficit)"
                expression="Deficitₕ = max(0, Demandₕ − Eɡₑₙ,ₕ)"
                legend="Zero in any hour where PV generation already meets or exceeds demand."
                color="#eb6834"
              />
              <Formula
                title="Required generator capacity"
                expression="Required = max(Deficitₕ) × (1 + Margin%)"
                legend="Sized for the single worst hour of the year, not the average — a generator that can't cover a peak causes brownouts. Margin covers motor-starting inrush and avoids continuous 100%-load running."
                color="#7a5cd6"
              />
              <Formula
                title="Recommended size, rounded"
                expression="Recommended = CEIL( Required / Step ) × Step"
                legend="Rounded UP (never down) to the nearest practical increment (e.g. 100 kW) — unlike battery sizing, under-sizing a generator directly causes brownouts."
                color={color}
              />
            </div>
          </Card>

          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <KpiCard icon={Sun} label="Annual PV Generation" value={r ? r.annual_egen_wh / 1e9 : null} decimals={4} suffix=" GWh" color="#eda100" />
            <KpiCard icon={Zap} label="Installed Generator Capacity" value={r ? r.installed_capacity_kw : null} decimals={0} suffix=" kW" color="#2a78d6" />
            <KpiCard icon={TimerOff} label="Unmet-Demand Hours" value={r ? r.unmet_hours : null} decimals={0} suffix=" h/yr" color="#eb6834" />
            <KpiCard icon={Fuel} label="Annual Fuel Cost" value={r ? r.annual_fuel_cost_eur : null} compact suffix=" EUR" color="#767468" />
          </div>

          <Card>
            <SectionHeader icon={Fuel} title="Deficit Load Duration Curve" subtitle="Hours of the year sorted by how much generator capacity they need — the standard genset-sizing view" color={color} />
            <EChart option={result ? deficitLoadDurationChart(result.loadDurationCurve, r.installed_capacity_kw, r.recommended_generator_kw) : {}} height={380} loading={!result} />
          </Card>

          <Card>
            <SectionHeader title="Demand vs. PV Generation vs. Generator Output (One Week)" color={color} />
            <Field label={`Week starting day ${weekStart}`} className="mb-3 max-w-md">
              <input type="range" min={1} max={359} value={weekStart} onChange={(e) => setWeekStart(Number(e.target.value))} className="h-2 w-full cursor-pointer appearance-none rounded-full bg-ink-100 accent-brand-500" />
            </Field>
            <EChart option={result ? generatorDispatchChart(result.simulation, weekStart) : {}} height={380} loading={!result} />
          </Card>

          <Card>
            <SectionHeader title="Hourly Irradiance vs. Demand Profile" color={color} />
            <Field label={`Number of days shown: ${irrDays}`} className="mb-3 max-w-md">
              <input type="range" min={1} max={14} value={irrDays} onChange={(e) => setIrrDays(Number(e.target.value))} className="h-2 w-full cursor-pointer appearance-none rounded-full bg-ink-100 accent-brand-500" />
            </Field>
            <EChart option={result ? irradianceVsDemandChart(result.simulation, weekStart, irrDays) : {}} height={380} loading={!result} />
          </Card>

          <Card>
            <SectionHeader title="Duck Curve" subtitle="Net load = Demand − PV Generation" color={color} />
            <EChart option={result ? duckCurveChart(result.simulation) : {}} height={380} loading={!result} />
          </Card>

          <div className="flex items-center justify-end gap-3 pb-4">
            {computing && <span className="text-xs text-ink-400">Recalculating…</span>}
            <Button onClick={handleSave} loading={saving}>
              Save Solar+Diesel Design
            </Button>
          </div>
        </>
      )}
    </div>
  );
}
