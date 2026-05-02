import AppKit

class StatusMenuController: NSObject {

    private var statusItem: NSStatusItem?
    private var hotkeyManager: HotkeyManager?
    private var candidateWindow: CandidateWindow?
    private var isEnabled: Bool = true

    var onQuit: (() -> Void)?

    override init() {
        super.init()
        setupStatusItem()
        setupHotkeyManager()
    }

    private func setupStatusItem() {
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.squareLength)

        if let button = statusItem?.button {
            button.image = NSImage(systemSymbolName: "character.cursor.ibeam", accessibilityDescription: "MindFlow")
            button.image?.isTemplate = true
        }

        let menu = NSMenu()

        let enableItem = NSMenuItem(title: "启用 MindFlow", action: #selector(toggleEnabled), keyEquivalent: "")
        enableItem.state = isEnabled ? .on : .off
        menu.addItem(enableItem)

        menu.addItem(NSMenuItem.separator())

        menu.addItem(NSMenuItem(title: "设置 API Key", action: #selector(openSettings), keyEquivalent: ","))
        menu.addItem(NSMenuItem.separator())
        menu.addItem(NSMenuItem(title: "退出", action: #selector(quit), keyEquivalent: "q"))

        statusItem?.menu = menu
    }

    private func setupHotkeyManager() {
        hotkeyManager = HotkeyManager()
        hotkeyManager?.onTrigger = { [weak self] text in
            self?.handleTrigger(text: text)
        }
        hotkeyManager?.start()
    }

    private func handleTrigger(text: String) {
        guard isEnabled else { return }
        guard !text.isEmpty else { return }

        print("Trigger detected: \(text)")

        // Show loading state
        candidateWindow?.showCandidate("...")

        // Call API
        APIClient.shared.generate(text: text) { [weak self] result in
            DispatchQueue.main.async {
                switch result {
                case .success(let response):
                    self?.candidateWindow?.showCandidate(response.candidate)
                case .failure(let error):
                    self?.candidateWindow?.showCandidate("Error: \(error.localizedDescription)")
                }
            }
        }
    }

    @objc private func toggleEnabled(_ sender: NSMenuItem) {
        isEnabled.toggle()
        sender.state = isEnabled ? .on : .off

        if isEnabled {
            hotkeyManager?.start()
        } else {
            hotkeyManager?.stop()
            candidateWindow?.hide()
        }
    }

    @objc private func openSettings() {
        let alert = NSAlert()
        alert.messageText = "设置 ANTHROPIC_API_KEY"
        alert.informativeText = "请输入您的 Anthropic API Key:"
        alert.alertStyle = .informational

        let input = NSTextField(frame: NSRect(x: 0, y: 0, width: 300, height: 24))
        input.placeholderString = "sk-ant-..."
        input.stringValue = UserDefaults.standard.string(forKey: "ANTHROPIC_API_KEY") ?? ""
        alert.accessoryView = input

        alert.addButton(withTitle: "保存")
        alert.addButton(withTitle: "取消")

        if alert.runModal() == .alertFirstButtonReturn {
            let key = input.stringValue.trimmingCharacters(in: .whitespacesAndNewlines)
            UserDefaults.standard.set(key, forKey: "ANTHROPIC_API_KEY")
        }
    }

    @objc private func quit() {
        onQuit?()
    }
}
