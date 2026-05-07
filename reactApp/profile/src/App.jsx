import { useState, useEffect } from "react";
import SplashScreen from "./screens/SplashScreen";
import HomeScreen from "./screens/HomeScreen";
import ScheduleScreen from "./screens/ScheduleScreen";
import AddAppointmentScreen from "./screens/AddAppointmentScreen";
import RemindersScreen from "./screens/RemindersScreen";
import AddReminderScreen from "./screens/AddReminderScreen";
import MakeAccount from "./screens/makeAccount";
import Connection from "./screens/ConnectionPage"; // Ensure this matches your filename
import SettingsScreen from "./screens/SettingsScreen";
import SignIn from "./screens/SignIn";
import BottomNav from "./components/BottomNav";
import "./styles/global.css";

export default function App() {
  const [screen, setScreen] = useState("splash");
  const [allData, setAllData] = useState([]);

  // ── Sync Data Across Screens ──
  // This effect runs whenever the screen changes, ensuring the Home Screen 
  // always has the latest info from LocalStorage.
  useEffect(() => {
    const loadData = () => {
      const pills = JSON.parse(localStorage.getItem("app_reminders") || "[]");
      const appts = JSON.parse(localStorage.getItem("app_schedule") || "[]");
      
      // Combine both for the Home Screen overview
      setAllData([...pills, ...appts]);
    };

    loadData();
    
    // Listen for storage changes in other tabs/components
    window.addEventListener("storage", loadData);
    return () => window.removeEventListener("storage", loadData);
  }, [screen]); 

  // ── Navigation Helper ──
  const hideNav = [
    "splash",
    "add-appointment",
    "add-reminder",
    "make-account",
    "connection",
    "sign-in",
  ].includes(screen);

  return (
    <div className="app-shell">
      {/* ── Onboarding & Auth ── */}
      {screen === "splash" && <SplashScreen navigate={setScreen} />}
      {screen === "make-account" && <MakeAccount navigate={setScreen} />}
      {screen === "sign-in" && <SignIn navigate={setScreen} />}
      
      {/* ── Bluetooth Connection ── */}
      {/* Note: Connection screen now uses "navigate" for the back button to home */}
      {screen === "connect" && (
        <Connection 
          navigate={setScreen} 
          onConnected={() => setScreen("home")} 
        />
      )}

      {/* ── Main Dashboard ── */}
      {screen === "home" && (
        <HomeScreen
          navigate={setScreen}
          reminders={allData} 
        />
      )}

      {/* ── Recipient Schedule (Care Recipient) ── */}
      {screen === "schedule" && (
        <ScheduleScreen navigate={setScreen} />
      )}
      {screen === "add-appointment" && (
        <AddAppointmentScreen navigate={setScreen} />
      )}

      {/* ── Self-Care Reminders (Caregiver) ── */}
      {screen === "reminders" && (
        <RemindersScreen
          navigate={setScreen}
          reminders={allData.filter(item => item.name)} // Filters for pill reminders
          onDelete={(id) => {
            const updated = allData.filter(r => r.id !== id);
            localStorage.setItem("app_reminders", JSON.stringify(updated.filter(i => i.name)));
            setScreen("reminders"); // Trigger re-render
          }}
        />
      )}
      {screen === "add-reminder" && (
        <AddReminderScreen navigate={setScreen} />
      )}

      {/* ── Settings ── */}
      {screen === "settings" && <SettingsScreen navigate={setScreen} />}

      {/* ── Global Navigation ── */}
      {!hideNav && <BottomNav active={screen} navigate={setScreen} />}
    </div>
  );
}