// SynthesisCapability — text → speech audio file, via AVSpeechSynthesizer.
//
// The fun, hard one. It prefers the user's on-device **Personal Voice** when one is
// enrolled and authorized — this is the macOS *accessibility* Personal Voice the user
// records in Settings. We can't create one programmatically (it's locked to enrollment);
// we can only use it if it already exists and the user has authorized access (the
// liarbird upgrade: your story in your voice). It falls back to a system voice otherwise
// — honest gating, never silently wrong. It writes to
// an audio FILE (not the speakers) by assembling the synthesizer's PCM buffers, the same
// artifact shape the rest of the fleet produces.
//
// Two real problems live here: Personal Voice needs async authorization and may not be
// enrolled at all; and AVSpeechSynthesizer wants the main actor and delivers its buffers
// through a callback we have to bridge to async. Both are handled on @MainActor so no
// non-Sendable AV type ever crosses an actor boundary.

import Foundation
import AVFoundation

@available(macOS 26.0, *)
public struct SynthesisCapability: Capability {
    public let name = "synthesis"
    public let role = "speech-synthesis"
    public init() {}

    public func available() -> (ok: Bool, reason: String) {
        // a system voice always exists; report whether a personal voice is installed so
        // the truth (your-voice vs robot) is visible up front.
        let hasPersonal = AVSpeechSynthesisVoice.speechVoices()
            .contains { $0.voiceTraits.contains(.isPersonalVoice) }
        return (true, hasPersonal ? "av-speech (+personal voice installed)"
                                  : "av-speech (system voices only)")
    }

    public func run(_ req: CapabilityRequest) async throws -> CapabilityResult {
        guard let text = req.text,
              !text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            throw CapabilityError.badRequest("synthesis needs non-empty text")
        }
        let outPath = req.params["out"]
            ?? (NSTemporaryDirectory() + "swift-speech-\(UUID().uuidString).caf")
        // everything AV stays on the main actor; only a Sendable dict comes back out.
        let detail = try await Self.speak(text: text, to: URL(fileURLWithPath: outPath))
        return CapabilityResult(outputPath: outPath, detail: detail)
    }

    @MainActor
    static func speak(text: String, to url: URL) async throws -> [String: String] {
        // prefer an authorized Personal Voice; else a system voice.
        let auth = await withCheckedContinuation {
            (c: CheckedContinuation<AVSpeechSynthesizer.PersonalVoiceAuthorizationStatus, Never>) in
            AVSpeechSynthesizer.requestPersonalVoiceAuthorization { c.resume(returning: $0) }
        }
        // NOTE: en-US is hardcoded. Mixed-language ("code-switching") input keeps biting
        // us and we have no good way to handle it here yet — one utterance gets one voice
        // in one language.
        var voice = AVSpeechSynthesisVoice(language: "en-US")
        var personal = false
        if auth == .authorized,
           let pv = AVSpeechSynthesisVoice.speechVoices()
                       .first(where: { $0.voiceTraits.contains(.isPersonalVoice) }) {
            voice = pv
            personal = true
        }

        let synth = AVSpeechSynthesizer()
        let utt = AVSpeechUtterance(string: text)
        utt.voice = voice

        // a reference box so the buffer callback can hold the file + completion latch
        // without capturing mutable locals.
        final class Sink { var file: AVAudioFile?; var done = false }
        let sink = Sink()

        try await withCheckedThrowingContinuation { (cont: CheckedContinuation<Void, Error>) in
            synth.write(utt) { (buffer: AVAudioBuffer) in
                guard let pcm = buffer as? AVAudioPCMBuffer else { return }
                if pcm.frameLength == 0 {                 // empty buffer = synthesis done
                    if !sink.done { sink.done = true; cont.resume() }
                    return
                }
                do {
                    if sink.file == nil {
                        sink.file = try AVAudioFile(forWriting: url, settings: pcm.format.settings)
                    }
                    try sink.file?.write(from: pcm)
                } catch {
                    if !sink.done { sink.done = true; cont.resume(throwing: error) }
                }
            }
            _ = synth   // keep the synthesizer alive until the callback latch fires
        }

        return ["role": "speech-synthesis",
                "voice": voice?.name ?? "system-default",
                "personal": String(personal)]
    }
}
