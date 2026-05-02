import AppKit

/// CandidateWindow displays AI-generated text results as a floating overlay.
/// Used by both the ;; trigger flow and the InputPanel flow.
/// Shows keyboard hints and auto-dismisses after a timeout.
class CandidateWindow {

    private var panel: NSPanel!
    private var contentStack: NSStackView!
    private var resultLabel: NSTextView!
    private var hintLabel: NSTextField!
    private var scrollView: NSScrollView!
    private var candidate: String = ""
    private var isVisible: Bool = false
    private var autoDismissTimer: Timer?
    private var localMonitor: Any?
    private var globalMonitor: Any?

    private let maxWidth: CGFloat = 500
    private let maxHeight: CGFloat = 200
    private let autoDismissInterval: TimeInterval = 10.0

    init() {
        setupPanel()
        setupMonitors()
    }

    // MARK: - Setup

    private func setupPanel() {
        panel = NSPanel(
            contentRect: NSRect(x: 0, y: 0, width: 400, height: 80),
            styleMask: [.nonactivatingPanel, .fullSizeContentView, .borderless],
            backing: .buffered,
            defer: false
        )

        panel.isFloatingPanel = true
        panel.level = .statusBar
        panel.hidesOnDeactivate = false
        panel.isMovableByWindowBackground = true
        panel.titleVisibility = .hidden
        panel.titlebarAppearsTransparent = true
        panel.isOpaque = false
        panel.backgroundColor = .clear
        panel.hasShadow = true
        panel.animationBehavior = .utilityWindow
        panel.collectionBehavior = [.canJoinAllSpaces, .stationary, .fullScreenAuxiliary]

        let contentView = panel.contentView!

        // Background with visual effect
        let visualEffect = NSVisualEffectView(frame: contentView.bounds)
        visualEffect.autoresizingMask = [.width, .height]
        visualEffect.material = .hudWindow
        visualEffect.state = .active
        visualEffect.blendingMode = .behindWindow
        visualEffect.wantsLayer = true
        visualEffect.layer?.cornerRadius = 10
        visualEffect.layer?.masksToBounds = true
        visualEffect.layer?.borderWidth = 0.5
        visualEffect.layer?.borderColor = NSColor.separatorColor.withAlphaComponent(0.3).cgColor
        contentView.addSubview(visualEffect)

        // Content stack
        contentStack = NSStackView(frame: .zero)
        contentStack.translatesAutoresizingMaskIntoConstraints = false
        contentStack.orientation = .vertical
        contentStack.alignment = .leading
        contentStack.spacing = 6
        contentView.addSubview(contentStack)

        // Scroll view for result text
        scrollView = NSScrollView(frame: .zero)
        scrollView.translatesAutoresizingMaskIntoConstraints = false
        scrollView.hasVerticalScroller = true
        scrollView.autohidesScrollers = true
        scrollView.borderType = .noBorder
        scrollView.drawsBackground = false

        resultLabel = NSTextView(frame: .zero)
        resultLabel.isEditable = false
        resultLabel.isSelectable = true
        resultLabel.font = NSFont.systemFont(ofSize: 14)
        resultLabel.textColor = .labelColor
        resultLabel.backgroundColor = .clear
        resultLabel.textContainerInset = NSSize(width: 2, height: 2)
        resultLabel.isVerticallyResizable = true
        resultLabel.isHorizontallyResizable = false
        resultLabel.textContainer?.widthTracksTextView = true
        resultLabel.textContainer?.lineFragmentPadding = 0
        scrollView.documentView = resultLabel

        contentStack.addArrangedSubview(scrollView)

        // Hint label
        hintLabel = NSTextField(labelWithString: "\u{21E5} Accept  \u{23CE} Dismiss  \u{238B} Cancel")
        hintLabel.font = NSFont.systemFont(ofSize: 11, weight: .regular)
        hintLabel.textColor = .tertiaryLabelColor
        hintLabel.translatesAutoresizingMaskIntoConstraints = false
        contentStack.addArrangedSubview(hintLabel)

        NSLayoutConstraint.activate([
            contentStack.topAnchor.constraint(equalTo: contentView.topAnchor, constant: 10),
            contentStack.bottomAnchor.constraint(equalTo: contentView.bottomAnchor, constant: -8),
            contentStack.leadingAnchor.constraint(equalTo: contentView.leadingAnchor, constant: 12),
            contentStack.trailingAnchor.constraint(equalTo: contentView.trailingAnchor, constant: -12),

            scrollView.widthAnchor.constraint(equalTo: contentStack.widthAnchor),
        ])
    }

    private func setupMonitors() {
        // Global monitor for key events when panel is visible
        globalMonitor = NSEvent.addGlobalMonitorForEvents(matching: .keyDown) { [weak self] event in
            guard let self = self, self.isVisible else { return }
            self.handleKeyEvent(event)
        }

        localMonitor = NSEvent.addLocalMonitorForEvents(matching: .keyDown) { [weak self] event in
            guard let self = self, self.isVisible else { return event }
            if self.handleKeyEvent(event) {
                return nil
            }
            return event
        }
    }

    @discardableResult
    private func handleKeyEvent(_ event: NSEvent) -> Bool {
        switch event.keyCode {
        case 48: // Tab - accept
            acceptCandidate()
            return true
        case 36, 76: // Return/Enter - dismiss
            hide()
            return true
        case 53: // Escape - cancel
            hide()
            return true
        default:
            return false
        }
    }

    // MARK: - Public Interface

    func showCandidate(_ text: String, isLoading: Bool = false) {
        candidate = text

        // Update text
        if isLoading {
            resultLabel.string = text
            resultLabel.textColor = .secondaryLabelColor
            hintLabel.stringValue = "Generating..."
        } else {
            resultLabel.string = text
            resultLabel.textColor = .labelColor
            hintLabel.stringValue = "\u{21E5} Accept  \u{23CE} Dismiss  \u{238B} Cancel"
        }

        // Calculate appropriate size
        let textSize = calculateTextSize(text)
        let panelWidth = min(max(textSize.width + 30, 200), maxWidth)
        let textHeight = min(max(textSize.height + 10, 30), maxHeight)
        let panelHeight = textHeight + 40 // text + hints + padding

        // Update scroll view height constraint
        for constraint in scrollView.constraints where constraint.firstAttribute == .height {
            scrollView.removeConstraint(constraint)
        }
        scrollView.heightAnchor.constraint(equalToConstant: textHeight).isActive = true

        // Position near cursor
        positionPanel(width: panelWidth, height: panelHeight)

        panel.setContentSize(NSSize(width: panelWidth, height: panelHeight))
        panel.orderFront(nil)
        isVisible = true

        // Reset auto-dismiss timer
        resetAutoDismissTimer()
    }

    func hide() {
        autoDismissTimer?.invalidate()
        autoDismissTimer = nil
        panel.orderOut(nil)
        isVisible = false
        candidate = ""
    }

    // MARK: - Private

    private func acceptCandidate() {
        guard !candidate.isEmpty else { hide(); return }

        // Save current clipboard content
        let savedClipboard = NSPasteboard.general.string(forType: .string)

        // Set candidate to clipboard
        NSPasteboard.general.clearContents()
        NSPasteboard.general.setString(candidate, forType: .string)

        hide()

        // Simulate Cmd+V
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) {
            let source = CGEventSource(stateID: .hidSystemState)

            let keyDown = CGEvent(keyboardEventSource: source, virtualKey: 0x09, keyDown: true)
            keyDown?.flags = .maskCommand
            let keyUp = CGEvent(keyboardEventSource: source, virtualKey: 0x09, keyDown: false)
            keyUp?.flags = .maskCommand

            keyDown?.post(tap: .cghidEventTap)
            keyUp?.post(tap: .cghidEventTap)

            // Restore clipboard after a delay
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
                if let saved = savedClipboard {
                    NSPasteboard.general.clearContents()
                    NSPasteboard.general.setString(saved, forType: .string)
                }
            }
        }
    }

    private func positionPanel(width: CGFloat, height: CGFloat) {
        guard let screen = NSScreen.main ?? NSScreen.screens.first else { return }

        let mouseLocation = NSEvent.mouseLocation
        let screenFrame = screen.visibleFrame

        // Position below and slightly right of cursor
        var x = mouseLocation.x - width / 2
        var y = mouseLocation.y - height - 25

        // Clamp to screen
        x = max(screenFrame.minX + 5, min(x, screenFrame.maxX - width - 5))
        y = max(screenFrame.minY + 5, min(y, screenFrame.maxY - height - 5))

        panel.setFrameOrigin(NSPoint(x: x, y: y))
    }

    private func calculateTextSize(_ text: String) -> NSSize {
        let attributes: [NSAttributedString.Key: Any] = [
            .font: NSFont.systemFont(ofSize: 14)
        ]
        let maxLayoutWidth = maxWidth - 30
        let boundingRect = (text as NSString).boundingRect(
            with: NSSize(width: maxLayoutWidth, height: CGFloat.greatestFiniteMagnitude),
            options: [.usesLineFragmentOrigin, .usesFontLeading],
            attributes: attributes
        )
        return NSSize(width: boundingRect.width + 10, height: boundingRect.height + 10)
    }

    private func resetAutoDismissTimer() {
        autoDismissTimer?.invalidate()
        autoDismissTimer = Timer.scheduledTimer(withTimeInterval: autoDismissInterval, repeats: false) { [weak self] _ in
            DispatchQueue.main.async {
                self?.hide()
            }
        }
    }

    deinit {
        if let monitor = localMonitor {
            NSEvent.removeMonitor(monitor)
        }
        if let monitor = globalMonitor {
            NSEvent.removeMonitor(monitor)
        }
        autoDismissTimer?.invalidate()
        panel?.orderOut(nil)
    }
}
