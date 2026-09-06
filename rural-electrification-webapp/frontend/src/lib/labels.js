// Human-readable labels for the raw snake_case `parameter` keys used in Cost Parameters, PV
// Parameters, and ROI Parameters tables (backend/data keep the snake_case names — this is display-only).
export const PARAM_LABELS = {
  // Cost parameters
  land_cost_approach: "Land Cost Approach",
  insurance_pct_per_year: "Insurance (%/year)",
  om_eur_per_kw_per_year: "O&M Cost",
  eur_to_pkr_rate: "EUR to PKR Rate",
  eur_to_usd_rate: "EUR to USD Rate",
  inflation_rate: "Inflation Rate",
  discount_rate: "Discount Rate",
  inverter_replacement_pct: "Inverter Replacement (%)",
  project_lifetime_years: "Project Lifetime",
  use_lump_sum_capex: "Use Lump-Sum Capital Cost",
  lump_sum_capex_eur: "Lump-Sum Capital Cost",
  // PV parameters
  performance_ratio_Q: "Performance Ratio",
  reference_irradiance_iqc_kwm2: "Reference Irradiance (STC)",
  ppeak_w: "PV Array Size (Ppeak)",
  battery_dod: "Battery Depth of Discharge",
  battery_quality_factor: "Battery Quality Factor",
  // ROI parameters
  electricity_tariff_eur_per_kwh: "Electricity Tariff",
  revenue_escalation_rate: "Revenue Escalation Rate",
  replacement_year: "Replacement Year",
  annual_load_growth_pct: "Annual Load Growth",
  // Diesel generator parameters
  generator_unit_size_kw: "Generator Unit Size",
  generator_count: "Number of Generators",
  capacity_margin_pct: "Sizing Safety Margin",
  rounding_increment_kw: "Rounding Increment",
  fuel_consumption_l_per_kwh: "Fuel Consumption",
  fuel_price_eur_per_liter: "Fuel Price",
  // Diesel cost parameters
  generator_overhaul_pct: "Generator Overhaul Cost (%)",
  // BOQ columns (used as table headers, not parameter rows, but kept here for one shared lookup)
  qty: "Qty",
  unit_cost_eur: "Unit Cost (EUR)",
  system_unit: "System Unit",
  lumpsum_unit_cost_eur: "Lumpsum Cost (per System Unit)",
};

// Fallback for any parameter not in the map above: snake_case -> Title Case.
export function humanizeParam(key) {
  if (PARAM_LABELS[key]) return PARAM_LABELS[key];
  return key
    .split("_")
    .map((w) => (w.length ? w[0].toUpperCase() + w.slice(1) : w))
    .join(" ");
}
