import { timingSafeEqual } from "node:crypto";

export const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

// Constant-time compare so a mismatched token can't be brute-forced via
// response-time differences — same approach as the ArgoCD/Alertmanager
// webhook token checks in services/ingest/app/auth.py
// (hmac.compare_digest). A length mismatch returns false immediately
// rather than calling timingSafeEqual (which throws on unequal-length
// buffers) — this does leak the correct token's length via response
// timing, same tradeoff auth.py's hmac.compare_digest makes.
export function isValidBearerToken(authorization: string | undefined, expected: string): boolean {
  const prefix = "Bearer ";
  if (!authorization || !authorization.startsWith(prefix)) return false;
  const provided = Buffer.from(authorization.slice(prefix.length));
  const expectedBuf = Buffer.from(expected);
  if (provided.length !== expectedBuf.length) return false;
  return timingSafeEqual(provided, expectedBuf);
}
