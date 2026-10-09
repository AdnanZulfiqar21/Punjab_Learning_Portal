import { expect, test } from "@playwright/test";

// P18.S2.T1 (HEADERS-01): pages carry defensive security headers.
test("pages carry security headers", async ({ request }) => {
  for (const path of ["/", "/learn", "/signin"]) {
    const res = await request.get(path);
    const h = res.headers();
    expect(h["x-content-type-options"], path).toBe("nosniff");
    expect(h["x-frame-options"], path).toBe("DENY");
    expect(h["referrer-policy"], path).toBe("strict-origin-when-cross-origin");
    expect(h["content-security-policy"], path).toContain("frame-ancestors 'none'");
    expect(h["content-security-policy"], path).toContain("object-src 'none'");
    expect(h["permissions-policy"], path).toContain("microphone=()");
  }
});
