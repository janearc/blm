// Routes is the provider's fixed local API, mapped onto ProviderService:
//
//   POST /invoke   decode model.v1 InvokeRequest (protojson), run it, return InvokeResponse
//   GET  /health   liveness + the roles this provider serves
//
// It is pure given the request bytes (no sockets), so the routing + status mapping is
// unit-tested directly; the HTTP server just hands it parsed requests.

import Foundation
import Contracts

@available(macOS 26.0, *)
public struct Routes: HTTPHandler {
    private let service: ProviderService
    private let roles: [String]

    public init(service: ProviderService, roles: [String]) {
        self.service = service
        self.roles = roles
    }

    public func handle(_ request: HTTPRequest) async -> HTTPResponse {
        switch (request.method, request.path) {
        case ("GET", "/health"):
            return Self.encode(200, Health(status: "ok", roles: roles))
        case ("POST", "/invoke"):
            return await invoke(request.body)
        default:
            return Self.encode(404, ErrorBody(error: "not found: \(request.method) \(request.path)"))
        }
    }

    private func invoke(_ body: Data) async -> HTTPResponse {
        let req: InvokeRequest
        do {
            req = try JSONDecoder().decode(InvokeRequest.self, from: body)
        } catch {
            return Self.encode(400, ErrorBody(error: "invalid InvokeRequest: \(error)"))
        }
        switch await service.handle(req) {
        case .success(let resp):
            return Self.encode(200, resp)
        case .failure(.busy):
            // retryable: the caller backs off and the bus redelivers; not an error result.
            return Self.encode(503, ErrorBody(error: "busy"))
        case .failure(.unavailable(let reason)):
            return Self.encode(503, ErrorBody(error: "unavailable: \(reason)"))
        case .failure(.failed(let message)):
            return Self.encode(500, ErrorBody(error: "failed: \(message)"))
        }
    }

    private struct Health: Encodable { let status: String; let roles: [String] }
    private struct ErrorBody: Encodable { let error: String }

    private static func encode<T: Encodable>(_ status: Int, _ value: T) -> HTTPResponse {
        let body = (try? JSONEncoder().encode(value)) ?? Data(#"{"error":"encode failed"}"#.utf8)
        return HTTPResponse(status: status, body: body)
    }
}
