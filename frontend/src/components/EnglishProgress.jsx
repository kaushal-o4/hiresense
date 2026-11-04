/*
 * English progress (GET /student/english/progress): words in the review list, review accuracy by week, and the
 * skill scores of recent evaluated sessions.
 */
import { BookOpen, CalendarCheck, GraduationCap, Target } from "lucide-react";
import { get } from "../api";
import { trendRows } from "../english/vocab";
import { SimpleBar, TimelineChart } from "./charts";
import { Card, StatCard, useApi } from "./ui";

const SKILLS = [
  { key: "overall", label: "Overall" }, { key: "grammar", label: "Grammar" }, { key: "vocabulary", label: "Vocabulary" },
  { key: "fluency", label: "Fluency" }, { key: "sentence_formation", label: "Sentences" },
];

export default function EnglishProgress() {
  const { data: p } = useApi(() => get("/student/english/progress"), []);
  if (!p) return null;
  const weekly = p.weekly_reviews.map((w) => ({ ...w, label: w.week.slice(5), accuracy: w.accuracy ?? 0 }));
  const anyReviews = p.weekly_reviews.some((w) => w.reviews > 0);
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 sm:gap-4 xl:grid-cols-4">
        <StatCard label="Words in your list" value={p.words.total} icon={BookOpen} hint={`${p.words.due} due now`} />
        <StatCard label="Words learned" value={p.words.learned} icon={GraduationCap} tone="green" hint={`${p.words.mastered} mastered`} />
        <StatCard label="Review accuracy" value={p.review_accuracy == null ? "—" : `${p.review_accuracy}%`} icon={Target} tone="sky" hint={`${p.reviews_recent} reviews, last 8 weeks`} />
        <StatCard label="Plan days completed" value={p.plan_days_completed} icon={CalendarCheck} tone="amber" hint="Days you finished the whole plan" />
      </div>
      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Skill scores by session">
          {p.score_trend.length ? <TimelineChart data={trendRows(p.score_trend)} keys={SKILLS} height={240} />
            : <p className="text-sm text-slate-500">Finish a conversation to get your first scores.</p>}
        </Card>
        <Card title="Review accuracy by week">
          {anyReviews ? <SimpleBar data={weekly} dataKey="accuracy" nameKey="label" max={100} height={240} />
            : <p className="text-sm text-slate-500">Review your words to see how many you remember each week.</p>}
        </Card>
      </div>
    </div>
  );
}
