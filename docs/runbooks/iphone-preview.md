# iPhone preview build

This prepares an internal iOS build. It does not sign the app, associate an Expo project, or show that a phone ran it.

The three variants in `apps/mobile/app.config.ts` stay as they are: development `pk.punjablearningportal.student.dev`, preview `pk.punjablearningportal.student.preview`, production `pk.punjablearningportal.student`. Those identifiers are still provisional (B11). `eas.json` does not turn on a development client, because `expo-dev-client` is not a dependency.

## Owner steps

Run these in `apps/mobile`. Enter the Apple and Expo passwords and the 2FA codes in the terminal yourself. Do not paste them into a chat.

```bash
npx eas-cli@latest login
npx eas-cli@latest init
npx eas-cli@latest device:create
```

The linked Expo project is `@desirly/punjab-learning-portal` (`0e89f0cd-7ca1-429a-8265-1a29a2dc999a`). `app.config.ts` keeps `extra.eas.projectId` and adds `variant` and `apiOrigin`. Do not create a second project. Register this iPhone with `device:create` before the build so the provisioning profile includes it. No Apple team is linked to the Expo account yet, so this command is what starts that link.

The preview profile sets `"environment": "preview"` and keeps `APP_VARIANT=preview`. A PowerShell variable is not sent to the cloud builder. Store the origin in the preview EAS environment after login:

```bash
npx eas-cli@latest env:set --name PORTAL_API_ORIGIN --value http://172.20.10.2:8100 --environment preview --visibility plaintext
```

Use the computer's address on the same Wi-Fi as the phone, not `127.0.0.1` (that address is the phone itself). On 15 October 2026 the Wi-Fi address was `172.20.10.2`. The API listened on `0.0.0.0:8100`, and both `http://172.20.10.2:8100/healthz` and `http://172.20.10.2:8100/readyz` answered from that computer. Recheck the address before `env:set`. Readiness on that date reported migration `f8a21c6d4e90` against the disposable database `portal_integrations_view_test`. Do not migrate the `portal` database for this preview.

Open this URL in Safari on the phone: `http://172.20.10.2:8100/readyz`. If it does not load, allow inbound TCP 8100 on the private profile only:

```powershell
New-NetFirewallRule -DisplayName "Punjab Portal API TCP 8100" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8100 -Profile Private -RemoteAddress LocalSubnet
```

`eas build` reads the app config once with only `APP_VARIANT` before it can download the EAS variable. Set the same origin in that terminal as well, then start the build. Choose Desirly Limited (`6FV87T5UMF`) and include the registered iPhone.

```powershell
$env:PORTAL_API_ORIGIN = "http://172.20.10.2:8100"
npx eas-cli@latest build --platform ios --profile preview
```

EAS will ask for the Apple Developer account during credential setup. Accepting that prompt is what creates the signing certificate and the provisioning profile. Until a build page shows a finished iOS artifact, signing and on-device testing are not done (B07, B09).

There is no `expo-updates` dependency, update channel, or development client. Restarting the API or Metro does not change the installed app. The finished preview installed on 15 October 2026 is build `1` of version `0.1.0`, bundle `pk.punjablearningportal.student.preview`, internal distribution, git `7d1be98`, build id `0be43c26-284c-4aa5-b083-9595b27babce`. iOS build `2` finished on 17 October 2026: id `1bcfc70b-9b5c-4410-b5b8-604ba23a6602`, git `c9028c7e128653062b36cd75775e90a660be5927`, same bundle and team, same registered iPhone. Install page: https://expo.dev/accounts/desirly/projects/punjab-learning-portal/builds/1bcfc70b-9b5c-4410-b5b8-604ba23a6602. The phone has not been checked after that install. Settings shows the variant, build number, source revision and API origin. It does not show a token.

**Build 3 (Class XI Biology Chapter 1 pilot, 18 October 2026).** Built from branch `feat/bio-xi-ch1-pilot` with `ios.buildNumber` `3`, same bundle, team and registered iPhone, `PORTAL_API_ORIGIN=http://172.20.10.2:8100` (the Wi-Fi address checked on 18 October). It carries the Learn chooser (class, then group), the compact chapter screen, the topic reader with the English | Roman Urdu control, native renderer 2 (comparison cards, `model3d` turntables) and the dashboard screen. EAS build id `d1a71a11-94ff-453c-86ed-9c9175f331db`, git `b9f3652126509e42b99bdc4006a1b983aeae915b`, started 18 October 2026 03:24 UTC, install page https://expo.dev/accounts/desirly/projects/punjab-learning-portal/builds/d1a71a11-94ff-453c-86ed-9c9175f331db. The build finished at 03:30 UTC on 18 October 2026 (artifact `.ipa` on that page). The phone has not been checked after this build. Before opening the pilot on the phone, run the API on `0.0.0.0:8100` against the `portal` database (where the Chapter 1 drafts were imported) and sign in on the phone as `studio-author@example.com` to see the drafts; a learner account sees the honest unpublished state. Claude did not run build 3 on the physical phone.

**Build 4 (Lecture view).** `expo-video` is a native module, so the English | Roman Urdu | Lecture control plays video only from build 4 onwards; build 3 shows the Lecture choice as "coming". Build 4: EAS id `37fdf223-8d09-4cfd-893a-ce529a37d218`, git `67a673d18d6232bb4515201ca321331de559fbc4` (the head of #237 as merged), `ios.buildNumber` 4, finished 18 October 2026 08:09 local; install page https://expo.dev/accounts/desirly/projects/punjab-learning-portal/builds/37fdf223-8d09-4cfd-893a-ce529a37d218. The API must run with `PORTAL_LECTURE_MEDIA_DIR` pointing at the owner's Chapter 1 videos folder (`.claude/launch.json` entry `api-lan`) for the Lecture view to play. The owner confirmed on 18 October 2026 that build 3 runs on the iPhone (Roman Urdu reader, topic 1.2).

**Build 5 (API address on the device, #239).** EAS id `7d74e5c3-b6d4-4a17-b034-9a924ca54be3`, git `bccf8ed`, `ios.buildNumber` 5, finished 18 October 2026 08:30 local, baked origin `http://192.168.1.162:8100` (the laptop on the home Wi-Fi; build 4's `172.20.10.2` was the iPhone hotspot address and stopped working when the laptop changed network). From this build, Settings → This installation → **API address on this device** changes the origin without a new build (preview and development variants only; production never reads it). Install page https://expo.dev/accounts/desirly/projects/punjab-learning-portal/builds/7d74e5c3-b6d4-4a17-b034-9a924ca54be3.

**Build 6 (Lecture view shows only the lecture, #240).** EAS id `db267715-4f56-4662-b2b6-3fce59355eb7`, git `e1184b9`, `ios.buildNumber` 6, finished 18 October 2026 13:59 local, baked origin `http://192.168.1.162:8100`; install page https://expo.dev/accounts/desirly/projects/punjab-learning-portal/builds/db267715-4f56-4662-b2b6-3fce59355eb7. The stream route no longer holds a request-scoped database session for the length of a video (that had saturated the development API's pool while the phone played lectures). Docker Desktop's engine hung for about an hour on 18 October (Postgres unreachable, API 503/offline on the phone); it recovered after a restart by the owner.

**Build 7 (21 October 2026, main after #353 to #360).** EAS id `0c7b2347-63d9-47c0-978d-b75af96f112e`, git `c55310c4` (`main` at `28da7ab6` plus the `ios.buildNumber` 7 bump), started 12:06 and finished 12:11 local on 21 October 2026; install page https://expo.dev/accounts/desirly/projects/punjab-learning-portal/builds/0c7b2347-63d9-47c0-978d-b75af96f112e. Same bundle, team and registered iPhone. The preview EAS environment's `PORTAL_API_ORIGIN` still held the hotspot address `http://172.20.10.2:8100`; it was set to the laptop's home Wi-Fi address `http://192.168.1.162:8100` (checked that day; `/healthz` answered on it) before the build. New on the phone since build 6: written tests ask the learner to confirm the question numbering on a page that answers several parts (REGION-MAP-01) and show which pages have an area marked on the website. The development database `portal` is at migration `8d2f6b1e7a30`. Claude did not run build 7 on the physical phone.

**Build 8 (21 October 2026, main after #364 to #366).** EAS id `534f4860-1019-46d3-88bb-e028de619fff`, git `eb9f854a` (`main` at `c905d2f3` plus the `ios.buildNumber` 8 bump), started 16:16 and finished 16:21 local on 21 October 2026; install page https://expo.dev/accounts/desirly/projects/punjab-learning-portal/builds/534f4860-1019-46d3-88bb-e028de619fff. Same bundle, team and registered iPhone; baked origin `http://192.168.1.162:8100` (unchanged since build 7, checked that day). New since build 7: tapping a lesson figure opens it full screen with pinch-to-zoom, drag, double-tap and -/Reset/+ buttons (DIAGRAM-ZOOM-01, #364), and tip callouts, used for the green diagram explanations, are green as on the web (#366). Before the build, `main` passed the token check, mobile `tsc`, `expo lint` and the 62 host tests. Claude did not run build 8 on the physical phone.

A production build must get an `https` origin. The preview exception for local networking is not on the production variant.
