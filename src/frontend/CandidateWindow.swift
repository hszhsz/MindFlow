import AppKit

class CandidateWindow {

    private var panel: NSPanel?
    private var label: NSTextField?
    private var candidate: String = ""
    private var isVisible: Bool = false

    init() {
        setupPanel()
    }

    private func setupPanel() {
        // Create a floating panel
        panel = NSPanel(
            contentRect: NSRect(x: 0, y: 0, width: 400, height: 40),
            styleMask: [.nonactivatingPanel, .titled, .fullSizeContentView],
            backing: .buffered,
            defer: false
        )

        panel?.isFloatingPanel = true
        panel?.level = .floating
        panel?.hidesOnDeactivate = false
        panel?.isMovableByWindowBackground = true
        panel?.titleVisibility = .hidden
        panel?.backgroundColor = NSColor.windowBackgroundColor.withAlphaComponent(0.95)
        panel?.hasShadow = true

        // Create label
        label = NSTextField(labelWithString: "")
        label?.font = NSFont.systemFont(ofSize: 14)
        label?.textColor = NSColor.labelColor
        label?.backgroundColor = .clear
        label?.isBordered = false
        label?.isEditable = false
        label?.lineBreakMode = .byTruncatingTail
        label?.translatesAutoresizingMaskIntoConstraints = false

        if let contentView = panel?.contentView {
            contentView.addSubview(label!)

            NSLayoutConstraint.activate([
                label!.leadingAnchor.constraint(equalTo: contentView.leadingAnchor, constant: 12),
                label!.trailingAnchor.constraint(equalTo: contentView.trailingAnchor, constant: -12),
                label!.centerYAnchor.constraint(equalTo: contentView.centerYAnchor)
            ])
        }

        // Setup key monitor for Tab/Enter
        NSEvent.addLocalMonitorForEvents(matching: .keyDown) { [weak self] event in
            guard self?.isVisible == true else { return event }

            if event.keyCode == 48 { // Tab
                self?.acceptCandidate()
                return nil
            } else if event.keyCode == 36 || event.keyCode == 76 { // Enter or Return
                self?.hide()
                return nil
            } else if event.keyCode == 53 { // Escape
                self?.hide()
                return nil
            }

            return event
        }
    }

    func showCandidate(_ text: String) {
        candidate = text
        label?.stringValue = "Tab: " + text

        // Position near cursor
        if let screen = NSScreen.main {
            let mouseLocation = NSEvent.mouseLocation
            let x = min(max(mouseLocation.x - 200, screen.visibleFrame.minX), screen.visibleFrame.maxX - 400)
            let y = max(mouseLocation.y - 60, screen.visibleFrame.minY)

            panel?.setFrameOrigin(NSPoint(x: x, y: y))
        }

        panel?.orderFront(nil)
        isVisible = true
    }

    func hide() {
        panel?.orderOut(nil)
        isVisible = false
        candidate = ""
    }

    private func acceptCandidate() {
        // Copy candidate to clipboard
        let pasteboard = NSPasteboard.general
        pasteboard.clearContents()
        pasteboard.setString(candidate, forType: .string)

        // Simulate Cmd+V to paste
        hide()

        // Small delay to let the panel hide
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) {
            self.pasteClipboard()
        }
    }

    private func pasteClipboard() {
        // Create and post Cmd+V key event
        let source = CGEventSource(stateID: .hidSystemState)

        let keyDown = CGEvent(keyboardEventSource: source, virtualKey: 0x09, keyDown: true) // V key
        keyDown?.flags = .maskCommand

        let keyUp = CGEvent(keyboardEventSource: source, virtualKey: 0x09, keyDown: false) // V key
        keyUp?.flags = .maskCommand

        keyDown?.post(tap: .cghidEventTap)
        keyUp?.post(tap: .cghidEventTap)
    }

    deinit {
        panel?.orderOut(nil)
    }
}
