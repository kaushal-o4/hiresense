/* 404 page for unknown routes inside the signed-in layout. */

import { Link } from "react-router-dom";
import { EmptyState } from "../components/ui";

export default function NotFound() {
  return <EmptyState title="Page not found" message="The page you're looking for doesn't exist." action={<Link className="inline-flex h-10 items-center rounded-xl px-5 text-sm font-medium bg-gradient-to-r from-brand-500 to-violet-500 text-snow shadow-glow hover:brightness-110" to="/">Go to dashboard</Link>} />;
}
