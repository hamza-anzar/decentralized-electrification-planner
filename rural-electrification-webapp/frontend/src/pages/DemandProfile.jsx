import { useEffect, useMemo, useRef, useState } from "react";
import { CalendarDays, PartyPopper, Flag, Grid3x3, Zap, UploadCloud, TrendingUp } from "lucide-react";
import { Card, SectionHeader, PageHeader } from "../components/Card";
import { Field, Select, NumberInput } from "../components/Field";
import EditableTable from "../components/Table";
import DayTypeGrid from "../components/DayTypeGrid";
import KpiCard from "../components/KpiCard";
import Button from "../components/Button";
import Alert from "../components/Alert";
import EChart from "../components/EChart";
import FileUpload from "../components/FileUpload";
import { useApiGet } from "../hooks/useApi";
import { useProgress } from "../context/ProgressContext";
import { api } from "../api/client";
import { stepByPath } from "../lib/steps";
import { fmtNumber } from "../lib/format";
import { yearlyOverviewChart, demandGrowthProjectionChart } from "../lib/charts";

const step = stepByPath("/demand-profile");

let rowKeySeq = 0;
const withKey = (row) => ({ __key: `dp${rowKeySeq++}`, ...row });
const strip = (rows) => rows.map(({ __key, ...r }) => r);

export default function DemandProfile() {
  const { data: defaults, error: defaultsError } = useApiGet("/api/demand-profile/defaults");
  const { data: loadSetup, error: loadSetupError } = useApiGet("/api/load-setup/defaults");
  const loadError = defaultsError || loadSetupError;
  const { refetchProgress } = useProgress();

  const [seasonPeriods, setSeasonPeriods] = useState(null);
  const [publicHolidays, setPublicHolidays] = useState(null);
  const [festivalHolidays, setFestivalHolidays] = useState(null);
  const [daytypeProfiles, setDaytypeProfiles] = useState(null);
  const [selectedDayType, setSelectedDayType] = useState(null);
  const [demandSettings, setDemandSettings] = useState(null); // {project_start_year, project_duration_years, annual_load_growth_pct}

  const [validationErrors, setValidationErrors] = useState([]);
  const [periodDayCounts, setPeriodDayCounts] = useState([]);
  const [result, setResult] = useState(null);
  const [computing, setComputing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [saved, setSaved] = useState(false);
  const [uploadedProfile, setUploadedProfile] = useState(null);

  const initialized = useRef(false);

  useEffect(() => {
    if (initialized.current || !defaults) return;
    initialized.current = true;
    setSeasonPeriods(defaults.seasonPeriods.map(withKey));
    setPublicHolidays(defaults.publicHolidays.map(withKey));
    setFestivalHolidays(defaults.festivalHolidays.map(withKey));
    setDaytypeProfiles(defaults.daytypeProfiles);
    setSelectedDayType(defaults.daytypeProfiles[0]?.day_type ?? null);
    setDemandSettings(defaults.demandSettings);
  }, [defaults]);

  const dayTypeOptions = useMemo(
    () => (daytypeProfiles ? [...new Set(daytypeProfiles.map((r) => r.day_type))] : []),
    [daytypeProfiles]
  );

  // Debounced validation of the season-period calendar (must cover all 365 days exactly once) — also
  // returns, per period, how many of its days are real weekdays vs. real weekends in the chosen year.
  useEffect(() => {
    if (!seasonPeriods || !demandSettings) return;
    const handle = setTimeout(() => {
      api
        .post("/api/demand-profile/validate", {
          seasonPeriods: strip(seasonPeriods),
          projectStartYear: demandSettings.project_start_year,
        })
        .then((r) => {
          setValidationErrors(r.errors || []);
          setPeriodDayCounts(r.periodDayCounts || []);
        })
        .catch(() => {});
    }, 400);
    return () => clearTimeout(handle);
  }, [seasonPeriods, demandSettings]);

  // Debounced full recompute — only once the calendar is valid and Load Setup data is available.
  useEffect(() => {
    if (!seasonPeriods || !publicHolidays || !festivalHolidays || !daytypeProfiles || !loadSetup || !demandSettings) return;
    if (validationErrors.length) {
      setResult(null);
      return;
    }
    setComputing(true);
    const handle = setTimeout(() => {
      api
        .post("/api/demand-profile/compute", {
          seasonPeriods: strip(seasonPeriods),
          publicHolidays: strip(publicHolidays),
          festivalHolidays: strip(festivalHolidays),
          daytypeProfiles,
          appliances: loadSetup.appliances,
          miscLoads: loadSetup.miscLoads,
          householdCategories: loadSetup.householdCategories,
          demandSettings,
        })
        .then(setResult)
        .catch((e) => setError(e.detail?.errors?.join(" ") || e.message))
        .finally(() => setComputing(false));
    }, 500);
    return () => clearTimeout(handle);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [seasonPeriods, publicHolidays, festivalHolidays, daytypeProfiles, loadSetup, demandSettings, validationErrors]);

  async function handleSave() {
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      const r = await api.post("/api/demand-profile/save", {
        seasonPeriods: strip(seasonPeriods),
        publicHolidays: strip(publicHolidays),
        festivalHolidays: strip(festivalHolidays),
        daytypeProfiles,
        appliances: loadSetup.appliances,
        miscLoads: loadSetup.miscLoads,
        householdCategories: loadSetup.householdCategories,
        demandSettings,
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

  const ready = seasonPeriods && publicHolidays && festivalHolidays && daytypeProfiles && loadSetup && demandSettings;
  const annualGwh = result ? result.annualWh / 1e9 : null;

  const seasonPeriodsWithCounts = useMemo(() => {
    if (!seasonPeriods) return seasonPeriods;
    const counts = new Map(periodDayCounts.map((r) => [r.period_name, r]));
    return seasonPeriods.map((r) => ({
      ...r,
      weekday_days: counts.get(r.period_name)?.weekday_days ?? "—",
      weekend_days: counts.get(r.period_name)?.weekend_days ?? "—",
    }));
  }, [seasonPeriods, periodDayCounts]);

  return (
    <div className="space-y-6">
      <PageHeader image={step.image} title={step.title} subtitle={step.description} color={step.color} />

      {error && <Alert type="error" onDismiss={() => setError(null)}>{error}</Alert>}
      {saved && <Alert type="success" onDismiss={() => setSaved(false)}>Demand profile saved — Energy Insights and Solar Design now use this 8,760-hour calendar.</Alert>}
      {loadError && <Alert type="error">Couldn't load Demand Profile data from the server: {loadError}. Is the backend running at {import.meta.env.VITE_API_URL || "http://localhost:8000"}?</Alert>}
      {uploadedProfile && (
        <Alert type="success" onDismiss={() => setUploadedProfile(null)}>
          Custom hourly profile in use — annual demand {fmtNumber(uploadedProfile.annualWh / 1e9, 4)} GWh, all
          seasonality/weekend/holiday tables below are ignored. Editing and saving those tables will overwrite it.
        </Alert>
      )}
      {!error && validationErrors.length > 0 && (
        <Alert type="error">
          <ul className="list-disc space-y-0.5 pl-4">
            {validationErrors.map((e, i) => (
              <li key={i}>{e}</li>
            ))}
          </ul>
        </Alert>
      )}

      {!ready ? (
        <Card className="py-16 text-center text-sm text-ink-400">{loadError ? "Couldn't load — see the error above." : "Loading demand profile…"}</Card>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            <KpiCard icon={Zap} label="Annual Demand" value={annualGwh} decimals={4} suffix=" GWh" color={step.color} />
            <KpiCard icon={CalendarDays} label="Season Periods" value={seasonPeriods.length} decimals={0} color="#2a78d6" />
            <KpiCard icon={Grid3x3} label="Day Types" value={dayTypeOptions.length} decimals={0} sublabel="usage patterns" color="#eda100" />
          </div>

          <Card>
            <SectionHeader
              icon={UploadCloud}
              title="Alternative: Upload a Full Hourly Profile"
              subtitle="Bypass season/day-type/calendar entirely — fill in your own 8,760-hour demand and use it directly"
              color={step.color}
            />
            <FileUpload
              downloadPath="/api/demand-profile/hourly-template"
              downloadFilename="Hourly_Load_Profile_Template.xlsx"
              uploadPath="/api/demand-profile/hourly-upload"
              uploadLabel="Upload & Use This Profile"
              onUploaded={(r) => {
                setUploadedProfile(r);
                setResult(r);
                refetchProgress();
              }}
            />
          </Card>

          <Card>
            <SectionHeader
              icon={CalendarDays}
              title="Season Periods"
              subtitle="Must cover all 365 days exactly once (MM-DD dates, no year) — weekday/weekend day-types are applied automatically to the real Saturdays/Sundays inside each period, not the whole period"
              color={step.color}
            />
            <div className="mb-4 flex flex-wrap items-end gap-4">
              <Field label="Project Start Year" className="w-40">
                <NumberInput
                  value={demandSettings.project_start_year}
                  onChange={(e) => setDemandSettings({ ...demandSettings, project_start_year: Number(e.target.value) || 2026 })}
                />
              </Field>
              <Field label="Project Duration (years)" className="w-48">
                <NumberInput
                  value={demandSettings.project_duration_years}
                  onChange={(e) => setDemandSettings({ ...demandSettings, project_duration_years: Number(e.target.value) || 1 })}
                />
              </Field>
              <p className="text-xs text-ink-400 max-w-xs">
                The calendar's weekday/weekend split (below) is calculated against the Project Start Year. Duration sets
                how many years the growth-projection chart at the bottom of this page covers.
              </p>
            </div>
            <EditableTable
              columns={[
                { key: "period_name", label: "Period", type: "text" },
                { key: "start_mmdd", label: "Start (MM-DD)", type: "text", width: 120 },
                { key: "end_mmdd", label: "End (MM-DD)", type: "text", width: 120 },
                { key: "weekday_daytype", label: "Weekday day-type", type: "select", options: dayTypeOptions, width: 180 },
                { key: "weekend_daytype", label: "Weekend day-type", type: "select", options: dayTypeOptions, width: 180 },
                { key: "weekday_days", label: "Weekday Days", type: "readonly", width: 110 },
                { key: "weekend_days", label: "Weekend Days", type: "readonly", width: 110 },
              ]}
              rows={seasonPeriodsWithCounts}
              onChange={(next) => setSeasonPeriods(next.map(({ weekday_days, weekend_days, ...r }) => r))}
              onRemoveRow={(i) => setSeasonPeriods(seasonPeriods.filter((_, idx) => idx !== i))}
              onAddRow={() => setSeasonPeriods([...seasonPeriods, withKey({ period_name: "New period", start_mmdd: "01-01", end_mmdd: "01-01", weekday_daytype: dayTypeOptions[0], weekend_daytype: dayTypeOptions[0] })])}
              addLabel="Add season period"
            />
            {!validationErrors.length && (
              <p className="mt-2 text-xs font-semibold text-leaf">
                Season periods cover all 365 days with no gaps or overlaps — see the Weekday/Weekend Days columns above
                to confirm only real weekend dates get the weekend day-type (e.g. a 31-day month has far fewer than 31
                weekend days).
              </p>
            )}
          </Card>

          <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
            <Card>
              <SectionHeader icon={Flag} title="Public Holidays" color="#7a5cd6" />
              <EditableTable
                columns={[
                  { key: "date_mmdd", label: "Date (MM-DD)", type: "text", width: 120 },
                  { key: "label", label: "Label", type: "text" },
                ]}
                rows={publicHolidays}
                onChange={setPublicHolidays}
                onRemoveRow={(i) => setPublicHolidays(publicHolidays.filter((_, idx) => idx !== i))}
                onAddRow={() => setPublicHolidays([...publicHolidays, withKey({ date_mmdd: "01-01", label: "Public Holiday" })])}
                addLabel="Add holiday"
              />
            </Card>
            <Card>
              <SectionHeader icon={PartyPopper} title="Festival Holidays" color="#eb6834" />
              <EditableTable
                columns={[
                  { key: "date_mmdd", label: "Date (MM-DD)", type: "text", width: 120 },
                  { key: "label", label: "Label", type: "text" },
                ]}
                rows={festivalHolidays}
                onChange={setFestivalHolidays}
                onRemoveRow={(i) => setFestivalHolidays(festivalHolidays.filter((_, idx) => idx !== i))}
                onAddRow={() => setFestivalHolidays([...festivalHolidays, withKey({ date_mmdd: "01-01", label: "Festival" })])}
                addLabel="Add festival"
              />
            </Card>
          </div>

          <Card>
            <SectionHeader icon={Grid3x3} title="Day-Type Usage Profiles" subtitle="How active each appliance is, hour by hour, for the selected day type (0 = off, 1 = fully on)" color={step.color} />
            <div className="mb-4 max-w-xs">
              <Field label="Day type">
                <Select value={selectedDayType} onChange={(e) => setSelectedDayType(e.target.value)}>
                  {dayTypeOptions.map((dt) => (
                    <option key={dt} value={dt}>
                      {dt}
                    </option>
                  ))}
                </Select>
              </Field>
            </div>
            <DayTypeGrid rows={daytypeProfiles} dayType={selectedDayType} onChange={setDaytypeProfiles} />
          </Card>

          <Card padded={false} className="overflow-hidden">
            <EChart option={result ? yearlyOverviewChart(result.hourlyProfile, "MWh") : {}} height={380} loading={!result} />
          </Card>

          <Card>
            <SectionHeader
              icon={TrendingUp}
              title="Load Growth Projection"
              subtitle="Energy(year n) = Energy(year 1) x (1 + g)^(n-1) — a compound annual growth rate applied to this year's total demand, projected across the project's full duration"
              color={step.color}
            />
            <div className="mb-4 flex flex-wrap items-end gap-4">
              <Field label="Annual Load Growth (%/year)" className="w-56">
                <NumberInput
                  step="0.1"
                  value={demandSettings.annual_load_growth_pct}
                  onChange={(e) => setDemandSettings({ ...demandSettings, annual_load_growth_pct: e.target.value === "" ? "" : Number(e.target.value) })}
                />
              </Field>
              <p className="text-xs text-ink-400 max-w-md">
                Depends on population growth, income/economic growth, an increasing connection rate, and productive-use
                uptake (new businesses, cold storage, agro-processing, etc. connecting over time). Typical mini-grid
                range is 3–8%/year; this projection is separate from the ROI cash-flow's own load-growth assumption on
                the Financials/Results steps.
              </p>
            </div>
            <EChart
              option={result ? demandGrowthProjectionChart(result.annualWh, demandSettings.project_start_year, demandSettings.project_duration_years, Number(demandSettings.annual_load_growth_pct) || 0) : {}}
              height={360}
              loading={!result}
            />
          </Card>

          <div className="flex items-center justify-end gap-3 pb-4">
            {computing && <span className="text-xs text-ink-400">Recalculating…</span>}
            <Button onClick={handleSave} loading={saving} disabled={validationErrors.length > 0}>
              Save Demand Profile
            </Button>
          </div>
        </>
      )}
    </div>
  );
}
