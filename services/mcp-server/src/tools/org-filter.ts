// Shared shape for the "AND <col> = $N" org-scoping fragment every
// Postgres-querying tool needs. Centralizing this means a future org-filter
// change (or an 11th tool) can't silently get the $N index wrong or forget
// the orgId === null (no filter) case the way ten hand-copied ternaries
// could.
export function orgFilter(
  orgId: string | null,
  paramIndex: number,
  column: string,
): { clause: string; params: unknown[] } {
  if (orgId === null) return { clause: "", params: [] };
  return { clause: `AND ${column} = $${paramIndex}`, params: [orgId] };
}
