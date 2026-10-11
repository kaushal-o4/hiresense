import { useSearchParams } from "react-router-dom";

/**
 * Page-level tabs kept in the URL (?tab=...), so every tab can be linked to and the back button works.
 * tabs: [{ id, label, element }]; the first tab is the default.
 */
export default function UrlTabs({ tabs, label }) {
  const [params, setParams] = useSearchParams();
  const active = tabs.find((t) => t.id === params.get("tab")) || tabs[0];
  const select = (id) => setParams(id === tabs[0].id ? {} : { tab: id }, { replace: true });
  return (
    <div className="space-y-6">
      <div role="tablist" aria-label={label} className="flex gap-1 overflow-x-auto border-b border-slate-200 print:hidden">
        {tabs.map((t) => (
          <button key={t.id} type="button" role="tab" aria-selected={t.id === active.id} onClick={() => select(t.id)}
            className={`-mb-px whitespace-nowrap border-b-2 px-4 py-2 text-sm font-medium transition ${t.id === active.id
              ? "border-brand-600 text-brand-700" : "border-transparent text-slate-500 hover:text-slate-800"}`}>
            {t.label}
          </button>
        ))}
      </div>
      <div role="tabpanel">{active.element}</div>
    </div>
  );
}
