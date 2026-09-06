import { useState } from "react";
import { PageHeader } from "../components/Card";
import Tabs from "../components/Tabs";
import { stepByPath } from "../lib/steps";
import FinancialsBattery from "./financials/FinancialsBattery";
import FinancialsDiesel from "./financials/FinancialsDiesel";

const step = stepByPath("/financials");
const SYSTEM_TYPES = [
  { value: "battery", label: "Solar PV with Battery System" },
  { value: "diesel", label: "Solar PV with Diesel Generator" },
];

export default function Financials() {
  const [systemType, setSystemType] = useState("battery");

  return (
    <div className="space-y-6">
      <PageHeader image={step.image} title={step.title} subtitle={step.description} color={step.color} />

      <Tabs options={SYSTEM_TYPES} value={systemType} onChange={setSystemType} />

      {systemType === "battery" ? <FinancialsBattery color={step.color} /> : <FinancialsDiesel color={step.color} />}
    </div>
  );
}
