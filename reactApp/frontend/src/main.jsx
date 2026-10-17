import React from "react";
import ReactDOM from "react-dom/client";
import { registerSW } from "virtual:pwa-register";
import { RobotModeProvider } from "./context/RobotModeProvider.jsx";
import App from "./App.jsx";

registerSW({
  immediate: true,
  onOfflineReady() {
    console.info("BrainCharge is ready to work offline.");
  },
});

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    {/* Provides face vs app mode to the whole app (boots on the robot face) */}
    <RobotModeProvider>
      <App />
    </RobotModeProvider>
  </React.StrictMode>,
);
