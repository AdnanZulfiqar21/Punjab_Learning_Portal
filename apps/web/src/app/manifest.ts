import type { MetadataRoute } from "next";

// P11.S4.T2 (PWA-01): installable web. The icons are a provisional text mark until the owner supplies a brand mark.
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Punjab Learning Portal",
    short_name: "Learning Portal",
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
