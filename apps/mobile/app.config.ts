// Three native variants with distinct identities (roadmap §5.5, P03.S3.T2). A development or preview binary is never
// re-pointed to production. Bundle identifiers are PROVISIONAL until the owner settles the product name (BLOCKERS B11)
// and must be final before the first store submission.
import type { ConfigContext, ExpoConfig } from "expo/config";

type Variant = "development" | "preview" | "production";
const variant = (process.env.APP_VARIANT ?? "development") as Variant;
if (!["development", "preview", "production"].includes(variant)) {
  throw new Error(`Unknown APP_VARIANT "${variant}"`);
}

const BASE_ID = "pk.punjablearningportal.student";
const IDS: Record<Variant, string> = {
  development: `${BASE_ID}.dev`,
  preview: `${BASE_ID}.preview`,
  production: BASE_ID,
};
const NAMES: Record<Variant, string> = {
  development: "Punjab Portal (Dev)",
  preview: "Punjab Portal (Preview)",
  production: "Punjab Learning Portal",
};

// The API origin is variant configuration. Production and preview builds must receive it explicitly; a production
// build can never fall back to a development address.
function apiOrigin(): string {
  const origin = process.env.PORTAL_API_ORIGIN;
  if (origin) return origin;
  if (variant !== "development") {
    throw new Error(`PORTAL_API_ORIGIN must be set for the ${variant} variant`);
  }
  // Development default for iOS simulator/web. Android emulators must set PORTAL_API_ORIGIN=http://10.0.2.2:8100.
  return "http://127.0.0.1:8100";
}

export default ({ config }: ConfigContext): ExpoConfig => ({
  ...config,
  name: NAMES[variant],
  slug: "punjab-learning-portal",
  version: "0.1.0",
  orientation: "portrait",
  scheme: variant === "production" ? "punjabportal" : `punjabportal-${variant}`,
  userInterfaceStyle: "automatic",
  icon: "./assets/images/icon.png",
  ios: {
    ...config.ios,
    bundleIdentifier: IDS[variant],
    icon: "./assets/expo.icon",
  },
  android: {
    ...config.android,
    package: IDS[variant].replaceAll("-", "_"),
    adaptiveIcon: {
      backgroundColor: "#E3F1F5",
      foregroundImage: "./assets/images/android-icon-foreground.png",
      backgroundImage: "./assets/images/android-icon-background.png",
      monochromeImage: "./assets/images/android-icon-monochrome.png",
    },
    predictiveBackGestureEnabled: false,
  },
  web: { output: "static", favicon: "./assets/images/favicon.png" },
  plugins: [
    "expo-router",
    ["expo-splash-screen", { backgroundColor: "#0B5D73", image: "./assets/images/splash-icon.png", imageWidth: 76 }],
  ],
  experiments: { typedRoutes: true, reactCompiler: true },
  extra: { variant, apiOrigin: apiOrigin() },
});
