# apple-silicon

The host-local, on-device capability provider for the fleet: one process per host
that fronts Apple's on-device frameworks behind a single arbiter (one front door to
the one Neural Engine per host), reached over the mesh. A pipeline never links Swift —
it reaches this through the good-citizen model client and the `model.v1` /
`sidecar.v1` descriptors.

**Library-first.** The `Capabilities` library is the core; the daemon and any shell
wrapper *call* it. There is no standalone CLI — this is a machine-first component.

## State (incremental)

- [x] **`Capabilities` library builds.** The bounded single-arbiter plus the
  transcription (audio→text) and synthesis (text→audio, +Personal Voice) capabilities,
  behind one uniform request/result.
- [ ] **Serving daemon.** An executable that imports `Capabilities` and serves
  `model.v1` operations as protojson over local HTTP, plus `/health`. (model.v1 gains
  the operation messages — a contract bump — and a small Swift emitter generates the
  matching `Codable` types.)
- [ ] **Discovery.** Announce a `sidecar.v1.SidecarDescriptor`, register with delightd,
  emit the observability heartbeat.
- [ ] **Text capability.** Add the on-device foundation model (text→text) to the same
  arbiter.

## Build

```
swift build
```

## Requirements

- **Apple Silicon + macOS 26** (the on-device frameworks).
- **Model assets are not automatically present.** The speech-transcriber assets
  download on first use (via `AssetInventory`), and a **Personal Voice** must be
  enrolled by the user in System Settings to be available at all. Having a Mac is not
  enough — expect a couple of downloads / a setup step.
