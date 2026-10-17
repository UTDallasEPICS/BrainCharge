import { createContext, useContext } from "react";

// Shared store so any child can read/set face vs app mode via useRobotMode().
// The value is provided by <RobotModeProvider> in RobotModeProvider.jsx.
export const RobotModeContext = createContext(null);

/** Hook for reading mode / calling goApp / goFace from any child of RobotModeProvider. */
export function useRobotMode() {
  const ctx = useContext(RobotModeContext);
  if (!ctx) {
    throw new Error("useRobotMode must be used within RobotModeProvider");
  }
  return ctx;
}
