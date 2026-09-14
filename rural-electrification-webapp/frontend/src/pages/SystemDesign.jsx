import { useState } from "react";
import { PageHeader } from "../components/Card";
import Tabs from "../components/Tabs";
import { stepByPath } from "../lib/steps";
import SolarBattery from "./solar/SolarBattery";
import SolarDiesel from "./solar/SolarDiesel";
import WindBattery from "./wind/WindBattery";
import WindDiesel from "./wind/WindDiesel";

const step = stepByPath("/solar-design");
const SYSTEM_TYPES = [
  { value: "battery", label: "Solar PV with Battery System" },
  { value: "diesel", label: "Solar PV with Diesel Generator" },
  { value: "wind_battery", label: "Wind Turbine with Battery System" },
  { value: "wind_diesel", label: "Wind Turbine with Diesel Generator" },
];

const PAGES = {
  battery: SolarBattery,
  diesel: SolarDiesel,
  wind_battery: WindBattery,
  wind_diesel: WindDiesel,
};

export default function SystemDesign() {
  const [systemType, setSystemType] = useState("battery");
  const Page = PAGES[systemType];

  return (
    <div className="space-y-6">
      <PageHeader image={step.image} title={step.title} subtitle="Size and configure the generation system — solar PV or a wind turbine, with a battery, or paired with a diesel generator" color={step.color} />
      <p className="-mt-4 text-sm text-ink-400">
        Sizes the chosen generation source (and battery, or diesel generator) against the saved demand profile.
      </p>

      <Tabs options={SYSTEM_TYPES} value={systemType} onChange={setSystemType} />

      <Page color={step.color} />
    </div>
  );
}
