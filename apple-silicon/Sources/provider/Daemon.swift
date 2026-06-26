// The on-device provider daemon. It assembles the real capabilities behind one arbiter,
// wraps them in the wire adapter + routes, and serves them over loopback HTTP. It runs
// bare-metal on the host -- it reaches the Neural Engine and the Swift-only Apple
// frameworks, which a Linux container cannot -- and is discovered by delightd's poll and
// reached over the mesh.
//
// Env: PROVIDER_PORT (default 8077), PROVIDER_CAPACITY (arbiter admission, default 2).

import Foundation
import Capabilities
import ProviderService

@main
struct Daemon {
    static func main() async throws {
        let env = ProcessInfo.processInfo.environment
        let port = UInt16(env["PROVIDER_PORT"] ?? "") ?? 8077
        let capacity = Int(env["PROVIDER_CAPACITY"] ?? "") ?? 2

        let router = Router(capabilities: [
            TranscriptionCapability(),
            SynthesisCapability(),
        ], capacity: capacity)
        let routes = Routes(service: ProviderService(router: router), roles: await router.roles)

        let server = try HTTPServer(port: port, handler: routes)
        let bound = try await server.start()
        FileHandle.standardError.write(Data("apple-silicon provider listening on 127.0.0.1:\(bound)\n".utf8))

        // park forever; the listener serves on its own queue until the process is signalled.
        while true {
            try await Task.sleep(for: .seconds(60 * 60))
        }
    }
}
