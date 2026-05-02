import AppKit
import Carbon

class AppDelegate: NSObject, NSApplicationDelegate {

    private var statusMenuController: StatusMenuController!
    private var backendProcess: Process?
    private let backendPort = 8765
    private var hotkeyManager: HotkeyManager!
    private var inputPanel: InputPanel!
    private var candidateWindow: CandidateWindow!
    private var globalHotkeyRef: EventHotKeyRef?

    // MARK: - Application Lifecycle

    func applicationDidFinishLaunching(_ notification: Notification) {
        checkAccessibilityPermissions()

        // Initialize core components
        candidateWindow = CandidateWindow()
        inputPanel = InputPanel()
        inputPanel.candidateWindow = candidateWindow

        // Initialize hotkey manager for ;; detection
        hotkeyManager = HotkeyManager()
        hotkeyManager.candidateWindow = candidateWindow
        hotkeyManager.start()

        // Register global hotkey Cmd+Shift+M to open InputPanel
        registerGlobalHotkey()

        // Start backend service
        startBackend()

        // Setup status menu
        statusMenuController = StatusMenuController(
            hotkeyManager: hotkeyManager,
            inputPanel: inputPanel,
            candidateWindow: candidateWindow
        )
    }

    func applicationWillTerminate(_ notification: Notification) {
        hotkeyManager.stop()
        unregisterGlobalHotkey()
        stopBackend()
    }

    // MARK: - Accessibility Permissions

    private func checkAccessibilityPermissions() {
        let options = [kAXTrustedCheckOptionPrompt.takeUnretainedValue(): true] as CFDictionary
        let trusted = AXIsProcessTrustedWithOptions(options)
        if !trusted {
            print("[MindFlow] Accessibility permission not granted. Some features require it.")
            DispatchQueue.main.asyncAfter(deadline: .now() + 2.0) {
                self.showAccessibilityAlert()
            }
        } else {
            print("[MindFlow] Accessibility permission granted.")
        }
    }

    private func showAccessibilityAlert() {
        let alert = NSAlert()
        alert.messageText = "Accessibility Permission Required"
        alert.informativeText = "MindFlow needs Accessibility permission to detect hotkeys and insert text.\n\nPlease grant permission in System Settings > Privacy & Security > Accessibility, then restart the app."
        alert.alertStyle = .warning
        alert.addButton(withTitle: "Open System Settings")
        alert.addButton(withTitle: "Later")

        let response = alert.runModal()
        if response == .alertFirstButtonReturn {
            if let url = URL(string: "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility") {
                NSWorkspace.shared.open(url)
            }
        }
    }

    // MARK: - Global Hotkey (Cmd+Shift+M)

    private func registerGlobalHotkey() {
        // Use Carbon hot key API for Cmd+Shift+M
        // Key code for 'M' is 46
        var hotKeyID = EventHotKeyID()
        hotKeyID.signature = OSType(0x4D464C57) // "MFLW"
        hotKeyID.id = 1

        var eventType = EventTypeSpec(eventClass: OSType(kEventClassKeyboard), eventKind: UInt32(kEventHotKeyPressed))

        let handler: EventHandlerUPP = { _, event, _ -> OSStatus in
            guard let event = event else { return OSStatus(eventNotHandledErr) }
            var hotKeyID = EventHotKeyID()
            GetEventParameter(event,
                              EventParamName(kEventParamDirectObject),
                              EventParamType(typeEventHotKeyID),
                              nil,
                              MemoryLayout<EventHotKeyID>.size,
                              nil,
                              &hotKeyID)

            if hotKeyID.id == 1 {
                DispatchQueue.main.async {
                    guard let delegate = NSApp.delegate as? AppDelegate else { return }
                    delegate.openInputPanel()
                }
            }
            return noErr
        }

        InstallEventHandler(GetApplicationEventTarget(), handler, 1, &eventType, nil, nil)

        let modifiers = UInt32(cmdKey | shiftKey)
        let keyCode = UInt32(46) // 'M'
        RegisterEventHotKey(keyCode, modifiers, hotKeyID, GetApplicationEventTarget(), 0, &globalHotkeyRef)

        print("[MindFlow] Global hotkey Cmd+Shift+M registered.")
    }

    private func unregisterGlobalHotkey() {
        if let ref = globalHotkeyRef {
            UnregisterEventHotKey(ref)
            globalHotkeyRef = nil
        }
    }

    @objc func openInputPanel() {
        inputPanel.show()
    }

    // MARK: - Backend Management

    private func startBackend() {
        if isPortInUse(backendPort) {
            print("[MindFlow] Backend already running on port \(backendPort)")
            return
        }

        let pythonPath = "/usr/bin/python3"
        guard FileManager.default.fileExists(atPath: pythonPath) else {
            print("[MindFlow] Python3 not found at \(pythonPath)")
            return
        }

        let currentDir = FileManager.default.currentDirectoryPath
        let projectRoot = (currentDir as NSString).appendingPathComponent("../..")

        backendProcess = Process()
        backendProcess?.executableURL = URL(fileURLWithPath: pythonPath)
        backendProcess?.arguments = ["-m", "uvicorn", "src.backend.main:app",
                                      "--host", "127.0.0.1",
                                      "--port", "\(backendPort)"]
        backendProcess?.currentDirectoryURL = URL(fileURLWithPath: projectRoot)

        var env = ProcessInfo.processInfo.environment
        if let apiKey = UserDefaults.standard.string(forKey: "apiKey"), !apiKey.isEmpty {
            env["ANTHROPIC_API_KEY"] = apiKey
        }
        backendProcess?.environment = env

        backendProcess?.standardOutput = FileHandle.nullDevice
        backendProcess?.standardError = FileHandle.nullDevice

        do {
            try backendProcess?.run()
            print("[MindFlow] Backend started with PID: \(backendProcess?.processIdentifier ?? 0)")
        } catch {
            print("[MindFlow] Failed to start backend: \(error)")
        }
    }

    private func stopBackend() {
        backendProcess?.terminate()
        backendProcess = nil
    }

    private func isPortInUse(_ port: Int) -> Bool {
        let sock = socket(AF_INET, SOCK_STREAM, 0)
        guard sock >= 0 else { return false }
        defer { close(sock) }

        var addr = sockaddr_in()
        addr.sin_family = sa_family_t(AF_INET)
        addr.sin_port = in_port_t(port).bigEndian
        addr.sin_addr.s_addr = inet_addr("127.0.0.1")

        let result = withUnsafePointer(to: &addr) {
            $0.withMemoryRebound(to: sockaddr.self, capacity: 1) {
                connect(sock, $0, socklen_t(MemoryLayout<sockaddr_in>.size))
            }
        }
        return result == 0
    }
}
