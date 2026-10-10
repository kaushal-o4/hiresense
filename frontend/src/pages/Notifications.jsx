import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Trash2 } from "lucide-react";
import { del, get, post } from "../api";
import { Button, Card, EmptyState, ErrorBox, PageHeader, Pagination, Spinner, fmtDateTime, useApi, useToast } from "../components/ui";

export default function Notifications() {
  const [page, setPage] = useState(1);
  const [unreadOnly, setUnreadOnly] = useState(false);
  const toast = useToast();
  const navigate = useNavigate();
  const { data, error, loading, reload } = useApi(() => get("/notifications", { page, page_size: 20, unread_only: unreadOnly }), [page, unreadOnly]);

  const act = async (fn) => { try { await fn(); reload(); } catch (e) { toast(e.message, "error"); } };

  return (
    <div>
      <PageHeader title="Notifications" subtitle={data ? `${data.unread} unread` : ""}
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
