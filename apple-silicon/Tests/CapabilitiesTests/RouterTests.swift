import XCTest
@testable import Capabilities

// A test double: a capability with no real framework behind it, so the router/arbiter
// dispatch can be tested without the Neural Engine. `hold`, when set, parks the worker
// inside run() until a test opens the gate -- used to occupy the single slot for the
// busy test.
@available(macOS 26.0, *)
private struct FakeCapability: Capability {
    let name: String
    let role: String
    var ok: Bool = true
    var reason: String = "fake-ready"
    var result: CapabilityResult = CapabilityResult(text: "ok")
    var hold: Gate? = nil

    func available() -> (ok: Bool, reason: String) { (ok, reason) }
    func run(_ req: CapabilityRequest) async throws -> CapabilityResult {
        if let hold {
            await hold.enterAndWait()
        }
        return result
    }
}

// Gate lets a test hold the arbiter's single worker: the capability signals when it has
// entered run() (so the slot is occupied), then parks until the test opens it.
@available(macOS 26.0, *)
private actor Gate {
    private var entered = false
    private var opened = false
    private var enteredWaiters: [CheckedContinuation<Void, Never>] = []
    private var openWaiters: [CheckedContinuation<Void, Never>] = []

    func enterAndWait() async {
        entered = true
        enteredWaiters.forEach { $0.resume() }
        enteredWaiters.removeAll()
        if opened { return }
        await withCheckedContinuation { openWaiters.append($0) }
    }

    func waitUntilEntered() async {
        if entered { return }
        await withCheckedContinuation { enteredWaiters.append($0) }
    }

    func open() {
        opened = true
        openWaiters.forEach { $0.resume() }
        openWaiters.removeAll()
    }
}

@available(macOS 26.0, *)
final class RouterTests: XCTestCase {
    func testSuccessRoutesToCapabilityAndReturnsResult() async {
        let cap = FakeCapability(name: "t", role: "transcription",
                                 result: CapabilityResult(text: "hello world"))
        let router = Router(capabilities: [cap], capacity: 2)
        let outcome = await router.invoke(role: "transcription", CapabilityRequest())
        guard case .ok(let result) = outcome else { return XCTFail("expected .ok, got \(outcome)") }
        XCTAssertEqual(result.text, "hello world")
    }

    func testUnknownRoleIsUnavailable() async {
        let router = Router(capabilities: [], capacity: 2)
        let outcome = await router.invoke(role: "nope", CapabilityRequest())
        guard case .unavailable = outcome else { return XCTFail("expected .unavailable, got \(outcome)") }
    }

    func testUnavailableCapabilityIsGatedBeforeAdmission() async {
        let cap = FakeCapability(name: "s", role: "synthesis", ok: false, reason: "no model installed")
        let router = Router(capabilities: [cap], capacity: 2)
        let outcome = await router.invoke(role: "synthesis", CapabilityRequest())
        guard case .unavailable(let reason) = outcome else { return XCTFail("expected .unavailable, got \(outcome)") }
        XCTAssertEqual(reason, "no model installed")
    }

    func testSecondCallIsBusyWhileTheSingleSlotIsHeld() async {
        let gate = Gate()
        let slow = FakeCapability(name: "x", role: "slow", hold: gate)
        let router = Router(capabilities: [slow], capacity: 1)

        // occupy the single slot; wait until the worker is actually running.
        let first = Task { await router.invoke(role: "slow", CapabilityRequest()) }
        await gate.waitUntilEntered()

        // a second call must be shed immediately as busy.
        let second = await router.invoke(role: "slow", CapabilityRequest())
        guard case .busy = second else { return XCTFail("expected .busy, got \(second)") }

        // release the worker; the first call completes normally.
        await gate.open()
        let firstOutcome = await first.value
        guard case .ok = firstOutcome else { return XCTFail("expected first .ok, got \(firstOutcome)") }
    }

    func testRolesReportsRegisteredCapabilities() async {
        let router = Router(capabilities: [
            FakeCapability(name: "t", role: "transcription"),
            FakeCapability(name: "s", role: "synthesis"),
        ], capacity: 2)
        let roles = await router.roles
        XCTAssertEqual(roles, ["synthesis", "transcription"])
    }
}
