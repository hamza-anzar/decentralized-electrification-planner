import loadSetupImg from "../assets/icons/load_setup.png";
import demandProfileImg from "../assets/icons/demand_profile.png";
import energyInsightsImg from "../assets/icons/energy_insights.png";
import solarDesignImg from "../assets/icons/solar_design.png";
import financialsImg from "../assets/icons/financials.png";
import resultsImg from "../assets/icons/results.png";

// Single source of truth for the six-step flow: route, illustration, palette, stepper labels.
// The landing page renders these as illustrated cards; the top stepper renders them as a progress rail.
export const STEPS = [
  {
    key: "loadSetup",
    index: 1,
    path: "/load-setup",
    title: "Load Setup",
    stepperLabel: "LOAD SETUP",
    tagline: "Build your electrical load",
    description: "Site & location details, household categories, appliances, and community loads.",
    image: loadSetupImg,
    color: "#2a78d6",
    colorSoft: "#eef5fd",
  },
  {
    key: "demandProfile",
    index: 2,
    path: "/demand-profile",
    title: "Demand Profile",
    stepperLabel: "DEMAND",
    tagline: "Understand when energy is being used",
    description: "A fully editable 365-day calendar drives the 8,760-hour annual demand profile.",
    image: demandProfileImg,
    color: "#1baf7a",
    colorSoft: "#e8faf3",
  },
  {
    key: "energyInsights",
    index: 3,
    path: "/energy-insights",
    title: "Energy Insights",
    stepperLabel: "INSIGHTS",
    tagline: "Explore consumption & demand patterns",
    description: "Hourly, daily, weekly, monthly and annual views of the demand profile.",
    image: energyInsightsImg,
    color: "#7a5cd6",
    colorSoft: "#f2effc",
  },
  {
    key: "solarDesign",
    index: 4,
    path: "/solar-design",
    title: "Solar Design",
    stepperLabel: "SOLAR DESIGN",
    tagline: "Size and configure the PV system",
    description: "Site solar resource, PV sizing, battery sizing, irradiance and duck-curve analysis.",
    image: solarDesignImg,
    color: "#eda100",
    colorSoft: "#fef6e6",
  },
  {
    key: "financials",
    index: 5,
    path: "/financials",
    title: "Financial Analysis",
    stepperLabel: "FINANCIALS",
    tagline: "Evaluate cost, savings & payback",
    description: "Bill of quantities, O&M present value, and levelized cost of energy — in EUR.",
    image: financialsImg,
    color: "#eb6834",
    colorSoft: "#fdece4",
  },
  {
    key: "results",
    index: 6,
    path: "/results",
    title: "Results",
    stepperLabel: "RESULTS",
    tagline: "Review ROI, payback & the full summary",
    description: "Every step's headline figures, plus payback, NPV and lifetime ROI.",
    image: resultsImg,
    color: "#d65c9e",
    colorSoft: "#fdedf5",
  },
];

export const stepByPath = (path) => STEPS.find((s) => s.path === path);
