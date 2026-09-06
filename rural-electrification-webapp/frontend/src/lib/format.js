// Number/unit/currency formatting shared across pages — mirrors the conversion logic in
// backend/core/charts.py and cost_lcoe.py so the frontend never re-derives a formula, only formats.

const WH_DIVISORS = { kWh: 1_000, MWh: 1_000_000, TWh: 1_000_000_000 };

export function convertWh(valueWh, unit) {
  return valueWh / WH_DIVISORS[unit];
}

export function fmtNumber(value, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return value.toLocaleString(undefined, { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

export function fmtInt(value) {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return Math.round(value).toLocaleString();
}

export function fmtCompact(value, digits = 1) {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return value.toLocaleString(undefined, { notation: "compact", maximumFractionDigits: digits });
}

const COMPACT_WORD_UNITS = [
  [1_000_000_000, "Billion"],
  [1_000_000, "Million"],
  [1_000, "Thousand"],
];

// Spelled-out compact form ("2.1 Million") rather than Intl's abbreviated "2.1M" — used for the
// large money/energy KPIs on the Results page.
export function fmtCompactWords(value, digits = 1) {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  const abs = Math.abs(value);
  for (const [threshold, word] of COMPACT_WORD_UNITS) {
    if (abs >= threshold) return `${fmtNumber(value / threshold, digits)} ${word}`;
  }
  return fmtNumber(value, digits);
}

// EUR is the app's base currency everywhere. eurToPkr / eurToUsd are the stored exchange rates
// (from default_cost_parameters.csv) — this mirrors backend core/cost_lcoe.py's convert_currency().
export function convertCurrency(eurValue, currency, eurToPkr, eurToUsd) {
  if (currency === "EUR") return eurValue;
  if (currency === "PKR") return eurValue * eurToPkr;
  if (currency === "USD") return eurValue * eurToUsd;
  return eurValue;
}

export function fmtCurrency(eurValue, currency, eurToPkr, eurToUsd, digits = 0) {
  const v = convertCurrency(eurValue, currency, eurToPkr, eurToUsd);
  return `${fmtNumber(v, digits)} ${currency}`;
}

export function fmtHours(h) {
  if (h === null || h === undefined) return "—";
  return `${fmtInt(h)} h/yr`;
}

export function fmtYears(y, fallbackLabel = "yr") {
  if (y === null || y === undefined) return `never (30${fallbackLabel})`;
  return `${fmtNumber(y, 1)} yr`;
}

export const MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
