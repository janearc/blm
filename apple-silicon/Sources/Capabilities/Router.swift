// Router — the capability router (the inside of the on-device daemon).
//
// It owns the set of capabilities and the shared arbiter, and routes one call to the
// capability registered for a role, runs it through the arbiter (one bouncer per chip),
// and returns a transport-agnostic Outcome. The HTTP/protojson layer wraps this: it maps
// the model.v1 InvokeRequest onto CapabilityRequest, the role enum onto the role key, and
// this Outcome onto status codes. No transport and no contracts here -- pure dispatch, so
// it is unit-testable without the network or the bus.

import Foundation

@available(macOS 26.0, *)
public actor Router {
    // Outcome is transport-agnostic. The HTTP layer maps it: .ok -> 200, .busy -> 429/503,
    // .unavailable -> 503, .failed -> 500. "Busy" is not an error -- the caller backs off
    // and the bus redelivers; completion is the caller's bento to own, never this layer's.
    public enum Outcome: Sendable {
        case ok(CapabilityResult)
        case busy
        case unavailable(reason: String)
        case failed(String)
    }

    private let arbiter: Arbiter
    private let byRole: [String: any Capability]

    // Capabilities are keyed by their `role`. capacity is the arbiter's admission bound
    // (running + queued) -- the single front door to the one Neural Engine on this host.
    // Two capabilities sharing a role is a configuration error caught in review (last wins).
    public init(capabilities: [any Capability], capacity: Int) {
        self.arbiter = Arbiter(capacity: capacity)
        var m: [String: any Capability] = [:]
        for c in capabilities {
            m[c.role] = c
        }
        self.byRole = m
    }

    // roles the router can serve -- the surface a descriptor / health view reports.
    public var roles: [String] { byRole.keys.sorted() }

    // invoke routes one request to the capability for `role`, gating on the capability's
    // own honest availability check before admitting it to the arbiter.
    public func invoke(role: String, _ req: CapabilityRequest) async -> Outcome {
        guard let cap = byRole[role] else {
            return .unavailable(reason: "no capability for role \"\(role)\"")
        }
        let (ok, reason) = cap.available()
        guard ok else {
            return .unavailable(reason: reason)
        }
        let outcome = await arbiter.submit(role) { try await cap.run(req) }
        switch outcome {
        case .done(let result, _):
            return .ok(result)
        case .busy:
            return .busy
        case .failed(let msg):
            return .failed(msg)
        }
    }
}
