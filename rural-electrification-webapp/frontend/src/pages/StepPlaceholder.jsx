import { PageHeader } from "../components/Card";
import { Card } from "../components/Card";

// Temporary placeholder shown for a step page not yet built out — swapped for the real page as each
// one is implemented, so navigation/routing can be verified end-to-end before every page is finished.
export default function StepPlaceholder({ step }) {
  return (
    <div>
      <PageHeader image={step.image} title={step.title} subtitle={step.tagline} color={step.color} />
      <Card className="flex flex-col items-center justify-center gap-2 py-16 text-center">
        <p className="font-display text-lg font-bold text-ink-800">This page is being built.</p>
        <p className="max-w-md text-sm text-ink-400">{step.description}</p>
      </Card>
    </div>
  );
}
