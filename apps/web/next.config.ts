import type { NextConfig } from "next";

// P18.S2.T1 (HEADERS-01): defensive headers for every page. Cache Components and partial prefetching rule out
// nonce-based CSP, so this is the documented no-nonce policy (node_modules/next/dist/docs/01-app/02-guides/
// content-security-policy.md). Images may come from the runtime media origin, hence https: for img-src. TLS and HSTS
// are set at the edge, not here (plain-http localhost must keep working).
const isDev = process.env.NODE_ENV === "development";
const csp = [
  "default-src 'self'",
  // CODE-RUNNER-01: 'wasm-unsafe-eval' lets the lesson code runner compile Python's WebAssembly (served from /pyodide/);
  // it allows WebAssembly only, not JavaScript eval.
  `script-src 'self' 'unsafe-inline' 'wasm-unsafe-eval'${isDev ? " 'unsafe-eval'" : ""}`,
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' blob: data: https:",
  "font-src 'self' data:",
  "connect-src 'self'",
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
].join("; ");

const securityHeaders = [
  { key: "Content-Security-Policy", value: csp },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(self), microphone=(), geolocation=(), payment=()" },
];

const nextConfig: NextConfig = {
  async headers() {
    return [
      { source: "/(.*)", headers: securityHeaders },
      // P11.S4.T2 (PWA-01): the service worker script is never cached, so a fix reaches every installed copy at once.
      {
        source: "/sw.js",
        headers: [
          { key: "Content-Type", value: "application/javascript; charset=utf-8" },
          { key: "Cache-Control", value: "no-cache, no-store, must-revalidate" },
        ],
      },
    ];
  },
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
