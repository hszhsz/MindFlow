import AppKit

// MindFlow - AI-powered input method for macOS
// Standard NSApplication setup for a menu bar agent app (LSUIElement)

let app = NSApplication.shared
app.setActivationPolicy(.accessory)

let delegate = AppDelegate()
app.delegate = delegate
app.run()
