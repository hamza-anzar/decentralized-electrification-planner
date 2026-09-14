import { useState } from "react";
import { PageHeader } from "../components/Card";
import Tabs from "../components/Tabs";
import { stepByPath } from "../lib/steps";
import FinancialsBattery from "./financials/FinancialsBattery";
import FinancialsDiesel from "./financials/FinancialsDiesel";
import FinancialsWindBattery from "./financials/FinancialsWindBattery";
import FinancialsWindDiesel from "./financials/FinancialsWindDiesel";

const step = stepByPath("/financials");
const SYSTEM_TYPES = [
  { value: "battery", label: "Solar PV with Battery System" },
  { value: "diesel", label: "Solar PV with Diesel Generator" },
  { value: "wind_battery", label: "Wind Turbine with Battery System" },
  { value: "wind_diesel", label: "Wind Turbine with Diesel Generator" },
];

const PAGES = {
  battery: FinancialsBattery,
  diesel: FinancialsDiesel,
  wind_battery: FinancialsWindBattery,
  wind_diesel: FinancialsWindDiesel,
};

export default function Financials() {
  const [systemType, setSystemType] = useState("battery");
  const Page = PAGES[systemType];

  return (
    <div className="space-y-6">
      <PageHeader image={step.image} title={step.title} subtitle={step.description} color={step.color} />

      <Tabs options={SYSTEM_TYPES} value={systemType} onChange={setSystemType} />

      <Page color={step.color} />
    </div>
  );
}
