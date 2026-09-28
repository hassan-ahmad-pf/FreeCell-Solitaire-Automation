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
- Team: `253XD74VB6`
- Device: `00008130-00010D283A31001C` (iPhone 15 Pro Max)
- Phone must be **unlocked** and **online** when you start `wda.sh` (cert re-trust).
- Leave `./scripts/wda.sh` running. Do not restart it after the suite goes offline.
