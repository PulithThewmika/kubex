import { describe, it, expect } from "vitest";
import { isValidBearerToken, UUID_RE } from "./http-auth.js";

describe("isValidBearerToken", () => {
  const TOKEN = "s3cr3t-token-value";

  it("accepts a matching bearer token", () => {
    expect(isValidBearerToken(`Bearer ${TOKEN}`, TOKEN)).toBe(true);
  });

  it("rejects a missing Authorization header", () => {
    expect(isValidBearerToken(undefined, TOKEN)).toBe(false);
  });

  it("rejects a header without the Bearer prefix", () => {
    expect(isValidBearerToken(TOKEN, TOKEN)).toBe(false);
  });

  it("rejects a wrong token of the same length", () => {
    const wrong = "x".repeat(TOKEN.length);
    expect(isValidBearerToken(`Bearer ${wrong}`, TOKEN)).toBe(false);
  });

  it("rejects a wrong token of a different length", () => {
    expect(isValidBearerToken("Bearer short", TOKEN)).toBe(false);
    expect(isValidBearerToken(`Bearer ${TOKEN}-extra`, TOKEN)).toBe(false);
  });

  it("rejects an empty bearer value", () => {
    expect(isValidBearerToken("Bearer ", TOKEN)).toBe(false);
  });
});

describe("UUID_RE", () => {
  it("matches a well-formed UUID", () => {
    expect(UUID_RE.test("acfec746-79ab-4401-af2a-d579beb97229")).toBe(true);
  });

  it("matches uppercase UUIDs", () => {
    expect(UUID_RE.test("ACFEC746-79AB-4401-AF2A-D579BEB97229")).toBe(true);
  });

  it("rejects a comma-joined duplicate header value", () => {
    expect(UUID_RE.test("acfec746-79ab-4401-af2a-d579beb97229, org-b-uuid")).toBe(false);
  });

  it("rejects a non-UUID string", () => {
    expect(UUID_RE.test("not-a-uuid")).toBe(false);
  });
});
