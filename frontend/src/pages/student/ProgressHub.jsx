/* "My Progress" menu item: Overview, Full report and Practice history as URL tabs. */

import UrlTabs from "../../components/Tabs";
import PerformanceReport from "./PerformanceReport";
import PracticeHistory from "./PracticeHistory";
import Progress from "./Progress";

// One "My Progress" area instead of three separate menu items (Progress, Performance Report, Practice History).
export default function ProgressHub() {
  return (
    <UrlTabs label="My progress" tabs={[
      { id: "overview", label: "Overview", element: <Progress /> },
      { id: "report", label: "Full report", element: <PerformanceReport /> },
      { id: "history", label: "Practice history", element: <PracticeHistory /> },
    ]} />
  );
}
