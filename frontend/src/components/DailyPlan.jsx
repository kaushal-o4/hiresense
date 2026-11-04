/*
 * "Today's English plan" (GET /student/english/daily-plan). Each item ticks itself from what the student did today
 * (reviews, a conversation in the suggested mode, an interview answer); finishing all of them earns points once a day.
 * `compact` is the student-dashboard version.
 */
import { Link } from "react-router-dom";
import { CheckCircle2, Circle } from "lucide-react";
import { get } from "../api";
import { planSummary } from "../english/vocab";
import { Card, ScoreBar, useApi } from "./ui";

export default function DailyPlan({ compact = false, className = "" }) {
  const { data: plan } = useApi(() => get("/student/english/daily-plan"), []);
  if (!plan) return null;
  const sum = planSummary(plan);
  return (
    <Card title="Today's English plan" className={className}
      actions={<span className="num text-xs text-slate-500">{sum.done}/{sum.total} done</span>}>
      <ScoreBar value={sum.percent} />
      <ul className={`mt-3 ${compact ? "space-y-2" : "space-y-3"}`}>
        {plan.items.map((i) => (
          <li key={i.id} className="flex items-start gap-2.5 text-sm">
            {i.done
              ? <CheckCircle2 size={16} className="mt-0.5 shrink-0 text-emerald-600" aria-label="Done" />
              : <Circle size={16} className="mt-0.5 shrink-0 text-slate-500" aria-label="Not done yet" />}
            <div className="min-w-0">
              <Link to={i.link} className={`font-medium hover:underline ${i.done ? "text-slate-500 line-through decoration-slate-300" : "text-slate-800"}`}>
                {i.title}
              </Link>
              {i.target > 1 && <span className="num ml-2 text-xs text-slate-500">{i.progress}/{i.target}</span>}
              {!compact && <p className="text-xs text-slate-500">{i.detail}</p>}
            </div>
          </li>
        ))}
      </ul>
      <p className="mt-3 text-xs text-slate-500">
        {sum.allDone ? "All done for today. Points added to your rewards." : "Ticks itself as you practise. Finish everything for bonus points."}
      </p>
    </Card>
  );
}
