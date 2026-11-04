/*
 * Full notification list for any role: mark as read, mark all read, delete (/notifications endpoints).
 * The header bell in components/Layout.jsx shows the latest few.
 */

import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Trash2 } from "lucide-react";
import { del, get, post } from "../api";
import { Button, Card, EmptyState, ErrorBox, PageHeader, Pagination, Spinner, fmtDateTime, useApi, useToast } from "../components/ui";
import { onNotificationStatus, subscribeNotifications } from "../live/notificationStream";

const LIVE_LABEL = { live: "Live", connecting: "Connecting…", polling: "Reconnecting… (checking every 30 s)" };

function LiveStatus() {
  const [status, setStatus] = useState("idle");
  useEffect(() => onNotificationStatus(setStatus), []);
  if (!LIVE_LABEL[status]) return null;
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-slate-500" role="status">
      <span className={`h-1.5 w-1.5 rounded-full ${status === "live" ? "bg-emerald-500" : "bg-amber-500"}`} />
      {LIVE_LABEL[status]}
    </span>
  );
}

export default function Notifications() {
  const [page, setPage] = useState(1);
  const [unreadOnly, setUnreadOnly] = useState(false);
  const toast = useToast();
  const navigate = useNavigate();
  const query = () => get("/notifications", { page, page_size: 20, unread_only: unreadOnly });
  const { data, setData, error, loading, reload } = useApi(query, [page, unreadOnly]);

  // Live: refresh quietly (no spinner) when the stream signals a change.
  const queryRef = useRef(query);
  queryRef.current = query;
  useEffect(() => {
    let timer = null;
    const unsubscribe = subscribeNotifications(() => {
      clearTimeout(timer);
      timer = setTimeout(() => queryRef.current().then(setData).catch(() => {}), 150);
    });
    return () => { unsubscribe(); clearTimeout(timer); };
  }, [setData]);

  const act = async (fn) => { try { await fn(); reload(); } catch (e) { toast(e.message, "error"); } };

  return (
    <div>
      <PageHeader title="Notifications" subtitle={data ? <span className="flex flex-wrap items-center gap-3">{data.unread} unread <LiveStatus /></span> : ""}
        actions={<>
          <Button variant="secondary" onClick={() => { setUnreadOnly(!unreadOnly); setPage(1); }}>{unreadOnly ? "Show all" : "Unread only"}</Button>
          <Button variant="secondary" onClick={() => act(() => post("/notifications/read-all"))}>Mark all read</Button>
        </>} />
      <Card bodyClass="">
        {loading && <Spinner />}
        <div className="p-4"><ErrorBox message={error} onRetry={reload} /></div>
        {data && data.items.length === 0 && <EmptyState title="No notifications" />}
        <ul className="divide-y divide-slate-100">
          {data?.items.map((n) => (
            <li key={n.id} className={`flex items-start gap-3 px-5 py-4 ${n.read ? "" : "bg-brand-50/40"}`}>
              <button className="flex-1 text-left" onClick={() => act(async () => { if (!n.read) await post(`/notifications/${n.id}/read`); if (n.link) navigate(n.link); })}>
                <p className="text-sm font-medium">{n.title} {!n.read && <span className="ml-1 inline-block h-2 w-2 rounded-full bg-brand-500" />}</p>
                <p className="text-sm text-slate-600">{n.message}</p>
                <p className="mt-1 text-xs text-slate-400">{fmtDateTime(n.created_at)}</p>
              </button>
              <button className="rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-red-600" aria-label="Delete notification"
                onClick={() => act(() => del(`/notifications/${n.id}`))}><Trash2 size={16} /></button>
            </li>
          ))}
        </ul>
        {data && <Pagination page={data.page} pages={data.pages} total={data.total} onPage={setPage} />}
      </Card>
    </div>
  );
}
