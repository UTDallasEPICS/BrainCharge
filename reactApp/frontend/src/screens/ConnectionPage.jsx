import { useLanguage } from "../i18n/language.js";
import { useState } from "react";
import "../styles/connection.css";

export default function ConnectionScreen({ navigate }) {
  const { t } = useLanguage();
  const [isSearching, setIsSearching] = useState(false);
  const [status, setStatus] = useState("Disconnected");

  const handleConnect = () => {
    setIsSearching(true);
    setStatus("Searching for devices...");

    // Simulate a Bluetooth scan for 3 seconds
    setTimeout(() => {
      setIsSearching(false);
      setStatus("No devices found nearby. Please ensure your companion device is in pairing mode.");
    }, 3000);
  };

  return (
    <div className="connection-page">
      {/* ── Header ── */}
      <div className="conn-header">
       <button className="back-btn-simple" onClick={() => navigate("home")}>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polyline points="15 18 9 12 15 6"/>
          </svg>
        </button>
        <h1>{t("Device Connection")}</h1>
        <p>{t("Connect your User's Companion device via Bluetooth.")}</p>
      </div>

      {/* ── Body ── */}
      <div className="conn-body">
        <div className="status-container">
          <div className={`status-orb ${isSearching ? "pulse" : ""}`}>
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#000" strokeWidth="1.5">
              <path d="M5 12.55a11 11 0 0114.08 0M1.42 9a16 16 0 0121.16 0M8.53 16.11a6 6 0 016.95 0M12 20h.01" />
            </svg>
          </div>
          <h2 className="status-text">{isSearching ? "Scanning..." : t("Ready to Pair")}</h2>
          <p className="status-subtext">{status}</p>
        </div>

        {isSearching && (
          <div className="loading-bar-container">
            <div className="loading-bar-fill"></div>
          </div>
        )}

        <button 
          className={`connect-main-btn ${isSearching ? "searching" : ""}`} 
          onClick={handleConnect}
          disabled={isSearching}
        >
          {isSearching ? (
            <span className="spinner-row">
              <div className="spinner"></div>
              {t("Searching...")}
            </span>
          ) : (
            t("Search for Bluetooth Device")
          )}
        </button>

        <div className="conn-help">
          <h3>{t("Trouble connecting?")}</h3>
          <ul>
            <li>{t("Keep the device within 3 feet of your phone.")}</li>
            <li>{t("Check that Bluetooth is enabled in your phone settings.")}</li>
            <li>{t("Ensure the device has at least 20% battery.")}</li>
          </ul>
        </div>
      </div>
    </div>
  );
}