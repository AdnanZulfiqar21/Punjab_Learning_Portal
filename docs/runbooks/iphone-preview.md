# iPhone preview build

This prepares an internal iOS build. It does not sign the app, associate an Expo project, or show that a phone ran it.

The three variants in `apps/mobile/app.config.ts` stay as they are: development `pk.punjablearningportal.student.dev`, preview `pk.punjablearningportal.student.preview`, production `pk.punjablearningportal.student`. Those identifiers are still provisional (B11). `eas.json` does not turn on a development client, because `expo-dev-client` is not a dependency.

## Owner steps

Run these in `apps/mobile`. Enter the Apple and Expo passwords and the 2FA codes in the terminal yourself. Do not paste them into a chat.

```bash
npx eas-cli@latest login
npx eas-cli@latest init
```

`eas init` writes the Expo project id into the app config. That association is not done until this command succeeds.

A preview build refuses to start unless `PORTAL_API_ORIGIN` is set. Use the computer's address on the same Wi-Fi as the phone, not `127.0.0.1` (that address is the phone itself). On 15 October 2026 the computer's Wi-Fi address was `172.20.10.2`, and `http://172.20.10.2:8100/healthz` answered from that computer. Recheck the address before a build. The API must listen on `0.0.0.0:8100`. If the phone's browser cannot open `/healthz`, allow inbound TCP 8100 in Windows Firewall for the private network.

PowerShell:

```powershell
$env:PORTAL_API_ORIGIN = "http://172.20.10.2:8100"
npx eas-cli@latest build --platform ios --profile preview
```

EAS will ask for the Apple Developer account during credential setup. Accepting that prompt is what creates the signing certificate and the provisioning profile. Until a build page shows a finished iOS artifact, signing and on-device testing are not done (B07, B09).

A production build must get an `https` origin. The preview exception for local networking is not on the production variant.
