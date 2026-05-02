import AppKit

class AppDelegate: NSObject, NSApplicationDelegate {

    private var statusMenuController: StatusMenuController?
    private var backendProcess: Process?
    private let backendPort = 8765

    func applicationDidFinishLaunching(_ notification: Notification) {
        // Start backend service
        startBackend()

        // Setup status menu
        statusMenuController = StatusMenuController()
        statusMenuController?.onQuit = { [weak self] in
            self?.quit()
        }

        // Hide dock icon - menu bar app only
        NSApp.setActivationPolicy(.accessory)
    }

    func applicationWillTerminate(_ notification: Notification) {
        stopBackend()
    }

    private func startBackend() {
        // Check if backend is already running
        if isPortInUse(backendPort) {
            print("Backend already running on port \(backendPort)")
            return
        }

        // Find Python path
        let pythonPath = "/usr/bin/python3"

        // Get the app's bundle directory or current directory
        let currentDir = FileManager.default.currentDirectoryPath
        let backendPath = (currentDir as NSString).appendingPathComponent("../../backend")

        // Start backend process
        backendProcess = Process()
        backendProcess?.executableURL = URL(fileURLWithPath: pythonPath)
        backendProcess?.arguments = ["-m", "uvicorn", "src.backend.main:app", "--host", "0.0.0.0", "--port", "\(backendPort)"]
        backendProcess?.currentDirectoryURL = URL(fileURLWithPath: (currentDir as NSString).appendingPathComponent("../.."))

        // Setup environment
        var env = ProcessInfo.processInfo.environment
        // Pass ANTHROPIC_API_KEY if set
        if let apiKey = UserDefaults.standard.string(forKey: "ANTHROPIC_API_KEY") {
            env["ANTHROPIC_API_KEY"] = apiKey
        }
        backendProcess?.environment = env

        // Handle output
        backendProcess?.standardOutput = Pipe()
        backendProcess?.standardError = Pipe()

        do {
            try backendProcess?.run()
            print("Backend started with PID: \(backendProcess?.processIdentifier ?? 0)")
        } catch {
            print("Failed to start backend: \(error)")
        }
    }

    private func stopBackend() {
        backendProcess?.terminate()
        backendProcess = nil
    }

    private func isPortInUse(_ port: Int) -> Bool {
        let sock = socket(AF_INET, SOCK_STREAM, 0)
        var addr = sockaddr_in()
        addr.sin_family = sa_family_t(AF_INET)
        addr.sin_port = in_port_t(port).bigEndian
        addr.sin_addr.s_addr = inet_addr("127.0.0.1")

        let result = withUnsafePointer(to: &addr) {
            $0.withMemoryRebound(to: sockaddr.self, capacity: 1) {
                connect(sock, $0, socklen_t(MemoryLayout<sockaddr_in>.size))
            }
        }

        close(sock)
        return result == 0
    }

    private func quit() {
        stopBackend()
        NSApp.terminate(nil)
    }
}
