import { useState } from "react";
import SplashScreen from "./screens/SplashScreen";
import HomeScreen from "./screens/HomeScreen";
import ScheduleScreen from "./screens/ScheduleScreen";
import AddAppointmentScreen from "./screens/AddAppointmentScreen";
import RemindersScreen from "./screens/RemindersScreen";
import AddReminderScreen from "./screens/AddReminderScreen";
import MakeAccount from "./screens/makeAccount";
import BottomNav from "./components/BottomNav";
import "./styles/global.css";

export default function App() {
  const [screen, setScreen] = useState("splash");
  const [reminders, setReminders] = useState([
    { id: 1, name: "Metformin 500mg", meta: "Daily · 8:00 AM & 6:00 PM · With meals", tag: "soon", tagLabel: "Due soon" },
    { id: 2, name: "Atorvastatin 20mg", meta: "Daily · 8:00 PM · With water", tag: "ok", tagLabel: "Tonight" },
    { id: 3, name: "Lisinopril 10mg", meta: "Daily · 9:00 AM · Morning", tag: "ok", tagLabel: "Tomorrow" },
    { id: 4, name: "Sertraline 50mg", meta: "Daily · 7:00 AM · With breakfast", tag: "ok", tagLabel: "Tomorrow" },
  ]);

  const hideNav = screen === "splash" || screen === "add-appointment" || screen === "add-reminder" || screen === "make-account";

  const addReminder = (r) => setReminders((prev) => [...prev, r]);
  const deleteReminder = (id) => setReminders((prev) => prev.filter((r) => r.id !== id));

  return (
    <div className="app-shell">
      
      {screen === "splash" && <SplashScreen navigate={setScreen} />}
      {screen === "home" && <HomeScreen navigate={setScreen} />}
      {screen === "schedule" && <ScheduleScreen navigate={setScreen} />}
      {screen === "add-appointment" && <AddAppointmentScreen navigate={setScreen} />}
      {screen === "make-account" && <MakeAccount navigate={setScreen} />}
      {screen === "reminders" && (
        <RemindersScreen navigate={setScreen} reminders={reminders} onDelete={deleteReminder} />
      )}
      {screen === "add-reminder" && (
        <AddReminderScreen navigate={setScreen} onSave={addReminder} />
      )}
      {!hideNav && <BottomNav active={screen} navigate={setScreen} />}
    </div>
  );
}
