import { useState, useEffect } from "react";
import "../styles/settings.css";

const DATA_ERASE_OPTIONS = [
  { label: "Never", value: "never" },
  { label: "After 7 days", value: "7d" },
  { label: "After 30 days", value: "30d" },
  { label: "After 90 days", value: "90d" },
  { label: "After 1 year", value: "1y" },
];

function loadSettings() {
  try {
    const s = localStorage.getItem("app_settings");
    return s
      ? JSON.parse(s)
      : {
          notifications: true,
          darkMode: false,
          autoBackup: false,
          fontSize: "medium",
          dataErase: "never",
          dataEraseEnabled: false,
          companionName: "User's Companion",
          language: "en",
        };
  } catch {
    return {
      notifications: true,
      darkMode: false,
      autoBackup: false,
      fontSize: "medium",
      dataErase: "never",
      dataEraseEnabled: false,
      companionName: "User's Companion",
      language: "en",
    };
  }
}

function ToggleSwitch({ checked, onChange }) {
  return (
    <button
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      className={`toggle-switch ${checked ? "toggle-on" : "toggle-off"}`}
    >
      <span className="toggle-thumb" />
    </button>
  );
}

function SettingRow({ icon, label, sublabel, right }) {
  return (
    <div className="setting-row">
      <div className="setting-row-left">
        <div className="setting-icon">{icon}</div>
        <div>
          <p className="setting-label">{label}</p>
          {sublabel && <p className="setting-sublabel">{sublabel}</p>}
        </div>
      </div>
      <div className="setting-row-right">{right}</div>
    </div>
  );
}

export default function SettingsScreen({ navigate }) {
  const [settings, setSettings] = useState(loadSettings);
  const [saved, setSaved] = useState(false);
  const [showEraseConfirm, setShowEraseConfirm] = useState(false);

  const update = (key, value) => {
    setSettings((prev) => {
      const next = { ...prev, [key]: value };
      localStorage.setItem("app_settings", JSON.stringify(next));
      return next;
    });
  };

  const handleSave = () => {
    localStorage.setItem("app_settings", JSON.stringify(settings));
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  const handleEraseNow = () => {
    setShowEraseConfirm(true);
  };

  const confirmErase = () => {
    localStorage.removeItem("app_reminders");
    localStorage.removeItem("app_appointments");
    setShowEraseConfirm(false);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <div className="settings-screen">
      {/* Header */}
      <div className="settings-header">
        <button className="back-btn" onClick={() => navigate("home")}>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="rgba(255,255,255,0.9)" strokeWidth="2">
            <polyline points="15 18 9 12 15 6" />
          </svg>
        </button>
        <div>
          <h1>Settings</h1>
          <p className="settings-subtitle">App preferences &amp; configuration</p>
        </div>
      </div>

      <div className="settings-body">
        {/* General */}
        <p className="settings-section-label">General</p>
        <div className="settings-group">
          <SettingRow
            icon={<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="var(--teal)" strokeWidth="2"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2" /><circle cx="12" cy="7" r="4" /></svg>}
            label="Companion Name"
            sublabel="Name shown on the home screen"
            right={
              <input
                className="setting-input"
                value={settings.companionName}
                onChange={(e) => update("companionName", e.target.value)}
                maxLength={30}
              />
            }
          />
          <div className="setting-divider" />
          <SettingRow
            icon={<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="var(--teal)" strokeWidth="2"><circle cx="12" cy="12" r="10" /><line x1="2" y1="12" x2="22" y2="12" /><path d="M12 2a15.3 15.3 0 014 10 15.3 15.3 0 01-4 10 15.3 15.3 0 01-4-10 15.3 15.3 0 014-10z" /></svg>}
            label="Language"
            sublabel="Display language"
            right={
              <select
                className="setting-select"
                value={settings.language}
                onChange={(e) => update("language", e.target.value)}
              >
                <option value="en">English</option>
                <option value="es">Español</option>
                <option value="fr">Français</option>
                <option value="de">Deutsch</option>
              </select>
            }
          />
          <div className="setting-divider" />
          <SettingRow
            icon={<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="var(--teal)" strokeWidth="2"><path d="M4 6h16M4 12h8M4 18h4" /></svg>}
            label="Font Size"
            sublabel="Text size throughout the app"
            right={
              <select
                className="setting-select"
                value={settings.fontSize}
                onChange={(e) => update("fontSize", e.target.value)}
              >
                <option value="small">Small</option>
                <option value="medium">Medium</option>
                <option value="large">Large</option>
              </select>
            }
          />
        </div>

        {/* Appearance */}
        <p className="settings-section-label">Appearance</p>
        <div className="settings-group">
          <SettingRow
            icon={<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="var(--teal)" strokeWidth="2"><path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z" /></svg>}
            label="Dark Mode"
            sublabel="Switch to dark theme"
            right={<ToggleSwitch checked={settings.darkMode} onChange={(v) => update("darkMode", v)} />}
          />
        </div>

        {/* Notifications */}
        <p className="settings-section-label">Notifications</p>
        <div className="settings-group">
          <SettingRow
            icon={<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="var(--teal)" strokeWidth="2"><path d="M18 8A6 6 0 006 8c0 7-3 9-3 9h18s-3-2-3-9" /><path d="M13.73 21a2 2 0 01-3.46 0" /></svg>}
            label="Push Notifications"
            sublabel="Reminders &amp; appointment alerts"
            right={<ToggleSwitch checked={settings.notifications} onChange={(v) => update("notifications", v)} />}
          />
          <div className="setting-divider" />
          <SettingRow
            icon={<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="var(--teal)" strokeWidth="2"><polyline points="20 6 9 17 4 12" /></svg>}
            label="Auto Backup"
            sublabel="Sync data automatically"
            right={<ToggleSwitch checked={settings.autoBackup} onChange={(v) => update("autoBackup", v)} />}
          />
        </div>

        {/* Data Management */}
        <p className="settings-section-label">Data Management</p>
        <div className="settings-group">
          <SettingRow
            icon={<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="var(--teal)" strokeWidth="2"><polyline points="3 6 5 6 21 6" /><path d="M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6" /><path d="M10 11v6M14 11v6" /><path d="M9 6V4a1 1 0 011-1h4a1 1 0 011 1v2" /></svg>}
            label="Auto-Erase Data"
            sublabel="Automatically delete app data after a set time"
            right={<ToggleSwitch checked={settings.dataEraseEnabled} onChange={(v) => update("dataEraseEnabled", v)} />}
          />
          {settings.dataEraseEnabled && (
            <div className="erase-sub">
              <p className="erase-sub-label">Erase data after:</p>
              <div className="erase-options">
                {DATA_ERASE_OPTIONS.map((opt) => (
                  <button
                    key={opt.value}
                    className={`erase-chip ${settings.dataErase === opt.value ? "erase-chip-active" : ""}`}
                    onClick={() => update("dataErase", opt.value)}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
              {settings.dataErase !== "never" && (
                <p className="erase-info">
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" strokeWidth="2" style={{ flexShrink: 0 }}>
                    <circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" />
                  </svg>
                  Reminders and local data will be cleared {DATA_ERASE_OPTIONS.find(o => o.value === settings.dataErase)?.label.toLowerCase()} of inactivity.
                </p>
              )}
            </div>
          )}
          <div className="setting-divider" />
          <div className="setting-row">
            <div className="setting-row-left">
              <div className="setting-icon">
                <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="#e05252" strokeWidth="2"><polyline points="3 6 5 6 21 6" /><path d="M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6" /><path d="M9 6V4a1 1 0 011-1h4a1 1 0 011 1v2" /></svg>
              </div>
              <div>
                <p className="setting-label setting-label-danger">Erase All Data Now</p>
                <p className="setting-sublabel">Immediately clear all local data</p>
              </div>
            </div>
            <button className="danger-btn" onClick={handleEraseNow}>Erase</button>
          </div>
        </div>

        <button className={`save-btn ${saved ? "save-btn-success" : ""}`} onClick={handleSave}>
          {saved ? (
            <>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2.5"><polyline points="20 6 9 17 4 12" /></svg>
              Saved!
            </>
          ) : (
            "Save Settings"
          )}
        </button>
      </div>

      {/* Erase confirmation modal */}
      {showEraseConfirm && (
        <div className="modal-overlay" onClick={() => setShowEraseConfirm(false)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="modal-icon-wrap">
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#e05252" strokeWidth="2"><polyline points="3 6 5 6 21 6" /><path d="M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6" /><path d="M9 6V4a1 1 0 011-1h4a1 1 0 011 1v2" /></svg>
            </div>
            <h3 className="modal-title">Erase All Data?</h3>
            <p className="modal-body">This will permanently delete all reminders and local app data. This cannot be undone.</p>
            <div className="modal-actions">
              <button className="modal-cancel" onClick={() => setShowEraseConfirm(false)}>Cancel</button>
              <button className="modal-confirm" onClick={confirmErase}>Yes, Erase</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}