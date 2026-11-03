// Filter chip style shared by the list pages (status/type filters): glass chip, gradient + glow when active.
// `capitalize` (not first-letter:) because ::first-letter does not apply to inline-flex elements.
export const chipClass = (active) =>
  `inline-flex h-8 items-center whitespace-nowrap rounded-lg border px-3 text-[13px] font-medium capitalize transition focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 ${
    active ? "border-brand-400/50 bg-gradient-to-r from-brand-500 to-violet-500 text-snow shadow-glow"
      : "border-slate-200 bg-slate-100/60 text-slate-600 hover:border-slate-300 hover:bg-slate-200/60 hover:text-slate-900"}`;
