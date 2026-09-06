# Rural Electrification Planner — Frontend

React + Vite single-page app for the Rural Electrification Planning project. See the project root's `README.md` for full run instructions (this frontend needs the `backend/` FastAPI server running alongside it).

## Stack

- **React 19** + **Vite** (SPA, `react-router-dom` for routing)
- **Tailwind CSS 3** for styling (custom theme in `tailwind.config.js` — reuses this project's established color palette: `brand` blue, `sun`, `leaf`, `coral`, `grape`, `blossom`)
- **Apache ECharts** via `echarts-for-react` for every chart (`src/lib/charts.js` builds the option objects)
- **Lucide React** for icons

## Structure

- `src/pages/` — one page per app step (Landing, LoadSetup, DemandProfile, EnergyInsights, SolarDesign, Financials, Results), lazy-loaded per route in `App.jsx`
- `src/components/` — shared UI (Card, KpiCard, Button, Field, EditableTable, Stepper, EChart wrapper, etc.)
- `src/lib/` — pure JS helpers ported from the backend's Python for client-side responsiveness: `charts.js` (ECharts option builders), `format.js` (number/currency formatting), `split.js` (household total/%-split math), `steps.js` (the 6-step flow's metadata)
- `src/api/client.js` — thin `fetch` wrapper for the backend REST API
- `src/context/ProgressContext.jsx` — shares `/api/progress` (which steps are saved) across the top stepper and the landing page

## Configuration

The backend URL defaults to `http://localhost:8000`. To point at a different backend, create a `.env.local` file here with:

```
VITE_API_URL=http://your-backend-host:port
```

## Commands

```
npm install       # first-time setup, and after pulling changes to package.json
npm run dev       # start the dev server (http://localhost:5173)
npm run build     # production build, output to dist/
```
