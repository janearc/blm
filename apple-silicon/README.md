# apple-silicon

The host-local, on-device capability provider for the fleet: one process per host
that fronts Apple's on-device frameworks behind a single arbiter (one front door to
the one Neural Engine per host), reached over the mesh. A pipeline never links Swift —
it reaches this through the good-citizen model client and the `model.v1` /
`sidecar.v1` descriptors.

**Library-first.** The `Capabilities` library is the core; the daemon and any shell
wrapper *call* it. There is no standalone CLI — this is a machine-first component.

## State (incremental)

- [x] **`Capabilities` library** — the single-arbiter (one bouncer per chip) +
  transcription/synthesis, with a `Router` that dispatches by role and sheds BUSY.
- [x] **Contracts wired** — `model.v1` `Invoke` messages + a Swift `Codable` emitter
  (`gen/swift`); the `ProviderService` adapter maps `InvokeRequest` ⟷ the capability core.
- [x] **HTTP transport** — a `Network.framework` daemon (`provider`) serving `POST
  /invoke` (model.v1 protojson) + `GET /health` over loopback; the thin executable wires
  the real capabilities behind the arbiter. Env: `PROVIDER_PORT` (8077),
  `PROVIDER_CAPACITY` (2).
- [ ] **Discovery** — announce a `sidecar.v1.SidecarDescriptor`; delightd's poll picks it up.
- [ ] **Text capability** — add the on-device foundation model (text→text) to the arbiter.

## Build

The Swift package is rooted at the **repo root** (one package, mirroring the single
`go.mod`):

```
swift build      # from the blm repo root
swift test
```

## Requirements

- **Apple Silicon + macOS 26** (the on-device frameworks).
- **Model assets are not automatically present.** The speech-transcriber assets
  download on first use (via `AssetInventory`), and a **Personal Voice** must be
  enrolled by the user in System Settings to be available at all. Having a Mac is not
  enough — expect a couple of downloads / a setup step.
