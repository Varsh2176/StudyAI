/** Map academic risk labels to badge variants. */
export function riskToBadgeVariant(risk) {
  const value = String(risk || "").toLowerCase();
  if (value.includes("low")) return "success";
  if (value.includes("high")) return "danger";
  if (value.includes("moderate") || value.includes("medium")) return "warning";
  return "neutral";
}

/** Map priority labels to badge variants. */
export function priorityToBadgeVariant(priority) {
  const value = String(priority || "").toLowerCase();
  if (value.includes("high")) return "danger";
  if (value.includes("maintenance") || value.includes("low")) return "success";
  if (value.includes("standard") || value.includes("medium")) return "warning";
  return "info";
}

/** Map session/status labels to badge variants. */
export function statusToBadgeVariant(status) {
  const value = String(status || "").toLowerCase().replace(/\s+/g, "-");
  if (value === "completed" || value === "done") return "success";
  if (value === "missed" || value === "failed") return "danger";
  if (value === "partial" || value === "in-progress" || value === "in_progress") return "warning";
  if (value === "planned" || value === "scheduled") return "info";
  return "neutral";
}
