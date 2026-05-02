import AppKit
import Carbon

class HotkeyManager {

    var onTrigger: ((String) -> Void)?

    private var eventTap: CFMachPort?
    private var runLoopSource: CFRunLoopSource?
    private var triggerBuffer = ""
    private let triggerSequence = ";"

    func start() {
        // Create event tap for key down events
        let eventMask = (1 << CGEventType.keyDown.rawValue)

        // Callback for event tap
        let callback: CGEventTapCallBack = { proxy, type, event, refcon in
            guard let refcon = refcon else { return Unmanaged.passRetained(event) }
            let manager = Unmanaged<HotkeyManager>.fromOpaque(refcon).takeUnretainedValue()
            manager.handleEvent(proxy: proxy, type: type, event: event)
            return Unmanaged.passRetained(event)
        }

        // Create event tap
        eventTap = CGEvent.tapCreate(
            tap: .cgSessionEventTap,
            place: .headInsertEventTap,
            options: .defaultTap,
            eventsOfInterest: CGEventMask(eventMask),
            callback: callback,
            userInfo: Unmanaged.passUnretained(self).toOpaque()
        )

        guard let eventTap = eventTap else {
            print("Failed to create event tap. Check Accessibility permissions.")
            return
        }

        // Create run loop source
        runLoopSource = CFMachPortCreateRunLoopSource(kCFAllocatorDefault, eventTap, 0)

        // Add to run loop
        CFRunLoopAddSource(CFRunLoopGetCurrent(), runLoopSource, .commonModes)

        // Enable the tap
        CGEvent.tapEnable(tap: eventTap, enable: true)

        print("HotkeyManager started")
    }

    func stop() {
        if let eventTap = eventTap {
            CGEvent.tapEnable(tap: eventTap, enable: false)
        }
        if let runLoopSource = runLoopSource {
            CFRunLoopRemoveSource(CFRunLoopGetCurrent(), runLoopSource, .commonModes)
        }
        eventTap = nil
        runLoopSource = nil
        triggerBuffer = ""
        print("HotkeyManager stopped")
    }

    private func handleEvent(proxy: CGEventTapProxy, type: CGEventType, event: CGEvent) {
        guard type == .keyDown else { return }

        let keyCode = event.getIntegerValueField(.keyboardEventKeycode)

        // Get the character
        var actualStringLength: Int = 0
        var unicodeString = [UniChar](repeating: 0, count: 4)
        event.keyboardGetUnicodeString(maxStringLength: 4, actualStringLength: &actualStringLength, unicodeString: &unicodeString)

        guard actualStringLength > 0 else { return }
        let char = String(utf16CodeUnits: unicodeString, count: actualStringLength)

        // Check for trigger sequence (;;)
        if char == ";" {
            triggerBuffer += char
            if triggerBuffer.count >= 2 && triggerBuffer.hasSuffix(";;") {
                // Trigger detected, clear buffer and wait for input
                triggerBuffer = ""
                // The actual text will come from the clipboard or we'll need to track typing
                // For MVP, we'll use a simpler approach: user selects text and presses Cmd+Shift+M
            }
        } else if keyCode == 49 { // Space key
            // Check if we have a partial trigger
            if triggerBuffer.hasSuffix(";") {
                // This is "; " - potential trigger
                triggerBuffer = ""
            } else {
                triggerBuffer = ""
            }
        } else {
            // Any other key clears the buffer
            triggerBuffer = ""
        }
    }

    deinit {
        stop()
    }
}
