import XCTest
import Capabilities
import Contracts
@testable import ProviderService

// A test double standing in for a real capability, so the wire mapping can be tested
// without the Neural Engine.
@available(macOS 26.0, *)
private struct FakeCapability: Capabilities.Capability {
    let name: String
    let role: String
    var result: CapabilityResult = CapabilityResult(text: "ok")
    func available() -> (ok: Bool, reason: String) { (true, "fake-ready") }
    func run(_ req: CapabilityRequest) async throws -> CapabilityResult { result }
}

@available(macOS 26.0, *)
final class ServiceTests: XCTestCase {
    func testTranscriptionRequestMapsThroughToResponse() async {
        let cap = FakeCapability(name: "t", role: "transcription",
                                 result: CapabilityResult(text: "the transcript", detail: ["role": "transcription"]))
        let service = ProviderService(router: Router(capabilities: [cap], capacity: 2))

        let req = InvokeRequest(role: .roleTranscription, inputPath: "/tmp/a.m4a")
        let outcome = await service.handle(req)

        guard case .success(let resp) = outcome else { return XCTFail("expected success, got \(outcome)") }
        XCTAssertEqual(resp.text, "the transcript")
        XCTAssertEqual(resp.detail["role"], "transcription")
    }

    func testSynthesisRoleMapsToTheSynthesisCapability() async {
        let cap = FakeCapability(name: "s", role: "speech-synthesis",
                                 result: CapabilityResult(outputPath: "/tmp/out.caf"))
        let service = ProviderService(router: Router(capabilities: [cap], capacity: 2))

        let outcome = await service.handle(InvokeRequest(role: .roleSpeechSynthesis, text: "hello"))

        guard case .success(let resp) = outcome else { return XCTFail("expected success, got \(outcome)") }
        XCTAssertEqual(resp.outputPath, "/tmp/out.caf")
    }

    func testUnsupportedRoleIsUnavailable() async {
        let cap = FakeCapability(name: "t", role: "transcription")
        let service = ProviderService(router: Router(capabilities: [cap], capacity: 2))

        // embedding is a valid wire role but one this provider does not serve.
        let outcome = await service.handle(InvokeRequest(role: .roleEmbedding))

        guard case .failure(.unavailable) = outcome else { return XCTFail("expected .unavailable, got \(outcome)") }
    }

    func testEmptyWireStringsBecomeNilOnTheCapabilityRequest() async {
        // a capability that echoes whether it saw text/inputPath, proving "" -> nil.
        let cap = EchoCapability(role: "transcription")
        let service = ProviderService(router: Router(capabilities: [cap], capacity: 2))

        let outcome = await service.handle(InvokeRequest(role: .roleTranscription, inputPath: "/tmp/a.m4a"))
        guard case .success(let resp) = outcome else { return XCTFail("expected success, got \(outcome)") }
        // text was "" on the wire -> nil in -> "saw text: false"; inputPath was set -> true.
        XCTAssertEqual(resp.detail["sawText"], "false")
        XCTAssertEqual(resp.detail["sawInputPath"], "true")
    }
}

// EchoCapability reports which optional fields it actually received, to prove the
// empty-string -> nil mapping.
@available(macOS 26.0, *)
private struct EchoCapability: Capabilities.Capability {
    let name = "echo"
    let role: String
    func available() -> (ok: Bool, reason: String) { (true, "echo") }
    func run(_ req: CapabilityRequest) async throws -> CapabilityResult {
        CapabilityResult(text: "ok", detail: [
            "sawText": String(req.text != nil),
            "sawInputPath": String(req.inputPath != nil),
        ])
    }
}
