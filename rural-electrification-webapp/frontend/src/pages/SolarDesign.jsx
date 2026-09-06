import { useState } from "react";
import { PageHeader } from "../components/Card";
import Tabs from "../components/Tabs";
import { stepByPath } from "../lib/steps";
import SolarBattery from "./solar/SolarBattery";
import SolarDiesel from "./solar/SolarDiesel";

const step = stepByPath("/solar-design");
const SYSTEM_TYPES = [
  { value: "battery", label: "Solar PV with Battery System" },
  { value: "diesel", label: "Solar PV with Diesel Generator" },
];

export default function SolarDesign() {
  const [systemType, setSystemType] = useState("battery");

  return (
    <div className="space-y-6">
      <PageHeader image={step.image} title={step.title} subtitle="Size and configure the PV system — with a battery, or paired with a diesel generator" color={step.color} />
      <p className="-mt-4 text-sm text-ink-400">
        Sizes the PV array (and battery, or diesel generator) against the saved demand profile.
      </p>

      <Tabs options={SYSTEM_TYPES} value={systemType} onChange={setSystemType} />

      {systemType === "battery" ? <SolarBattery color={step.color} /> : <SolarDiesel color={step.color} />}
    </div>
  );
}
