import { createContext, useContext } from "react";
import { useApiGet } from "../hooks/useApi";

const ProgressContext = createContext(null);

// Wraps /api/progress in a context so any step page can call refetch() right after a successful save
// and have the top stepper's checkmarks update immediately, without waiting for a route change.
export function ProgressProvider({ children }) {
  const { data, refetch } = useApiGet("/api/progress");
  return <ProgressContext.Provider value={{ progress: data, refetchProgress: refetch }}>{children}</ProgressContext.Provider>;
}

export function useProgress() {
  const ctx = useContext(ProgressContext);
  if (!ctx) throw new Error("useProgress must be used within a ProgressProvider");
  return ctx;
}
