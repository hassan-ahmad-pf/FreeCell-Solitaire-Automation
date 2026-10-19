# `wda/` — signed WebDriverAgent for this FreeCell phone

Pre-built, pre-signed runner so `scripts/wda.sh` needs no `WDA_PRODUCTS` and
nothing under `/tmp` (that path is what died last time).

```
wda/
├── WebDriverAgentRunner_iphoneos27.0-arm64.xctestrun
└── Debug-iphoneos/
    ├── WebDriverAgentLib.framework/
    └── WebDriverAgentRunner-Runner.app/
```

`__TESTROOT__` in the `.xctestrun` is this folder. Do not flatten it.

- Bundle: `com.hassanahmad.WebDriverAgentRunner.xctrunner`
- Team: `253XD74VB6` (a free Apple ID: its provisioning profiles last 7 days)
- Device: `00008130-00010D283A31001C` (iPhone 15 Pro Max)
- Phone must be **unlocked** and **online** when you start `wda.sh` (cert re-trust).
- Leave `./scripts/wda.sh running`. Do not restart it after the suite goes offline.

## Renewal

When the profile here and in `log/wda-build` both have under a day left
(`WDA_RENEW_HOURS`, default 24), `wda.sh` rebuilds Appium's WebDriverAgent
(`WDA_SOURCE`, default `~/.appium/.../appium-webdriveragent`) with
`xcodebuild -allowProvisioningUpdates` into `log/wda-build` and starts that.
It does the same once if the phone refuses the profile at launch.
`./scripts/wda.sh renew` re-signs on demand. Xcode must be signed in to the
team's Apple ID (Xcode → Settings → Accounts).

The certificate itself lasts until Sep 2027, but after a re-sign iOS may
refuse the runner until it is trusted again: Settings → General → VPN &
Device Management → the Apple Development entry → Verify App / Trust, with
the phone online. `wda.sh` says so when that happens. A paid Apple
Developer team issues one-year profiles: set `WDA_TEAM` (and `WDA_BUNDLE`
if that team needs its own ID) to use one.
