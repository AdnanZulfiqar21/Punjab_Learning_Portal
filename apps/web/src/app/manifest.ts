import type { MetadataRoute } from "next";

// P11.S4.T2 (PWA-01): installable web. BRAND-LOGO-01 (owner, 2026-11-10): icons are the Sirf Concepts mark (logo 2A,
// vector source in docs/brand).
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Sirf Concepts",
    short_name: "Sirf Concepts",
    description: "Class 11 and 12 Biology, Chemistry, Physics, Computer Science and Mathematics, organised by the official Punjab textbooks.",
    start_url: "/",
    scope: "/",
    display: "standalone",
    background_color: "#f7f8fa",
    theme_color: "#0b5d73",
    icons: [
      { src: "/icon-192.png", sizes: "192x192", type: "image/png" },
      { src: "/icon-512.png", sizes: "512x512", type: "image/png" },
      { src: "/icon-maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
  };
}
