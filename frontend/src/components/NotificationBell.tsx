import { useState, useEffect, useRef } from 'react';
import { Bell, CheckCheck, X } from 'lucide-react';

export default function NotificationBell() {
  const [notifications, setNotifications] = useState<any[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  const fetchNotifications = async () => {
    try {
      const res = await fetch('/api/ontology/notifications');
      const data = await res.json();
      setNotifications(data.notifications || []);
      setUnreadCount(data.unread_count || 0);
    } catch { }
  };

  useEffect(() => {
    fetchNotifications();
    const iv = setInterval(fetchNotifications, 15000);
    return () => clearInterval(iv);
  }, []);

  // Close on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const markAllRead = async () => {
    await fetch('/api/ontology/notifications/read-all', { method: 'POST' });
    fetchNotifications();
  };

  const TYPE_COLORS: Record<string, string> = {
    action_proposed: '#EC9A3C',
    action_approved: '#32A467',
    action_rejected: '#E76A6E',
    action_completed: '#4C90F0',
    alert_triggered: '#E76A6E',
  };

  return (
    <div ref={ref} style={{ position: 'relative' }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          height: 28, width: 28, borderRadius: 6,
          border: '1px solid var(--b2)', background: 'transparent',
          color: 'var(--muted)', cursor: 'pointer',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          position: 'relative',
        }}
      >
        <Bell size={13} />
        {unreadCount > 0 && (
          <span style={{
            position: 'absolute', top: -3, right: -3,
            width: 14, height: 14, borderRadius: '50%',
            background: 'var(--rose)', color: '#fff',
            fontSize: 8, fontWeight: 700,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div style={{
          position: 'absolute', top: 32, right: 0, zIndex: 200,
          width: 300, maxHeight: 360, overflowY: 'auto',
          background: 'var(--bg1)', border: '1px solid var(--b2)',
          borderRadius: 'var(--r2)', boxShadow: '0 8px 24px rgba(0,0,0,.5)',
        }}>
          {/* Header */}
          <div style={{
            padding: '8px 10px', borderBottom: '1px solid var(--b1)',
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          }}>
            <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--heading)' }}>Notifications</span>
            <div style={{ display: 'flex', gap: 4 }}>
              {unreadCount > 0 && (
                <button onClick={markAllRead} style={{
                  background: 'none', border: 'none', color: 'var(--sky)',
                  cursor: 'pointer', fontSize: 9, display: 'flex', alignItems: 'center', gap: 3,
                }}>
                  <CheckCheck size={10} /> Read all
                </button>
              )}
              <button onClick={() => setOpen(false)} style={{
                background: 'none', border: 'none', color: 'var(--muted)', cursor: 'pointer', padding: 2,
              }}>
                <X size={12} />
              </button>
            </div>
          </div>

          {/* Notification list */}
          {notifications.length === 0 ? (
            <div style={{ padding: 20, textAlign: 'center', fontSize: 11, color: 'var(--dim)' }}>
              No notifications yet
            </div>
          ) : (
            notifications.slice(0, 20).map(n => (
              <div
                key={n.id}
                style={{
                  padding: '8px 10px', borderBottom: '1px solid var(--b1)',
                  background: n.is_read ? 'transparent' : 'rgba(76,144,240,.03)',
                  cursor: n.link ? 'pointer' : 'default',
                }}
                onClick={() => {
                  if (n.link) window.location.hash = `#${n.link}`;
                  setOpen(false);
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2 }}>
                  <div style={{
                    width: 6, height: 6, borderRadius: '50%',
                    background: n.is_read ? 'var(--dim)' : (TYPE_COLORS[n.type] || 'var(--sky)'),
                    flexShrink: 0,
                  }} />
                  <span style={{ fontSize: 10, fontWeight: 600, color: 'var(--heading)' }}>{n.title}</span>
                </div>
                <div style={{ fontSize: 9, color: 'var(--muted)', paddingLeft: 12, lineHeight: 1.4 }}>
                  {n.message}
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
