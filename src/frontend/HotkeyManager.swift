import AppKit
import Carbon

/// HotkeyManager monitors global keystrokes to detect the `;;` trigger sequence.
/// After detecting `;;`, it collects subsequent keystrokes into a buffer until
/// Return/Enter is pressed, then sends the buffered text to the backend.
/// Escape or focus change cancels the collection.
class HotkeyManager {

    weak var candidateWindow: CandidateWindow?

    private var eventTap: CFMachPort?
    private var runLoopSource: CFRunLoopSource?

    // State machine for ;; detection and text collection
    private enum State {
        case idle                // Waiting for first ';'
        case firstSemicolon     // Got one ';', waiting for second
        case collecting         // Got ';;', collecting text until Enter
    }

    private var state: State = .idle
    private var collectionBuffer: String = ""
    private var isRunning: Bool = false

    // Track active application to detect focus changes
    private var activeAppObserver: NSObjectProtocol?
    private var activeApp: NSRunningApplication?

    // MARK: - Public Interface

    func start() {
        guard !isRunning else { return }

        let eventMask: CGEventMask = (1 << CGEventType.keyDown.rawValue) | (1 << CGEventType.flagsChanged.rawValue)

        guard let tap = CGEvent.tapCreate(
            tap: .cgSessionEventTap,
            place: .headInsertEventTap,
            options: .defaultTap,
            eventsOfInterest: eventMask,
            callback: { proxy, type, event, refcon -> Unmanaged<CGEvent>? in
                guard let refcon = refcon else { return Unmanaged.passRetained(event) }
                let manager = Unmanaged<HotkeyManager>.fromOpaque(refcon).takeUnretainedValue()
                return manager.handleEvent(proxy: proxy, type: type, event: event)
            },
            userInfo: Unmanaged.passUnretained(self).toOpaque()
        ) else {
            print("[HotkeyManager] Failed to create event tap. Check Accessibility permissions.")
            return
        }

        eventTap = tap
        runLoopSource = CFMachPortCreateRunLoopSource(kCFAllocatorDefault, tap, 0)
        CFRunLoopAddSource(CFRunLoopGetMain(), runLoopSource, .commonModes)
        CGEvent.tapEnable(tap: tap, enable: true)

        // Observe application focus changes to cancel collection
        activeApp = NSWorkspace.shared.frontmostApplication
        activeAppObserver = NSWorkspace.shared.notificationCenter.addObserver(
            forName: NSWorkspace.didActivateApplicationNotification,
            object: nil,
            queue: .main
        ) { [weak self] notification in
            guard let self = self else { return }
            let newApp = notification.userInfo?[NSWorkspace.applicationUserInfoKey] as? NSRunningApplication
            if self.state == .collecting && newApp?.processIdentifier != self.activeApp?.processIdentifier {
                self.cancelCollection()
            }
            self.activeApp = newApp
        }

        isRunning = true
        print("[HotkeyManager] Started - listening for ;; trigger")
    }

    func stop() {
        guard isRunning else { return }

        if let tap = eventTap {
            CGEvent.tapEnable(tap: tap, enable: false)
        }
        if let source = runLoopSource {
            CFRunLoopRemoveSource(CFRunLoopGetMain(), source, .commonModes)
        }
        if let observer = activeAppObserver {
            NSWorkspace.shared.notificationCenter.removeObserver(observer)
        }

        eventTap = nil
        runLoopSource = nil
        activeAppObserver = nil
        state = .idle
        collectionBuffer = ""
        isRunning = false
        print("[HotkeyManager] Stopped")
    }

    var enabled: Bool {
        get { isRunning }
        set {
            if newValue && !isRunning { start() }
            else if !newValue && isRunning { stop() }
        }
    }

    // MARK: - Event Handling

    private func handleEvent(proxy: CGEventTapProxy, type: CGEventType, event: CGEvent) -> Unmanaged<CGEvent>? {
        // If the tap is disabled by the system, re-enable it
        if type == .tapDisabledByTimeout || type == .tapDisabledByUserInput {
            if let tap = eventTap {
                CGEvent.tapEnable(tap: tap, enable: true)
            }
            return Unmanaged.passRetained(event)
        }

        guard type == .keyDown else {
            return Unmanaged.passRetained(event)
        }

        let keyCode = event.getIntegerValueField(.keyboardEventKeycode)
        let flags = event.flags

        // Get the typed character
        var actualLength: Int = 0
        var unicodeBuffer = [UniChar](repeating: 0, count: 4)
        event.keyboardGetUnicodeString(maxStringLength: 4, actualStringLength: &actualLength, unicodeString: &unicodeBuffer)

        let character: String
        if actualLength > 0 {
            character = String(utf16CodeUnits: unicodeBuffer, count: actualLength)
        } else {
            character = ""
        }

        switch state {
        case .idle:
            if character == ";" {
                state = .firstSemicolon
            }
            return Unmanaged.passRetained(event)

        case .firstSemicolon:
            if character == ";" {
                // ;; detected - transition to collecting mode
                state = .collecting
                collectionBuffer = ""
                activeApp = NSWorkspace.shared.frontmostApplication
                print("[HotkeyManager] ;; trigger detected, collecting input...")
                // We let the second ';' pass through; the user will see ';;' in their text.
                // The backend result will replace it later.
                return Unmanaged.passRetained(event)
            } else {
                // Not a second semicolon, reset
                state = .idle
                return Unmanaged.passRetained(event)
            }

        case .collecting:
            return handleCollectingState(keyCode: keyCode, character: character, flags: flags, event: event)
        }
    }

    private func handleCollectingState(keyCode: Int64, character: String, flags: CGEventFlags, event: CGEvent) -> Unmanaged<CGEvent>? {
        // Escape cancels
        if keyCode == 53 {
            cancelCollection()
            return Unmanaged.passRetained(event)
        }

        // Return/Enter triggers generation
        if keyCode == 36 || keyCode == 76 {
            let text = collectionBuffer.trimmingCharacters(in: .whitespacesAndNewlines)
            state = .idle
            collectionBuffer = ""

            if !text.isEmpty {
                triggerGeneration(text: text)
                // Suppress the Enter key so it doesn't insert a newline
                return nil
            }
            return Unmanaged.passRetained(event)
        }

        // Backspace removes last character from buffer
        if keyCode == 51 {
            if !collectionBuffer.isEmpty {
                collectionBuffer.removeLast()
            } else {
                // Buffer empty, cancel collection
                cancelCollection()
            }
            return Unmanaged.passRetained(event)
        }

        // Tab - ignore but don't cancel
        if keyCode == 48 {
            return Unmanaged.passRetained(event)
        }

        // Modifier keys alone don't affect buffer
        if flags.contains(.maskCommand) || flags.contains(.maskControl) {
            // Allow Cmd/Ctrl shortcuts to pass through but cancel collection
            cancelCollection()
            return Unmanaged.passRetained(event)
        }

        // Regular character - add to buffer
        if !character.isEmpty && character != "\r" && character != "\n" {
            collectionBuffer += character
        }

        return Unmanaged.passRetained(event)
    }

    // MARK: - Actions

    private func cancelCollection() {
        state = .idle
        collectionBuffer = ""
        print("[HotkeyManager] Collection cancelled")
    }

    private func triggerGeneration(text: String) {
        print("[HotkeyManager] Triggering generation for: \(text)")

        // Delete the typed text (;;+text) from the active field
        let deleteCount = text.count + 2 // +2 for the ';;'
        deleteTypedCharacters(count: deleteCount)

        // Show loading in candidate window
        DispatchQueue.main.async { [weak self] in
            self?.candidateWindow?.showCandidate("Generating...", isLoading: true)
        }

        // Call backend
        Task {
            do {
                let response = try await APIClient.shared.generate(text: text)
                await MainActor.run { [weak self] in
                    self?.candidateWindow?.showCandidate(response.candidate, isLoading: false)
                }
            } catch {
                await MainActor.run { [weak self] in
                    self?.candidateWindow?.showCandidate("Error: \(error.localizedDescription)", isLoading: false)
                }
            }
        }
    }

    /// Deletes the specified number of characters by simulating backspace key presses
    private func deleteTypedCharacters(count: Int) {
        let source = CGEventSource(stateID: .hidSystemState)

        for _ in 0..<count {
            let keyDown = CGEvent(keyboardEventSource: source, virtualKey: 51, keyDown: true) // Backspace
            let keyUp = CGEvent(keyboardEventSource: source, virtualKey: 51, keyDown: false)
            keyDown?.post(tap: .cghidEventTap)
            keyUp?.post(tap: .cghidEventTap)
        }
    }

    deinit {
        stop()
    }
}
