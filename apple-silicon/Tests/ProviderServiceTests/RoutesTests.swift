import XCTest
import Foundation
import Capabilities
import Contracts
@testable import ProviderService

@available(macOS 26.0, *)
private struct FakeCapability: Capabilities.Capability {
    let name: String
    let role: String
    var result: CapabilityResult = CapabilityResult(text: "ok")
    func available() -> (ok: Bool, reason: String) { (true, "fake") }
    func run(_ req: CapabilityRequest) async throws -> CapabilityResult { result }
}

@available(macOS 26.0, *)
final class RoutesTests: XCTestCase {
    private func routes(_ caps: [any Capabilities.Capability]) async -> Routes {
        let router = Router(capabilities: caps, capacity: 2)
        return Routes(service: ProviderService(router: router), roles: await router.roles)
    }

    func testHealthReportsRoles() async {
        let r = await routes([FakeCapability(name: "t", role: "transcription")])
        let resp = await r.handle(HTTPRequest(method: "GET", path: "/health"))
        XCTAssertEqual(resp.status, 200)
        let body = try! JSONSerialization.jsonObject(with: resp.body) as! [String: Any]
        XCTAssertEqual(body["status"] as? String, "ok")
        XCTAssertEqual(body["roles"] as? [String], ["transcription"])
    }

    func testInvokeRoutesAndReturnsResponse() async {
        let r = await routes([FakeCapability(name: "t", role: "transcription",
                                             result: CapabilityResult(text: "the words"))])
        let body = try! JSONEncoder().encode(InvokeRequest(role: .roleTranscription, inputPath: "/a.m4a"))
        let resp = await r.handle(HTTPRequest(method: "POST", path: "/invoke", body: body))
        XCTAssertEqual(resp.status, 200)
        let decoded = try! JSONDecoder().decode(InvokeResponse.self, from: resp.body)
        XCTAssertEqual(decoded.text, "the words")
    }

    func testInvalidBodyIsRejected() async {
        let r = await routes([FakeCapability(name: "t", role: "transcription")])
        let resp = await r.handle(HTTPRequest(method: "POST", path: "/invoke", body: Data("not json".utf8)))
        XCTAssertEqual(resp.status, 400)
    }

    func testUnsupportedRoleIsUnavailable() async {
        let r = await routes([FakeCapability(name: "t", role: "transcription")])
        let body = try! JSONEncoder().encode(InvokeRequest(role: .roleEmbedding))
        let resp = await r.handle(HTTPRequest(method: "POST", path: "/invoke", body: body))
        XCTAssertEqual(resp.status, 503)
    }

    func testUnknownPathIsNotFound() async {
        let r = await routes([FakeCapability(name: "t", role: "transcription")])
        let resp = await r.handle(HTTPRequest(method: "GET", path: "/nope"))
        XCTAssertEqual(resp.status, 404)
    }
}
