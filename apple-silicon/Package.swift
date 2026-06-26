// swift-tools-version: 6.0
//
// apple-silicon — the host-local, on-device capability provider for the fleet: one
// process per host that fronts Apple's on-device frameworks (transcription, synthesis,
// and — next — text) and reaches the rest of the fleet over the mesh. It is
// library-first: the Capabilities library is the core, and the daemon and any shell
// wrapper call it.
import PackageDescription

let package = Package(
    name: "apple-silicon",
    platforms: [
        .macOS("26.0"),
    ],
    products: [
        .library(name: "Capabilities", targets: ["Capabilities"]),
    ],
    targets: [
        // The capability core: the bounded single-arbiter — one front door to the one
        // Neural Engine per host, so contended work is serialized to a single worker and
        // overflow is shed immediately as BUSY rather than flooding the chip — plus the
        // transcription and synthesis capabilities behind one uniform request/result.
        .target(
            name: "Capabilities",
            path: "Sources/Capabilities"
        ),
    ]
)
