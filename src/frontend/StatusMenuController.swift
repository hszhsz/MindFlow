import AppKit

/// StatusMenuController manages the menu bar icon and dropdown menu.
/// Shows backend connection status, provides quick access to InputPanel,
/// and offers settings/quit options.
class StatusMenuController: NSObject {

    private var statusItem: NSStatusItem!
    private var menu: NSMenu!
    private var hotkeyManager: HotkeyManager
    private var inputPanel: InputPanel
    private var candidateWindow: CandidateWindow
    private var isEnabled: Bool = true
    private var backendStatusItem: NSMenuItem!
    private var enableItem: NSMenuItem!
    private var healthCheckTimer: Timer?

    init(hotkeyManager: HotkeyManager, inputPanel: InputPanel, candidateWindow: CandidateWindow) {
        self.hotkeyManager = hotkeyManager
        self.inputPanel = inputPanel
        self.candidateWindow = candidateWindow
        super.init()
        setupStatusItem()
        startHealthCheck()
    }

    // MARK: - Setup

    private func setupStatusItem() {
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.squareLength)

        if let button = statusItem.button {
            button.image = NSImage(systemSymbolName: "character.cursor.ibeam", accessibilityDescription: "MindFlow")
            button.image?.isTemplate = true
        }

        menu = NSMenu()
        menu.delegate = self

        // Open Input Panel
        let openPanelItem = NSMenuItem(title: "Open Input Panel", action: #selector(openInputPanel), keyEquivalent: "M")
        openPanelItem.keyEquivalentModifierMask = [.command, .shift]
        openPanelItem.target = self
        menu.addItem(openPanelItem)

        menu.addItem(NSMenuItem.separator())

        // Enable/Disable
        enableItem = NSMenuItem(title: "Enabled", action: #selector(toggleEnabled), keyEquivalent: "")
        enableItem.target = self
        enableItem.state = .on
        menu.addItem(enableItem)

        menu.addItem(NSMenuItem.separator())

        // Backend Status
        backendStatusItem = NSMenuItem(title: "Backend: Checking...", action: nil, keyEquivalent: "")
        backendStatusItem.isEnabled = false
        menu.addItem(backendStatusItem)

        menu.addItem(NSMenuItem.separator())

        // Settings
        let settingsItem = NSMenuItem(title: "Settings...", action: #selector(openSettings), keyEquivalent: ",")
        settingsItem.target = self
        menu.addItem(settingsItem)

        menu.addItem(NSMenuItem.separator())

        // Quit
        let quitItem = NSMenuItem(title: "Quit MindFlow", action: #selector(quit), keyEquivalent: "q")
        quitItem.target = self
        menu.addItem(quitItem)

        statusItem.menu = menu
    }

    // MARK: - Health Check

    private func startHealthCheck() {
        // Check immediately
        checkBackendStatus()

        // Then check every 30 seconds
        healthCheckTimer = Timer.scheduledTimer(withTimeInterval: 30.0, repeats: true) { [weak self] _ in
            self?.checkBackendStatus()
        }
    }

    private func checkBackendStatus() {
        Task {
            let healthy = await APIClient.shared.checkHealth()
            await MainActor.run { [weak self] in
                self?.updateBackendStatus(connected: healthy)
            }
        }
    }

    private func updateBackendStatus(connected: Bool) {
        if connected {
            backendStatusItem.title = "\u{1F7E2} Backend: Connected"
        } else {
            backendStatusItem.title = "\u{1F534} Backend: Disconnected"
        }
    }

    // MARK: - Actions

    @objc private func openInputPanel() {
        inputPanel.show()
    }

    @objc private func toggleEnabled() {
        isEnabled.toggle()
        enableItem.state = isEnabled ? .on : .off

        if isEnabled {
            hotkeyManager.start()
            statusItem.button?.image = NSImage(systemSymbolName: "character.cursor.ibeam", accessibilityDescription: "MindFlow")
        } else {
            hotkeyManager.stop()
            candidateWindow.hide()
            statusItem.button?.image = NSImage(systemSymbolName: "character.cursor.ibeam", accessibilityDescription: "MindFlow (Disabled)")
            // Dim the icon when disabled
            statusItem.button?.appearsDisabled = true
        }
        statusItem.button?.appearsDisabled = !isEnabled
    }

    @objc private func openSettings() {
        let settingsWindow = SettingsWindowController()
        settingsWindow.showWindow(nil)
        NSApp.activate(ignoringOtherApps: true)
    }

    @objc private func quit() {
        NSApp.terminate(nil)
    }

    deinit {
        healthCheckTimer?.invalidate()
    }
}

// MARK: - NSMenuDelegate

extension StatusMenuController: NSMenuDelegate {
    func menuWillOpen(_ menu: NSMenu) {
        // Refresh backend status when menu opens
        checkBackendStatus()
    }
}

// MARK: - Settings Window

class SettingsWindowController: NSWindowController, NSWindowDelegate {

    private var apiKeyField: NSSecureTextField!
    private var backendURLField: NSTextField!

    convenience init() {
        let window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 450, height: 200),
            styleMask: [.titled, .closable],
            backing: .buffered,
            defer: false
        )
        window.title = "MindFlow Settings"
        window.center()
        window.isReleasedWhenClosed = false

        self.init(window: window)
        self.window?.delegate = self
        setupUI()
        loadSettings()
    }

    private func setupUI() {
        guard let contentView = window?.contentView else { return }

        let stackView = NSStackView(frame: .zero)
        stackView.translatesAutoresizingMaskIntoConstraints = false
        stackView.orientation = .vertical
        stackView.alignment = .leading
        stackView.spacing = 16
        contentView.addSubview(stackView)

        NSLayoutConstraint.activate([
            stackView.topAnchor.constraint(equalTo: contentView.topAnchor, constant: 20),
            stackView.leadingAnchor.constraint(equalTo: contentView.leadingAnchor, constant: 20),
            stackView.trailingAnchor.constraint(equalTo: contentView.trailingAnchor, constant: -20),
        ])

        // API Key
        let apiKeyLabel = NSTextField(labelWithString: "API Key:")
        apiKeyLabel.font = NSFont.systemFont(ofSize: 13, weight: .medium)
        stackView.addArrangedSubview(apiKeyLabel)

        apiKeyField = NSSecureTextField(frame: .zero)
        apiKeyField.translatesAutoresizingMaskIntoConstraints = false
        apiKeyField.placeholderString = "sk-ant-..."
        stackView.addArrangedSubview(apiKeyField)
        apiKeyField.widthAnchor.constraint(equalToConstant: 400).isActive = true

        // Backend URL
        let urlLabel = NSTextField(labelWithString: "Backend URL:")
        urlLabel.font = NSFont.systemFont(ofSize: 13, weight: .medium)
        stackView.addArrangedSubview(urlLabel)

        backendURLField = NSTextField(frame: .zero)
        backendURLField.translatesAutoresizingMaskIntoConstraints = false
        backendURLField.placeholderString = "http://localhost:8765"
        stackView.addArrangedSubview(backendURLField)
        backendURLField.widthAnchor.constraint(equalToConstant: 400).isActive = true

        // Save button
        let saveButton = NSButton(title: "Save", target: self, action: #selector(saveSettings))
        saveButton.bezelStyle = .rounded
        saveButton.keyEquivalent = "\r"
        stackView.addArrangedSubview(saveButton)
    }

    private func loadSettings() {
        apiKeyField.stringValue = UserDefaults.standard.string(forKey: "apiKey") ?? ""
        backendURLField.stringValue = UserDefaults.standard.string(forKey: "backendURL") ?? "http://localhost:8765"
    }

    @objc private func saveSettings() {
        let apiKey = apiKeyField.stringValue.trimmingCharacters(in: .whitespacesAndNewlines)
        let backendURL = backendURLField.stringValue.trimmingCharacters(in: .whitespacesAndNewlines)

        UserDefaults.standard.set(apiKey, forKey: "apiKey")
        UserDefaults.standard.set(backendURL.isEmpty ? "http://localhost:8765" : backendURL, forKey: "backendURL")

        // Update APIClient base URL
        let finalURL = backendURL.isEmpty ? "http://localhost:8765" : backendURL
        Task {
            await APIClient.shared.updateBaseURL(finalURL)
        }

        window?.close()
    }

    func windowWillClose(_ notification: Notification) {
        // No-op, window is retained by the controller
    }
}
