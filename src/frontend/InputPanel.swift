import AppKit

/// InputPanel is a compact floating NSPanel opened by Cmd+Shift+M.
/// The user types their intent, presses Enter to send to backend,
/// and sees the AI-generated result with Copy/Insert buttons.
class InputPanel: NSObject, NSTextFieldDelegate {

    weak var candidateWindow: CandidateWindow?

    private var panel: NSPanel!
    private var inputField: NSTextField!
    private var resultTextView: NSScrollView!
    private var resultText: NSTextView!
    private var loadingIndicator: NSProgressIndicator!
    private var copyButton: NSButton!
    private var insertButton: NSButton!
    private var hintLabel: NSTextField!
    private var resultContainer: NSView!

    private let panelWidth: CGFloat = 480
    private let inputHeight: CGFloat = 36
    private let resultHeight: CGFloat = 160
    private let padding: CGFloat = 12

    private var currentResult: String = ""

    override init() {
        super.init()
        setupPanel()
    }

    // MARK: - Setup

    private func setupPanel() {
        let initialHeight = inputHeight + padding * 3 + 20 // input + hints + padding
        panel = NSPanel(
            contentRect: NSRect(x: 0, y: 0, width: panelWidth, height: initialHeight),
            styleMask: [.nonactivatingPanel, .fullSizeContentView, .borderless],
            backing: .buffered,
            defer: false
        )

        panel.isFloatingPanel = true
        panel.level = .floating
        panel.hidesOnDeactivate = false
        panel.isMovableByWindowBackground = true
        panel.titleVisibility = .hidden
        panel.titlebarAppearsTransparent = true
        panel.isOpaque = false
        panel.backgroundColor = .clear
        panel.hasShadow = true
        panel.animationBehavior = .utilityWindow
        panel.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary]

        // Visual effect background
        let visualEffect = NSVisualEffectView(frame: panel.contentView!.bounds)
        visualEffect.autoresizingMask = [.width, .height]
        visualEffect.material = .popover
        visualEffect.state = .active
        visualEffect.blendingMode = .behindWindow
        visualEffect.wantsLayer = true
        visualEffect.layer?.cornerRadius = 12
        visualEffect.layer?.masksToBounds = true
        panel.contentView?.addSubview(visualEffect)

        let contentView = panel.contentView!

        // Input field
        inputField = NSTextField(frame: .zero)
        inputField.translatesAutoresizingMaskIntoConstraints = false
        inputField.placeholderString = "Type your intent... (e.g., project delayed one week, notify client)"
        inputField.font = NSFont.systemFont(ofSize: 15)
        inputField.isBordered = false
        inputField.backgroundColor = .clear
        inputField.focusRingType = .none
        inputField.delegate = self
        inputField.cell?.sendsActionOnEndEditing = false
        inputField.target = self
        inputField.action = #selector(inputFieldAction(_:))
        contentView.addSubview(inputField)

        // Hint label
        hintLabel = NSTextField(labelWithString: "Enter to generate  |  Esc to dismiss")
        hintLabel.translatesAutoresizingMaskIntoConstraints = false
        hintLabel.font = NSFont.systemFont(ofSize: 11)
        hintLabel.textColor = .tertiaryLabelColor
        contentView.addSubview(hintLabel)

        // Result container (hidden initially)
        resultContainer = NSView(frame: .zero)
        resultContainer.translatesAutoresizingMaskIntoConstraints = false
        resultContainer.isHidden = true
        contentView.addSubview(resultContainer)

        // Separator
        let separator = NSBox(frame: .zero)
        separator.translatesAutoresizingMaskIntoConstraints = false
        separator.boxType = .separator
        resultContainer.addSubview(separator)

        // Result text view in scroll view
        resultTextView = NSScrollView(frame: .zero)
        resultTextView.translatesAutoresizingMaskIntoConstraints = false
        resultTextView.hasVerticalScroller = true
        resultTextView.autohidesScrollers = true
        resultTextView.borderType = .noBorder
        resultTextView.drawsBackground = false

        resultText = NSTextView(frame: .zero)
        resultText.isEditable = false
        resultText.isSelectable = true
        resultText.font = NSFont.systemFont(ofSize: 14)
        resultText.textColor = .labelColor
        resultText.backgroundColor = .clear
        resultText.textContainerInset = NSSize(width: 4, height: 4)
        resultText.isVerticallyResizable = true
        resultText.isHorizontallyResizable = false
        resultText.textContainer?.widthTracksTextView = true
        resultTextView.documentView = resultText
        resultContainer.addSubview(resultTextView)

        // Loading indicator
        loadingIndicator = NSProgressIndicator(frame: .zero)
        loadingIndicator.translatesAutoresizingMaskIntoConstraints = false
        loadingIndicator.style = .spinning
        loadingIndicator.controlSize = .small
        loadingIndicator.isHidden = true
        resultContainer.addSubview(loadingIndicator)

        // Button stack
        let buttonStack = NSStackView(frame: .zero)
        buttonStack.translatesAutoresizingMaskIntoConstraints = false
        buttonStack.orientation = .horizontal
        buttonStack.spacing = 8
        buttonStack.alignment = .centerY
        resultContainer.addSubview(buttonStack)

        copyButton = NSButton(title: "Copy", target: self, action: #selector(copyResult))
        copyButton.bezelStyle = .rounded
        copyButton.controlSize = .small
        copyButton.font = NSFont.systemFont(ofSize: 12)
        buttonStack.addArrangedSubview(copyButton)

        insertButton = NSButton(title: "Insert (Tab)", target: self, action: #selector(insertResult))
        insertButton.bezelStyle = .rounded
        insertButton.controlSize = .small
        insertButton.font = NSFont.systemFont(ofSize: 12)
        insertButton.keyEquivalent = "\t"
        buttonStack.addArrangedSubview(insertButton)

        // Layout constraints
        NSLayoutConstraint.activate([
            // Input field
            inputField.topAnchor.constraint(equalTo: contentView.topAnchor, constant: padding),
            inputField.leadingAnchor.constraint(equalTo: contentView.leadingAnchor, constant: padding),
            inputField.trailingAnchor.constraint(equalTo: contentView.trailingAnchor, constant: -padding),
            inputField.heightAnchor.constraint(equalToConstant: inputHeight),

            // Hint label
            hintLabel.topAnchor.constraint(equalTo: inputField.bottomAnchor, constant: 4),
            hintLabel.leadingAnchor.constraint(equalTo: contentView.leadingAnchor, constant: padding),

            // Result container
            resultContainer.topAnchor.constraint(equalTo: hintLabel.bottomAnchor, constant: 8),
            resultContainer.leadingAnchor.constraint(equalTo: contentView.leadingAnchor),
            resultContainer.trailingAnchor.constraint(equalTo: contentView.trailingAnchor),
            resultContainer.bottomAnchor.constraint(equalTo: contentView.bottomAnchor),

            // Separator
            separator.topAnchor.constraint(equalTo: resultContainer.topAnchor),
            separator.leadingAnchor.constraint(equalTo: resultContainer.leadingAnchor, constant: padding),
            separator.trailingAnchor.constraint(equalTo: resultContainer.trailingAnchor, constant: -padding),

            // Result text view
            resultTextView.topAnchor.constraint(equalTo: separator.bottomAnchor, constant: 8),
            resultTextView.leadingAnchor.constraint(equalTo: resultContainer.leadingAnchor, constant: padding),
            resultTextView.trailingAnchor.constraint(equalTo: resultContainer.trailingAnchor, constant: -padding),
            resultTextView.heightAnchor.constraint(equalToConstant: resultHeight),

            // Loading indicator
            loadingIndicator.centerXAnchor.constraint(equalTo: resultTextView.centerXAnchor),
            loadingIndicator.centerYAnchor.constraint(equalTo: resultTextView.centerYAnchor),

            // Button stack
            buttonStack.topAnchor.constraint(equalTo: resultTextView.bottomAnchor, constant: 8),
            buttonStack.trailingAnchor.constraint(equalTo: resultContainer.trailingAnchor, constant: -padding),
            buttonStack.bottomAnchor.constraint(equalTo: resultContainer.bottomAnchor, constant: -padding),
        ])

        // Keyboard monitor for Escape
        NSEvent.addLocalMonitorForEvents(matching: .keyDown) { [weak self] event in
            guard let self = self, self.panel.isVisible else { return event }
            if event.keyCode == 53 { // Escape
                self.dismiss()
                return nil
            }
            return event
        }
    }

    // MARK: - Show / Dismiss

    func show() {
        // Reset state
        inputField.stringValue = ""
        resultText.string = ""
        resultContainer.isHidden = true
        loadingIndicator.isHidden = true
        currentResult = ""

        // Resize to compact form
        let compactHeight = inputHeight + padding * 3 + 20
        var frame = panel.frame
        frame.size.height = compactHeight
        panel.setFrame(frame, display: false)

        // Position near cursor or center of screen
        positionPanel()

        panel.makeKeyAndOrderFront(nil)
        panel.makeFirstResponder(inputField)

        // Bring to front
        NSApp.activate(ignoringOtherApps: true)
    }

    func dismiss() {
        panel.orderOut(nil)
        currentResult = ""
    }

    private func positionPanel() {
        guard let screen = NSScreen.main ?? NSScreen.screens.first else { return }

        let mouseLocation = NSEvent.mouseLocation
        let screenFrame = screen.visibleFrame

        // Try to position near cursor, offset below
        var x = mouseLocation.x - panelWidth / 2
        var y = mouseLocation.y - panel.frame.height - 20

        // Clamp to screen bounds
        x = max(screenFrame.minX + 10, min(x, screenFrame.maxX - panelWidth - 10))
        y = max(screenFrame.minY + 10, min(y, screenFrame.maxY - panel.frame.height - 10))

        panel.setFrameOrigin(NSPoint(x: x, y: y))
    }

    // MARK: - Input Handling

    @objc private func inputFieldAction(_ sender: NSTextField) {
        let text = sender.stringValue.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { return }

        // Show result area with loading
        showLoading()

        // Call backend
        Task {
            do {
                let response = try await APIClient.shared.generate(text: text)
                await MainActor.run { [weak self] in
                    self?.showResult(response.candidate)
                }
            } catch {
                await MainActor.run { [weak self] in
                    self?.showResult("Error: \(error.localizedDescription)")
                }
            }
        }
    }

    private func showLoading() {
        resultContainer.isHidden = false
        loadingIndicator.isHidden = false
        loadingIndicator.startAnimation(nil)
        resultText.string = ""
        copyButton.isEnabled = false
        insertButton.isEnabled = false

        // Expand panel
        let expandedHeight = inputHeight + padding * 4 + 20 + resultHeight + 50
        var frame = panel.frame
        let heightDelta = expandedHeight - frame.height
        frame.size.height = expandedHeight
        frame.origin.y -= heightDelta
        panel.setFrame(frame, display: true, animate: true)
    }

    private func showResult(_ text: String) {
        currentResult = text
        loadingIndicator.stopAnimation(nil)
        loadingIndicator.isHidden = true
        resultText.string = text
        copyButton.isEnabled = true
        insertButton.isEnabled = true
    }

    // MARK: - Actions

    @objc private func copyResult() {
        guard !currentResult.isEmpty else { return }
        NSPasteboard.general.clearContents()
        NSPasteboard.general.setString(currentResult, forType: .string)

        // Visual feedback
        copyButton.title = "Copied!"
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.5) { [weak self] in
            self?.copyButton.title = "Copy"
        }
    }

    @objc private func insertResult() {
        guard !currentResult.isEmpty else { return }

        // Save current clipboard
        let savedClipboard = NSPasteboard.general.string(forType: .string)

        // Put result on clipboard
        NSPasteboard.general.clearContents()
        NSPasteboard.general.setString(currentResult, forType: .string)

        // Dismiss panel
        dismiss()

        // Simulate Cmd+V after a small delay
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.15) {
            let source = CGEventSource(stateID: .hidSystemState)

            let keyDown = CGEvent(keyboardEventSource: source, virtualKey: 0x09, keyDown: true) // V key
            keyDown?.flags = .maskCommand
            let keyUp = CGEvent(keyboardEventSource: source, virtualKey: 0x09, keyDown: false)
            keyUp?.flags = .maskCommand

            keyDown?.post(tap: .cghidEventTap)
            keyUp?.post(tap: .cghidEventTap)

            // Restore clipboard after paste
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
                if let saved = savedClipboard {
                    NSPasteboard.general.clearContents()
                    NSPasteboard.general.setString(saved, forType: .string)
                }
            }
        }
    }

}
