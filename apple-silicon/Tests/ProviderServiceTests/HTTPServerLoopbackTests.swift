import XCTest
import Foundation
@testable import ProviderService

// EchoHandler exercises the real socket path without capabilities: it echoes a POST body
// and answers /health, so the test proves parse -> dispatch -> response over a live port.
@available(macOS 26.0, *)
private struct EchoHandler: HTTPHandler {
    func handle(_ request: HTTPRequest) async -> HTTPResponse {
        if request.path == "/health" {
            return HTTPResponse(status: 200, body: Data(#"{"status":"ok"}"#.utf8))
        }
        return HTTPResponse(status: 200, body: request.body)
    }
}

@available(macOS 26.0, *)
final class HTTPServerLoopbackTests: XCTestCase {
    func testPostAndHealthOverRealSocket() async throws {
        let server = try HTTPServer(port: 0, handler: EchoHandler())
        let port = try await server.start()
        defer { server.stop() }

        // a real POST over the loopback socket; the body must round-trip.
        var post = URLRequest(url: URL(string: "http://127.0.0.1:\(port)/invoke")!)
        post.httpMethod = "POST"
        post.httpBody = Data("hello over the wire".utf8)
        let (data, resp) = try await URLSession.shared.data(for: post)
        XCTAssertEqual((resp as? HTTPURLResponse)?.statusCode, 200)
        XCTAssertEqual(String(data: data, encoding: .utf8), "hello over the wire")

        // and a real GET /health.
        let (hdata, hresp) = try await URLSession.shared.data(from: URL(string: "http://127.0.0.1:\(port)/health")!)
        XCTAssertEqual((hresp as? HTTPURLResponse)?.statusCode, 200)
        XCTAssertTrue(String(data: hdata, encoding: .utf8)?.contains("ok") ?? false)
    }
}
