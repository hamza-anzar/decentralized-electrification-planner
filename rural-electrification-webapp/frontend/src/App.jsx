import { lazy, Suspense } from "react";
import { Routes, Route } from "react-router-dom";
import Layout from "./components/Layout";
import { ProgressProvider } from "./context/ProgressContext";
import Landing from "./pages/Landing";
import StepPlaceholder from "./pages/StepPlaceholder";
import { STEPS } from "./lib/steps";

// Each step page pulls in Apache ECharts option builders — lazy-loading them keeps the initial bundle
// (and the landing page's time-to-interactive) small, splitting the heavier pages into their own chunks.
const LoadSetup = lazy(() => import("./pages/LoadSetup"));
const DemandProfile = lazy(() => import("./pages/DemandProfile"));
const EnergyInsights = lazy(() => import("./pages/EnergyInsights"));
const SystemDesign = lazy(() => import("./pages/SystemDesign"));
const Financials = lazy(() => import("./pages/Financials"));
const Results = lazy(() => import("./pages/Results"));

const BUILT_PAGES = {
  loadSetup: LoadSetup,
  demandProfile: DemandProfile,
  energyInsights: EnergyInsights,
  solarDesign: SystemDesign,
  financials: Financials,
  results: Results,
};

function PageFallback() {
  return <div className="py-24 text-center text-sm text-ink-400">Loading…</div>;
}

export default function App() {
  return (
    <ProgressProvider>
      <Layout>
        <Suspense fallback={<PageFallback />}>
          <Routes>
            <Route path="/" element={<Landing />} />
            {STEPS.map((step) => {
              const Page = BUILT_PAGES[step.key];
              return (
                <Route
                  key={step.key}
                  path={step.path}
                  element={Page ? <Page /> : <StepPlaceholder step={step} />}
                />
              );
            })}
          </Routes>
        </Suspense>
      </Layout>
    </ProgressProvider>
  );
}
