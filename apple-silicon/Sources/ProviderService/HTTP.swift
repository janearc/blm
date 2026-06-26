// The tiny HTTP surface the provider serves. Deliberately minimal -- a fixed local API,
// so this is just enough to route a method + path with a body and write a response. The
// HTTP server (Network.framework) parses bytes into HTTPRequest and writes HTTPResponse;
// the routing in between is pure and testable without a socket.

import Foundation

public struct HTTPRequest: Sendable {
    public let method: String
    public let path: String
    public let headers: [String: String]
    public let body: Data
    public init(method: String, path: String, headers: [String: String] = [:], body: Data = Data()) {
        self.method = method
        self.path = path
        self.headers = headers
        self.body = body
    }
}

public struct HTTPResponse: Sendable {
    public var status: Int
    public var contentType: String
    public var body: Data
    public init(status: Int, body: Data, contentType: String = "application/json") {
        self.status = status
        self.body = body
        self.contentType = contentType
    }
}

// HTTPHandler turns one request into one response. Routes implements it over
// ProviderService; the server feeds it parsed requests.
public protocol HTTPHandler: Sendable {
    func handle(_ request: HTTPRequest) async -> HTTPResponse
}
