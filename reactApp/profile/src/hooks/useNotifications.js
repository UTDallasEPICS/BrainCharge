import { useCallback, useEffect, useRef, useState } from "react";
import { listEvents } from "../api/calendar";
import {
  buildNotificationItems,
  getBadgeCount,
  loadNotificationSettings,
} from "../utils/notifications";

const POLL_INTERVAL_MS = 60_000;

export function useNotifications() {
  const [items, setItems] = useState([]);
  const [enabled, setEnabled] = useState(loadNotificationSettings);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [toast, setToast] = useState(null);
  const seenUrgentRef = useRef(new Set());

  const refresh = useCallback(async () => {
    const notificationsOn = loadNotificationSettings();
    setEnabled(notificationsOn);

    const reminders = JSON.parse(localStorage.getItem("app_reminders") || "[]");
    let calendarEvents = [];

    try {
      calendarEvents = await listEvents({ maxResults: 50 });
      setError("");
    } catch (err) {
      setError(err.message);
    }

    const nextItems = buildNotificationItems({ reminders, calendarEvents });
    setItems(nextItems);
    setLoading(false);

    if (notificationsOn) {
      const urgent = nextItems.filter((item) => item.urgency === "urgent");
      const fresh = urgent.find((item) => !seenUrgentRef.current.has(item.id));
      if (fresh) {
        seenUrgentRef.current.add(fresh.id);
        setToast({
          id: fresh.id,
          title: fresh.title,
          message: fresh.urgencyLabel,
        });
      }
    }

    return nextItems;
  }, []);

  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, POLL_INTERVAL_MS);
    const onUpdate = () => refresh();

    window.addEventListener("calendar-updated", onUpdate);
    window.addEventListener("storage", onUpdate);
    window.addEventListener("settings-updated", onUpdate);

    return () => {
      clearInterval(interval);
      window.removeEventListener("calendar-updated", onUpdate);
      window.removeEventListener("storage", onUpdate);
      window.removeEventListener("settings-updated", onUpdate);
    };
  }, [refresh]);

  useEffect(() => {
    if (!toast) return undefined;
    const timer = setTimeout(() => setToast(null), 5000);
    return () => clearTimeout(timer);
  }, [toast]);

  return {
    items,
    badgeCount: enabled ? getBadgeCount(items) : 0,
    enabled,
    loading,
    error,
    toast,
    dismissToast: () => setToast(null),
    refresh,
  };
}
