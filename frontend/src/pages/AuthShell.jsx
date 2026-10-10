import { BarChart3, Mic, Sparkles, Target } from "lucide-react";

export default function AuthShell({ title, subtitle, children }) {
  return (
    <div className="flex min-h-screen">
      <div className="hidden w-1/2 flex-col justify-between bg-gradient-to-br from-brand-900 via-brand-800 to-brand-600 p-12 text-white lg:flex">
        <div className="flex items-center gap-2">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-white/15"><Sparkles /></div>
          <span className="text-2xl font-bold">HireSense</span>
        </div>
        <div>
          <h2 className="text-4xl font-bold leading-tight text-white">AI-powered interview &amp; placement readiness</h2>
          <ul className="mt-8 space-y-4 text-brand-100">
            <li className="flex items-center gap-3"><Mic size={20} /> Mock interviews with instant, explainable feedback</li>
            <li className="flex items-center gap-3"><BarChart3 size={20} /> Track progress across interviews, English &amp; assessments</li>
            <li className="flex items-center gap-3"><Target size={20} /> Mentors, recruiters and the placement office on one platform</li>
          </ul>
        </div>
        <p className="text-sm text-brand-200">Students · Recruiters · Mentors · Administrators</p>
      </div>
      <div className="flex flex-1 items-center justify-center px-4 py-12">
        <div className="w-full max-w-md">
          <div className="mb-8 lg:hidden">
            <span className="text-2xl font-bold text-brand-700">HireSense</span>
          </div>
          <h1 className="text-2xl font-bold">{title}</h1>
          {subtitle && <p className="mt-1 text-sm text-slate-500">{subtitle}</p>}
          <div className="mt-8">{children}</div>
        </div>
      </div>
    </div>
  );
}
