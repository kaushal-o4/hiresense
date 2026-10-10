import { Link } from "react-router-dom";
import { EmptyState } from "../components/ui";

export default function NotFound() {
  return <EmptyState title="Page not found" message="The page you're looking for doesn't exist." action={<Link className="text-brand-600 hover:underline" to="/">Go to dashboard</Link>} />;
}
