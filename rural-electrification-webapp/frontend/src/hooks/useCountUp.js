import { useEffect, useRef, useState } from "react";
import { fmtCompactWords } from "../lib/format";

// Animates a number from its previous value to a new one whenever `value` changes — powers the
// "animated KPI cards" requirement without pulling in a full animation library.
export default function useCountUp(value, { duration = 700, decimals = 0, compact = false, compactWords = false } = {}) {
  const [display, setDisplay] = useState(value ?? 0);
  const fromRef = useRef(value ?? 0);
  const rafRef = useRef(null);

  useEffect(() => {
    if (value === null || value === undefined || Number.isNaN(value)) {
      setDisplay(null);
      return;
    }
    const from = fromRef.current ?? 0;
    const to = value;
    const start = performance.now();

    cancelAnimationFrame(rafRef.current);
    function tick(now) {
      const t = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - t, 3);
      const current = from + (to - from) * eased;
      setDisplay(current);
      if (t < 1) {
        rafRef.current = requestAnimationFrame(tick);
      } else {
        fromRef.current = to;
      }
    }
    rafRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafRef.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value, duration]);

  if (display === null) return "—";
  if (compactWords) return fmtCompactWords(display, 2);
  if (compact) return display.toLocaleString(undefined, { notation: "compact", maximumFractionDigits: 2 });
  return display.toLocaleString(undefined, { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}
