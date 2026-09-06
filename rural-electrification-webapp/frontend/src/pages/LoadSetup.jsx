import { useEffect, useMemo, useRef, useState } from "react";
import { Home, Users, Zap, MapPin, PlugZap, Building2 } from "lucide-react";
import { Card, SectionHeader, PageHeader } from "../components/Card";
import { Field, TextInput, NumberInput } from "../components/Field";
import EditableTable from "../components/Table";
import Tabs from "../components/Tabs";
import KpiCard from "../components/KpiCard";
import Button from "../components/Button";
import Alert from "../components/Alert";
import EChart from "../components/EChart";
import { useApiGet } from "../hooks/useApi";
import { useProgress } from "../context/ProgressContext";
import { api } from "../api/client";
import { stepByPath } from "../lib/steps";
import { applyTotalHousesSplit } from "../lib/split";
import { fmtInt, fmtNumber } from "../lib/format";
import { householdSplitPieChart, connectedLoadByCategoryChart, topContributorsChart } from "../lib/charts";

const step = stepByPath("/load-setup");

const SITE_FIELDS = [
  { key: "project_name", label: "Project name", type: "text" },
  { key: "country", label: "Country", type: "text" },
  { key: "region_city_village", label: "City / village / region", type: "text" },
  { key: "latitude", label: "Latitude", type: "number", step: "0.001", suffix: "°N" },
  { key: "longitude", label: "Longitude", type: "number", step: "0.001", suffix: "°E" },
  { key: "population", label: "Population", type: "number", suffix: "people" },
  { key: "area_km2", label: "Site area", type: "number", step: "0.01", suffix: "km²" },
  { key: "weather_type", label: "Weather type", type: "text" },
  { key: "socioeconomic_class", label: "Socio-economic class", type: "text" },
  { key: "gdp_per_capita_usd", label: "GDP per capita", type: "number", suffix: "USD/yr" },
  { key: "electrification_pct", label: "Pre-project electrification", type: "number", step: "0.1", suffix: "%" },
];

let rowKeySeq = 0;
const withKey = (row) => ({ __key: `r${rowKeySeq++}`, ...row });

export default function LoadSetup() {
  const { data: defaults, error: defaultsError } = useApiGet("/api/load-setup/defaults");
  const { data: siteDefaults, error: siteDefaultsError } = useApiGet("/api/site-info");
  const loadError = defaultsError || siteDefaultsError;
  const { refetchProgress } = useProgress();

  const [siteInfo, setSiteInfo] = useState(null);
  const [totalHouses, setTotalHouses] = useState(null);
  const [categoriesBase, setCategoriesBase] = useState(null); // [{category, label, area_sqm, pct_split}]
  const [appliances, setAppliances] = useState(null);
  const [miscLoads, setMiscLoads] = useState(null);
  const [applianceCategory, setApplianceCategory] = useState("A");

  const [result, setResult] = useState(null);
  const [computing, setComputing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [saved, setSaved] = useState(false);

  const initialized = useRef(false);

  // Seed local editable state once from the two default-loading fetches.
  useEffect(() => {
    if (initialized.current || !defaults || !siteDefaults) return;
    initialized.current = true;
    setSiteInfo(siteDefaults);
    const total = defaults.householdCategories.reduce((a, c) => a + Number(c.household_count || 0), 0);
    setTotalHouses(total);
    setCategoriesBase(defaults.householdCategories.map((c) => withKey({ category: c.category, label: c.label, area_sqm: c.area_sqm, pct_split: c.pct_split })));
    setAppliances(defaults.appliances.map(withKey));
    setMiscLoads(defaults.miscLoads.map(withKey));
  }, [defaults, siteDefaults]);

  const householdCategories = useMemo(() => {
    if (!categoriesBase || totalHouses == null) return null;
    return applyTotalHousesSplit(categoriesBase, totalHouses);
  }, [categoriesBase, totalHouses]);

  const pctTotal = useMemo(() => (categoriesBase ? categoriesBase.reduce((a, c) => a + Number(c.pct_split || 0), 0) : 0), [categoriesBase]);

  // Appliances are filtered to the active category tab so the table doesn't repeat "A, A, A, B, B…" —
  // categoryIndices maps the visible (filtered) row positions back to their real index in `appliances`.
  const categoryIndices = useMemo(
    () => (appliances ? appliances.map((_, i) => i).filter((i) => appliances[i].category === applianceCategory) : []),
    [appliances, applianceCategory]
  );
  const visibleAppliances = useMemo(() => categoryIndices.map((i) => appliances[i]), [appliances, categoryIndices]);

  // Debounced recompute against the (fast, pure) backend pipeline whenever the inputs change.
  useEffect(() => {
    if (!householdCategories || !appliances || !miscLoads) return;
    setComputing(true);
    const handle = setTimeout(() => {
      api
        .post("/api/load-setup/compute", {
          householdCategories: householdCategories.map(({ __key, ...r }) => r),
          appliances: appliances.map(({ __key, ...r }) => r),
          miscLoads: miscLoads.map(({ __key, ...r }) => r),
        })
        .then(setResult)
        .catch((e) => setError(e.message))
        .finally(() => setComputing(false));
    }, 350);
    return () => clearTimeout(handle);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [householdCategories, appliances, miscLoads]);

  async function handleSave() {
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      await api.post("/api/site-info", siteInfo);
      const r = await api.post("/api/load-setup/save", {
        householdCategories: householdCategories.map(({ __key, ...row }) => row),
        appliances: appliances.map(({ __key, ...row }) => row),
        miscLoads: miscLoads.map(({ __key, ...row }) => row),
      });
      setResult(r);
      setSaved(true);
      refetchProgress();
    } catch (e) {
      setError(e.message || String(e));
    } finally {
      setSaving(false);
    }
  }

  const ready = siteInfo && householdCategories && appliances && miscLoads;

  return (
    <div className="space-y-6">
      <PageHeader image={step.image} title={step.title} subtitle={step.description} color={step.color} />

      {error && <Alert type="error" onDismiss={() => setError(null)}>{error}</Alert>}
      {saved && <Alert type="success" onDismiss={() => setSaved(false)}>Load setup saved — the connected load figures now feed every later step.</Alert>}
      {loadError && <Alert type="error">Couldn't load Load Setup data from the server: {loadError}. Is the backend running at {import.meta.env.VITE_API_URL || "http://localhost:8000"}?</Alert>}

      {!ready ? (
        <Card className="py-16 text-center text-sm text-ink-400">{loadError ? "Couldn't load — see the error above." : "Loading load setup…"}</Card>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <KpiCard icon={Zap} label="Connected Load" value={result ? result.total_w / 1_000_000 : null} decimals={3} suffix=" MW" color={step.color} />
            <KpiCard icon={Home} label="Total Households" value={totalHouses} decimals={0} color="#2a78d6" />
            <KpiCard icon={Users} label="Population" value={Number(siteInfo.population) || 0} decimals={0} color="#1baf7a" />
            <KpiCard icon={Building2} label="Community Loads" value={miscLoads.length} decimals={0} sublabel="hospital, school, street lights…" color="#eda100" />
          </div>

          <Card>
            <SectionHeader icon={MapPin} title="Site & Location" subtitle="Context fields — not used in the load calculation itself" color={step.color} />
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {SITE_FIELDS.map((f) => (
                <Field key={f.key} label={f.label}>
                  {f.type === "number" ? (
                    <div className="relative">
                      <NumberInput
                        step={f.step ?? "1"}
                        value={siteInfo[f.key] ?? ""}
                        onChange={(e) => setSiteInfo({ ...siteInfo, [f.key]: e.target.value === "" ? "" : Number(e.target.value) })}
                        className={f.suffix ? "pr-16" : ""}
                      />
                      {f.suffix && <span className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-xs text-ink-400">{f.suffix}</span>}
                    </div>
                  ) : (
                    <TextInput value={siteInfo[f.key] ?? ""} onChange={(e) => setSiteInfo({ ...siteInfo, [f.key]: e.target.value })} />
                  )}
                </Field>
              ))}
            </div>
          </Card>

          <Card>
            <SectionHeader icon={Home} title="Household Categories" subtitle="Household counts are computed live from the total and each category's % split" color={step.color} />
            <div className="mb-4 flex flex-wrap items-end gap-4">
              <Field label="Total number of houses" className="w-48">
                <NumberInput value={totalHouses} onChange={(e) => setTotalHouses(Number(e.target.value) || 0)} />
              </Field>
              <p className={clsxPct(pctTotal)}>% split total: {fmtNumber(pctTotal, 1)}%{pctTotal !== 100 && " — should add up to 100%"}</p>
            </div>
            <EditableTable
              columns={[
                { key: "category", label: "Category", type: "readonly", width: 100 },
                { key: "label", label: "Description", type: "text" },
                { key: "area_sqm", label: "Living Area (sqm)", type: "number", width: 130 },
                { key: "pct_split", label: "% Split", type: "number", step: "0.1", width: 110 },
                { key: "household_count", label: "Households", type: "readonly", width: 120, format: (v) => fmtInt(v) },
              ]}
              rows={householdCategories}
              onChange={(next) => setCategoriesBase(next.map(({ household_count, ...r }) => r))}
            />
          </Card>

          <Card>
            <SectionHeader icon={PlugZap} title="Appliances per Household" subtitle="Pick a category, then edit its appliance list — power, quantity per house, and any notes" color={step.color} />
            <div className="mb-4">
              <Tabs options={["A", "B", "C"]} value={applianceCategory} onChange={setApplianceCategory} />
            </div>
            <EditableTable
              columns={[
                { key: "appliance", label: "Appliance", type: "text" },
                { key: "power_w", label: "Power (W)", type: "number", width: 110 },
                { key: "qty_per_house", label: "Qty / house", type: "number", width: 110 },
                { key: "comment", label: "Comment", type: "text" },
              ]}
              rows={visibleAppliances}
              onChange={(nextVisible) => {
                const next = [...appliances];
                nextVisible.forEach((row, idx) => { next[categoryIndices[idx]] = row; });
                setAppliances(next);
              }}
              onRemoveRow={(i) => setAppliances(appliances.filter((_, idx) => idx !== categoryIndices[i]))}
              onAddRow={() => setAppliances([...appliances, withKey({ category: applianceCategory, appliance: "New appliance", power_w: 0, qty_per_house: 1, comment: "" })])}
              addLabel="Add appliance"
            />
          </Card>

          <Card>
            <SectionHeader icon={Building2} title="Community / Misc Loads" subtitle="Shared community infrastructure — hospital, school, street lighting, etc." color={step.color} />
            <EditableTable
              columns={[
                { key: "appliance", label: "Load", type: "text" },
                { key: "power_w", label: "Power (W)", type: "number", width: 110 },
                { key: "qty", label: "Qty", type: "number", width: 90 },
                { key: "comment", label: "Comment", type: "text" },
              ]}
              rows={miscLoads}
              onChange={setMiscLoads}
              onRemoveRow={(i) => setMiscLoads(miscLoads.filter((_, idx) => idx !== i))}
              onAddRow={() => setMiscLoads([...miscLoads, withKey({ appliance: "New load", power_w: 0, qty: 1, comment: "" })])}
              addLabel="Add community load"
            />
          </Card>

          <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
            <Card padded={false} className="overflow-hidden">
              <EChart option={result ? householdSplitPieChart(householdCategories) : {}} height={320} loading={!result} />
            </Card>
            <Card padded={false} className="overflow-hidden">
              <EChart option={result ? connectedLoadByCategoryChart(result.by_category) : {}} height={320} loading={!result} />
            </Card>
          </div>
          <Card padded={false} className="overflow-hidden">
            <EChart option={result ? topContributorsChart(result.lines, 10) : {}} height={420} loading={!result} />
          </Card>

          <div className="flex items-center justify-end gap-3 pb-4">
            {computing && <span className="text-xs text-ink-400">Recalculating…</span>}
            <Button onClick={handleSave} loading={saving} icon={undefined}>
              Save Load Setup
            </Button>
          </div>
        </>
      )}
    </div>
  );
}

function clsxPct(pctTotal) {
  return `text-xs font-semibold ${pctTotal === 100 ? "text-leaf" : "text-coral"}`;
}
