// HTTPServer -- a minimal HTTP/1.1 server over Network.framework, bound to loopback.
// One request per connection, Content-Length bodies (no chunked, no keep-alive): the
// provider serves a small fixed local API to the mesh, so this is deliberately tiny. It
// parses bytes into HTTPRequest, calls the HTTPHandler, and writes HTTPResponse.

import Foundation
import Network

@available(macOS 26.0, *)
public final class HTTPServer: @unchecked Sendable {
    private let listener: NWListener
    private let handler: any HTTPHandler
    private let queue = DispatchQueue(label: "apple-silicon.http", attributes: .concurrent)

    public init(port: UInt16, handler: any HTTPHandler) throws {
        let params = NWParameters.tcp
        params.allowLocalEndpointReuse = true
        params.requiredInterfaceType = .loopback
        let nwPort = NWEndpoint.Port(rawValue: port) ?? .any
        self.listener = try NWListener(using: params, on: nwPort)
        self.handler = handler
    }

    // start begins listening and returns the actually-bound port once ready, so a caller
    // can pass port 0 and learn the assigned port (used by the loopback test).
    public func start() async throws -> UInt16 {
        let handler = self.handler
        let queue = self.queue
        listener.newConnectionHandler = { connection in
            let box = ConnectionBox(connection)
            connection.start(queue: queue)
            Task { await Self.serve(box.value, handler: handler) }
        }
        let listener = self.listener
        return try await withCheckedThrowingContinuation { (cont: CheckedContinuation<UInt16, Error>) in
            let once = Once()
            listener.stateUpdateHandler = { state in
                switch state {
                case .ready:
                    if once.fire() { cont.resume(returning: listener.port?.rawValue ?? 0) }
                case .failed(let error):
                    if once.fire() { cont.resume(throwing: error) }
                default:
                    break
                }
            }
            listener.start(queue: queue)
        }
    }

    public func stop() {
        listener.cancel()
    }

    // serve handles one connection: read a request, dispatch it, write the response, close.
    private static func serve(_ connection: NWConnection, handler: any HTTPHandler) async {
        defer { connection.cancel() }
        do {
            let request = try await readRequest(connection)
            let response = await handler.handle(request)
            try await send(response, on: connection)
        } catch {
            try? await send(HTTPResponse(status: 400, body: Data(#"{"error":"bad request"}"#.utf8)), on: connection)
        }
    }

    private static func readRequest(_ connection: NWConnection) async throws -> HTTPRequest {
        var buffer = Data()
        while true {
            if let request = try parse(buffer) { return request }
            let chunk = try await receive(connection)
            if chunk.isEmpty { throw HTTPError.incomplete }   // EOF before a full request
            buffer.append(chunk)
        }
    }

    private static func receive(_ connection: NWConnection) async throws -> Data {
        try await withCheckedThrowingContinuation { (cont: CheckedContinuation<Data, Error>) in
            connection.receive(minimumIncompleteLength: 1, maximumLength: 64 * 1024) { data, _, _, error in
                if let error { cont.resume(throwing: error) } else { cont.resume(returning: data ?? Data()) }
            }
        }
    }

    private static func send(_ response: HTTPResponse, on connection: NWConnection) async throws {
        var head = "HTTP/1.1 \(response.status) \(reason(response.status))\r\n"
        head += "Content-Type: \(response.contentType)\r\n"
        head += "Content-Length: \(response.body.count)\r\n"
        head += "Connection: close\r\n\r\n"
        var data = Data(head.utf8)
        data.append(response.body)
        try await withCheckedThrowingContinuation { (cont: CheckedContinuation<Void, Error>) in
            connection.send(content: data, completion: .contentProcessed { error in
                if let error { cont.resume(throwing: error) } else { cont.resume() }
            })
        }
    }

    // parse returns a request once the buffer holds a full head + Content-Length body, or
    // nil if more bytes are needed.
    private static func parse(_ buffer: Data) throws -> HTTPRequest? {
        guard let headEnd = buffer.range(of: Data("\r\n\r\n".utf8)) else { return nil }
        guard let headText = String(data: buffer[..<headEnd.lowerBound], encoding: .utf8) else {
            throw HTTPError.malformed
        }
        let lines = headText.components(separatedBy: "\r\n")
        let requestLine = lines.first?.split(separator: " ") ?? []
        guard requestLine.count >= 2 else { throw HTTPError.malformed }
        let method = String(requestLine[0])
        let path = String(requestLine[1])

        var headers: [String: String] = [:]
        for line in lines.dropFirst() {
            guard let colon = line.firstIndex(of: ":") else { continue }
            let key = line[..<colon].trimmingCharacters(in: .whitespaces).lowercased()
            let value = line[line.index(after: colon)...].trimmingCharacters(in: .whitespaces)
            headers[key] = value
        }
        let contentLength = Int(headers["content-length"] ?? "0") ?? 0
        let bodyStart = headEnd.upperBound
        guard buffer.distance(from: bodyStart, to: buffer.endIndex) >= contentLength else { return nil }
        let bodyEnd = buffer.index(bodyStart, offsetBy: contentLength)
        return HTTPRequest(method: method, path: path, headers: headers, body: Data(buffer[bodyStart..<bodyEnd]))
    }

    private static func reason(_ status: Int) -> String {
        switch status {
        case 200: return "OK"
        case 400: return "Bad Request"
        case 404: return "Not Found"
        case 500: return "Internal Server Error"
        case 503: return "Service Unavailable"
        default: return "Status"
        }
    }
}

enum HTTPError: Error { case incomplete, malformed }

// ConnectionBox carries a non-Sendable NWConnection across the Task boundary. Network
// confines the connection to its own queue and we only touch it through the continuation
// bridges above, so the transfer is safe.
@available(macOS 26.0, *)
private struct ConnectionBox: @unchecked Sendable {
    let value: NWConnection
    init(_ value: NWConnection) { self.value = value }
}

// Once is a single-shot guard so the start() continuation resumes exactly once across the
// listener's state callbacks.
private final class Once: @unchecked Sendable {
    private let lock = NSLock()
    private var fired = false
    func fire() -> Bool {
        lock.lock(); defer { lock.unlock() }
        if fired { return false }
        fired = true
        return true
    }
}
