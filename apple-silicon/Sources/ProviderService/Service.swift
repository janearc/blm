// ProviderService — the wire adapter for the on-device provider.
//
// It bridges the contract (model.v1 InvokeRequest/InvokeResponse, generated as Codable in
// Contracts) to the capability core (Capabilities): it maps the wire Role onto the role
// the router keys on, turns an InvokeRequest into a CapabilityRequest, runs it through the
// router, and maps the router's Outcome back to an InvokeResponse or a typed ServiceError.
// The HTTP transport (next step) calls handle() and maps ServiceError onto status codes;
// the mapping itself is tested here without the network.

import Foundation
import Capabilities
import Contracts

// ServiceError is the typed failure the transport maps to HTTP: .busy -> 429/503,
// .unavailable -> 503, .failed -> 500. "Busy" is not an error in the result sense -- the
// caller backs off and the bus redelivers -- but it is a distinct outcome the transport
// must signal, so it is modeled here.
public enum ServiceError: Error, Sendable {
    case busy
    case unavailable(String)
    case failed(String)
}

public struct ProviderService: Sendable {
    private let router: Router

    public init(router: Router) {
        self.router = router
    }

    // roleKey maps a wire Role to the role string the router keys on, or nil for a role
    // this provider does not serve. (Chat/completion -> "text" lands with the on-device
    // foundation-model capability.)
    static func roleKey(for role: Role) -> String? {
        switch role {
        case .roleTranscription: return "transcription"
        case .roleSpeechSynthesis: return "speech-synthesis"
        default: return nil
        }
    }

    // handle runs one wire request through the router and returns a wire response, or a
    // typed error the transport turns into a status code. Empty wire strings are proto3
    // defaults (absent), so they map to nil on the in-process request.
    public func handle(_ req: InvokeRequest) async -> Result<InvokeResponse, ServiceError> {
        guard let key = Self.roleKey(for: req.role) else {
            return .failure(.unavailable("unsupported role \"\(req.role.rawValue)\""))
        }
        let capReq = CapabilityRequest(
            text: req.text.isEmpty ? nil : req.text,
            inputPath: req.inputPath.isEmpty ? nil : req.inputPath,
            params: req.params
        )
        switch await router.invoke(role: key, capReq) {
        case .ok(let result):
            return .success(InvokeResponse(
                text: result.text ?? "",
                outputPath: result.outputPath ?? "",
                detail: result.detail
            ))
        case .busy:
            return .failure(.busy)
        case .unavailable(let reason):
            return .failure(.unavailable(reason))
        case .failed(let msg):
            return .failure(.failed(msg))
        }
    }
}
