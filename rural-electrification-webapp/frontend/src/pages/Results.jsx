import { useState } from "react";
import { PageHeader } from "../components/Card";
import Disclaimer from "../components/Disclaimer";
import Tabs from "../components/Tabs";
import { stepByPath } from "../lib/steps";
import ResultsOverview from "./results/ResultsOverview";
import ResultsScenario from "./results/ResultsScenario";

const step = stepByPath("/results");
const VIEWS = [
  { value: "overview", label: "Overview" },
  { value: "battery", label: "Solar + Battery" },
  { value: "diesel", label: "Solar + Diesel" },
];

export default function Results() {
  const [view, setView] = useState("overview");

  return (
    <div className="space-y-6">
      <PageHeader image={step.image} title={step.title} subtitle={step.description} color={step.color} />
      <Disclaimer />

      <Tabs options={VIEWS} value={view} onChange={setView} />

      {view === "overview" && <ResultsOverview />}
      {view !== "overview" && <ResultsScenario key={view} systemType={view} color={step.color} />}
    </div>
  );
}
