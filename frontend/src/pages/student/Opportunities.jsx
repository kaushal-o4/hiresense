import UrlTabs from "../../components/Tabs";
import StudentDrives from "./Drives";
import Jobs from "./Jobs";

// Job openings and campus placement drives in one place (previously two menu items).
export default function Opportunities() {
  return (
    <UrlTabs label="Opportunities" tabs={[
      { id: "jobs", label: "Job openings", element: <Jobs /> },
      { id: "drives", label: "Placement drives", element: <StudentDrives /> },
    ]} />
  );
}
