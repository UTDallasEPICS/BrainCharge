import { useState, useEffect } from "react";
import { useSession, signOut } from "./lib/auth-client";
import SplashScreen from "./screens/SplashScreen";
import HomeScreen from "./screens/HomeScreen";
import ScheduleScreen from "./screens/ScheduleScreen";
import AddAppointmentScreen from "./screens/AddAppointmentScreen";
import RemindersScreen from "./screens/RemindersScreen";
import AddReminderScreen from "./screens/AddReminderScreen";
import MakeAccount from "./screens/MakeAccount";
import Connection from "./screens/ConnectionPage";
import SettingsScreen from "./screens/SettingsScreen";
import SignIn from "./screens/SignIn";
import BottomNav from "./components/BottomNav";
import NotificationCenter from "./components/NotificationCenter";
import "./styles/global.css";

const PUBLIC_SCREENS = new Set(["splash", "sign-in", "make-account"]);

function AuthLoading({ message = "Loading..." }) {
  return (
    <div className="app-shell auth-loading">
      <p>{message}</p>
    </div>
  );
}

function RequireAuth({ session, isPending, children, message = "Signing you in..." }) {
  if (isPending) return <AuthLoading message={message} />;
  if (!session) return null;
  return children(session);
}

export default function App() {
  const { data: session, isPending } = useSession();
  const [screen, setScreen] = useState("splash");
  const [allData, setAllData] = useState([]);
  const [editingAppointment, setEditingAppointment] = useState(null);
  const [isLoggingOut, setIsLoggingOut] = useState(false);

{/*Dark mode & font size state management - AnahiF  */}
  const [isDarkMode, setIsDarkMode] = useState(false);
  const [fontSize, setFontSize] = useState("medium");

  useEffect(() => {
    const syncSettings = () => {
      try {
        const storedSettings = JSON.parse(localStorage.getItem("app_settings") || "{}");
        setIsDarkMode(Boolean(storedSettings.darkMode));
        const size = storedSettings.fontSize;
        setFontSize(size === "small" || size === "large" ? size : "medium");
      } catch {
        setIsDarkMode(false);
        setFontSize("medium");
      }
    };

    syncSettings();
    window.addEventListener("settings-updated", syncSettings);

    return () => {
      window.removeEventListener("settings-updated", syncSettings);
    };
  }, []);
{/*End of dark mode & font size state management - AnahiF  */}
  useEffect(() => {
    if (isPending || isLoggingOut) return;

    if (session && PUBLIC_SCREENS.has(screen)) {
      setScreen("home");
      return;
    }

    if (!session && !PUBLIC_SCREENS.has(screen)) {
      setScreen("sign-in");
    }
  }, [session, isPending, screen, isLoggingOut]);

  const navigate = (next) => {
    setScreen(next);
  };

  const handleLogout = async () => {
    setIsLoggingOut(true);
    setScreen("sign-in");
    await signOut();
    setIsLoggingOut(false);
  };

  useEffect(() => {
    const loadData = () => {
      const pills = JSON.parse(localStorage.getItem("app_reminders") || "[]");
      const appts = JSON.parse(localStorage.getItem("app_schedule") || "[]");
      setAllData([...pills, ...appts]);
    };

    loadData();
    window.addEventListener("storage", loadData);
    return () => window.removeEventListener("storage", loadData);
  }, [screen]);

  const hideNav = [
    "splash",
    "add-appointment",
    "add-reminder",
    "make-account",
    "connection",
    "sign-in",
  ].includes(screen);

  if (isPending && !PUBLIC_SCREENS.has(screen)) {
    return <AuthLoading />;
  }

  {/* app-shell className includes theme + font-size classes from settings - AnahiF*/}
  return (
    <div className={`app-shell ${isDarkMode ? "dark" : ""} font-size-${fontSize}`}> 
      {screen === "splash" && <SplashScreen navigate={navigate} />}
      {screen === "make-account" && <MakeAccount navigate={navigate} />}
      {screen === "sign-in" && <SignIn navigate={navigate} />}

      {screen === "connect" && (
        <RequireAuth session={session} isPending={isPending}>
          {() => (
            <Connection
              navigate={navigate}
              onConnected={() => navigate("home")}
            />
          )}
        </RequireAuth>
      )}

      {screen === "home" && (
        <RequireAuth session={session} isPending={isPending}>
          {(authSession) => (
            <HomeScreen navigate={navigate} user={authSession.user} onLogout={handleLogout} />
          )}
        </RequireAuth>
      )}

      {screen === "schedule" && (
        <RequireAuth session={session} isPending={isPending}>
          {() => (
            <ScheduleScreen
              navigate={navigate}
              onEditAppointment={(appt) => {
                setEditingAppointment(appt);
                navigate("add-appointment");
              }}
            />
          )}
        </RequireAuth>
      )}

      {screen === "add-appointment" && (
        <RequireAuth session={session} isPending={isPending}>
          {() => (
            <AddAppointmentScreen
              navigate={navigate}
              editingAppointment={editingAppointment}
              onClearEdit={() => setEditingAppointment(null)}
            />
          )}
        </RequireAuth>
      )}

      {screen === "reminders" && (
        <RequireAuth session={session} isPending={isPending}>
          {() => (
            <RemindersScreen
              navigate={navigate}
              reminders={allData.filter((item) => item.name)}
              onDelete={(id) => {
                const updated = allData.filter((r) => r.id !== id);
                localStorage.setItem("app_reminders", JSON.stringify(updated.filter((i) => i.name)));
                navigate("reminders");
              }}
            />
          )}
        </RequireAuth>
      )}

      {screen === "add-reminder" && (
        <RequireAuth session={session} isPending={isPending}>
          {() => <AddReminderScreen navigate={navigate} />}
        </RequireAuth>
      )}

      {screen === "settings" && (
        <RequireAuth session={session} isPending={isPending}>
          {() => <SettingsScreen navigate={navigate} />}
        </RequireAuth>
      )}

      {session && !hideNav && <NotificationCenter navigate={navigate} />}
      {session && !hideNav && <BottomNav active={screen} navigate={navigate} />}
    </div>
  );
}
