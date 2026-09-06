// Port of backend/core/load_estimation.py's apply_total_houses_split() — largest-remainder rounding
// so household counts always sum exactly to the entered total, computed live as the user types
// (matches instantly in the UI without a round trip to the backend).
export function applyTotalHousesSplit(categories, totalHouses) {
  const raw = categories.map((c) => (Number(c.pct_split) / 100) * Number(totalHouses));
  const floors = raw.map((v) => Math.floor(v));
  const remainder = Math.round(totalHouses) - floors.reduce((a, b) => a + b, 0);

  const order = raw
    .map((v, i) => ({ i, frac: v - floors[i] }))
    .sort((a, b) => b.frac - a.frac);

  const counts = [...floors];
  for (let k = 0; k < Math.max(remainder, 0); k++) {
    counts[order[k].i] += 1;
  }

  return categories.map((c, i) => ({ ...c, household_count: counts[i] }));
}
