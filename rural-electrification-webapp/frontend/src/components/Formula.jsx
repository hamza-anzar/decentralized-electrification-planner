// A styled formula block — the non-Streamlit replacement for st.latex(), rendered with plain
// CSS/Unicode rather than a math-typesetting library (keeps the bundle dependency-free).
export default function Formula({ title, expression, legend, color = "#2a78d6" }) {
  return (
    <div className="rounded-2xl border border-ink-100 bg-ink-50/50 p-4">
      {title && <p className="mb-2 text-xs font-bold uppercase tracking-wide text-ink-500">{title}</p>}
      <p className="break-words rounded-xl bg-white px-4 py-3 font-display text-base font-bold italic leading-snug sm:text-lg" style={{ color }}>
        {expression}
      </p>
      {legend && <p className="mt-2 text-xs leading-relaxed text-ink-400">{legend}</p>}
    </div>
  );
}
