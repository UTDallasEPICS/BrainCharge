import { useEffect, useRef, useState } from "react";
import { useNotifications } from "../hooks/useNotifications";
import { groupNotifications } from "../utils/notifications";
import "../styles/notifications.css";

export default function NotificationCenter({ navigate }) {
  const [open, setOpen] = useState(false);
  const panelRef = useRef(null);
  const {
    items,
    badgeCount,
    enabled,
    loading,
    error,
    toast,
    dismissToast,
    refresh,
  } = useNotifications();

  const groups = groupNotifications(items);

  useEffect(() => {
    if (!open) return undefined;

    const onPointerDown = (event) => {
      if (panelRef.current && !panelRef.current.contains(event.target)) {
        setOpen(false);
      }
    };

    document.addEventListener("mousedown", onPointerDown);
    return () => document.removeEventListener("mousedown", onPointerDown);
  }, [open]);

  const handleItemClick = (item) => {
    setOpen(false);
    navigate(item.source === "calendar" ? "schedule" : "reminders");
  };

  return (
    <>
      <div className="notification-center" ref={panelRef}>
        <button
          type="button"
          className="notification-bell"
          aria-label="Notifications"
          aria-expanded={open}
          onClick={() => setOpen((prev) => !prev)}
        >
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M18 8A6 6 0 006 8c0 7-3 9-3 9h18s-3-2-3-9" />
            <path d="M13.73 21a2 2 0 01-3.46 0" />
          </svg>
          {badgeCount > 0 && (
            <span className="notification-badge">{badgeCount > 9 ? "9+" : badgeCount}</span>
          )}
        </button>

        {open && (
          <div className="notification-panel">
            <div className="notification-panel-header">
              <h2>Notifications</h2>
              <button type="button" className="notification-refresh" onClick={refresh}>
                Refresh
              </button>
            </div>

            {!enabled && (
              <p className="notification-disabled">
                Notifications are off. Enable them in Settings.
              </p>
            )}

            {error && (
              <p className="notification-error">{error}</p>
            )}

            {loading ? (
              <p className="notification-empty">Loading...</p>
            ) : groups.length === 0 ? (
              <p className="notification-empty">
                {enabled
                  ? "Nothing due soon. You're all caught up."
                  : "Turn on notifications in Settings to see upcoming alerts."}
              </p>
            ) : (
              groups.map((group) => (
                <div key={group.key} className="notification-group">
                  <p className="notification-group-label">{group.label}</p>
                  {group.items.map((item) => (
                    <button
                      key={item.id}
                      type="button"
                      className={`notification-item urgency-${item.urgency}`}
                      onClick={() => handleItemClick(item)}
                    >
                      <div className="notification-item-main">
                        <span className="notification-item-title">{item.title}</span>
                        <span className="notification-item-sub">{item.subtitle}</span>
                      </div>
                      <div className="notification-item-meta">
                        <span className="notification-item-time">{item.time}</span>
                        <span className="notification-item-label">{item.urgencyLabel}</span>
                      </div>
                    </button>
                  ))}
                </div>
              ))
            )}
          </div>
        )}
      </div>

      {toast && enabled && (
        <div className="notification-toast" role="status">
          <div>
            <p className="notification-toast-title">{toast.title}</p>
            <p className="notification-toast-message">{toast.message}</p>
          </div>
          <button type="button" className="notification-toast-close" onClick={dismissToast}>
            ×
          </button>
        </div>
      )}
    </>
  );
}
