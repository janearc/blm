// apple-silicon — the capability core.
//
// What this gives the fleet: direct, in-enclave access to the on-device models on
// Apple Silicon, with the heavy work shunted to the Neural Engine (ANE) where it
// runs at roughly 70:1 realtime — the same work we fought to get anywhere near 1:1
// off-device. Three capabilities front three Apple frameworks behind one uniform
// request/result:
//
//   • transcription — audio → text  (the on-device speech transcriber)
//   • synthesis     — text → audio  (speech synthesizer + Personal Voice)
//   • text          — text → text   (the on-device foundation model, "AFM") — next
//
// blm is optimized for Apple Silicon, and this is where that optimization lives.
// One arbiter fronts the shared chip (there is one ANE per host) so a machine never
// floods its own silicon.

import Foundation
import Speech
import AVFoundation

// MARK: - The uniform capability shape
//
// A single request/result carries text and/or a file path; each capability validates and
// interprets the fields it needs. (On the wire these become role-specific model.v1
// messages; in-process this struct pair is the erasure that lets one arbiter and one
// server front every capability the same way.)

public struct CapabilityRequest: Sendable {
    public var text: String?
    public var inputPath: String?
    public var params: [String: String]
    public init(text: String? = nil, inputPath: String? = nil, params: [String: String] = [:]) {
        self.text = text
        self.inputPath = inputPath
        self.params = params
    }
}

public struct CapabilityResult: Sendable {
    public var text: String?
    public var outputPath: String?
    public var detail: [String: String]
    public init(text: String? = nil, outputPath: String? = nil, detail: [String: String] = [:]) {
        self.text = text
        self.outputPath = outputPath
        self.detail = detail
    }
    public var summary: String {
        if let t = text { return "chars=\(t.count)" }
        if let p = outputPath { return "out=\((p as NSString).lastPathComponent)" }
        return "ok"
    }
}

public enum CapabilityError: Error, CustomStringConvertible {
    case badRequest(String)
    case unavailable(String)
    public var description: String {
        switch self {
        case .badRequest(let m): return "bad request: \(m)"
        case .unavailable(let m): return "unavailable: \(m)"
        }
    }
}

@available(macOS 26.0, *)
public protocol Capability: Sendable {
    var name: String { get }
    var role: String { get }
    func available() -> (ok: Bool, reason: String)
    func run(_ req: CapabilityRequest) async throws -> CapabilityResult
}

// MARK: - Transcription (audio → text), via SpeechTranscriber

@available(macOS 26.0, *)
public struct TranscriptionCapability: Capability {
    public let name = "transcription"
    public let role = "transcription"
    let locale: Locale
    public init(locale: Locale = Locale(identifier: "en-US")) { self.locale = locale }

    public func available() -> (ok: Bool, reason: String) { (true, "speech-transcriber") }

    public func run(_ req: CapabilityRequest) async throws -> CapabilityResult {
        guard let inputPath = req.inputPath else {
            throw CapabilityError.badRequest("transcription needs inputPath (an audio file)")
        }
        let url = URL(fileURLWithPath: inputPath)
        let transcriber = SpeechTranscriber(locale: locale, transcriptionOptions: [],
                                            reportingOptions: [], attributeOptions: [])
        if let r = try await AssetInventory.assetInstallationRequest(supporting: [transcriber]) {
            try await r.downloadAndInstall()
        }
        let analyzer = SpeechAnalyzer(modules: [transcriber])
        let audioFile = try AVAudioFile(forReading: url)
        let collector = Task { () -> String in
            var text = AttributedString()
            for try await result in transcriber.results { text += result.text }
            return String(text.characters)
        }
        if let last = try await analyzer.analyzeSequence(from: audioFile) {
            try await analyzer.finalizeAndFinish(through: last)
        } else {
            await analyzer.cancelAndFinishNow()
        }
        return CapabilityResult(text: try await collector.value, detail: ["role": role])
    }
}

// MARK: - Arbiter (bounded admission + single worker; BUSY when full)

@available(macOS 26.0, *)
func stamp() -> String {
    let f = DateFormatter(); f.dateFormat = "HH:mm:ss.SSS"; return f.string(from: Date())
}

@available(macOS 26.0, *)
public actor Arbiter {
    public enum Outcome: Sendable { case done(summary: String, wall: Double); case busy; case failed(String) }

    public let capacity: Int           // max admitted at once (running + queued)
    private var admitted = 0
    private var running = false
    private var waiters: [CheckedContinuation<Void, Never>] = []

    public init(capacity: Int) { self.capacity = capacity }

    public func submit(_ label: String, _ work: @Sendable @escaping () async throws -> CapabilityResult) async -> Outcome {
        guard admitted < capacity else {
            print("  [\(stamp())] BUSY   \(label)  (admitted \(admitted)/\(capacity))")
            return .busy
        }
        admitted += 1
        print("  [\(stamp())] ADMIT  \(label)  (admitted \(admitted)/\(capacity))")

        // single worker: park until the worker is free, so RUN events never overlap.
        while running {
            await withCheckedContinuation { (c: CheckedContinuation<Void, Never>) in waiters.append(c) }
        }
        running = true
        defer {
            running = false
            admitted -= 1
            if !waiters.isEmpty { waiters.removeFirst().resume() }
        }

        print("  [\(stamp())] RUN    \(label)")
        let t = Date()
        do {
            let res = try await work()
            let wall = Date().timeIntervalSince(t)
            print("  [\(stamp())] DONE   \(label)  \(res.summary) wall=\(String(format: "%.1f", wall))s")
            return .done(summary: res.summary, wall: wall)
        } catch {
            print("  [\(stamp())] FAIL   \(label)  \(error)")
            return .failed("\(error)")
        }
    }
}
