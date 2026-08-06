import AppKit
import SwiftUI

@main
struct LanGuardMacApp: App {
    @State private var appModel = AppModel()

    var body: some Scene {
        WindowGroup("LanGuard", id: "main") {
            ContentView()
                .environment(appModel)
        }
        .windowStyle(.hiddenTitleBar)

        Window("About LanGuard", id: "about") {
            AboutView()
                .environment(appModel)
                .frame(minWidth: 320, idealWidth: 340, maxWidth: 380,
                       minHeight: 340, idealHeight: 360, maxHeight: 390)
                .background(AboutWindowChrome())
        }
        .defaultSize(width: 340, height: 360)
        .windowResizability(.contentSize)

        MenuBarExtra {
            LanGuardMenuBarView()
                .environment(appModel)
        } label: {
            Image(systemName: "shield.lefthalf.filled.badge.checkmark")
        }
        .menuBarExtraStyle(.menu)

        Settings {
            SettingsView()
        }
        .commands {
            AboutCommands()
        }
    }
}

private struct LanGuardMenuBarView: View {
    @Environment(AppModel.self) private var appModel
    @Environment(\.openWindow) private var openWindow

    var body: some View {
        Button {
            showMainWindow()
        } label: {
            Label("Show LanGuard", systemImage: "macwindow")
        }

        Button {
            showAboutWindow()
        } label: {
            Label("About LanGuard", systemImage: "info.circle")
        }

        Button {
            appModel.runScan()
        } label: {
            Label(appModel.isScanning ? "Scanning..." : "Run Scan", systemImage: "arrow.clockwise")
        }
        .disabled(appModel.isScanning)

        Divider()

        Label("Devices: \(appModel.devices.count)", systemImage: "desktopcomputer")
        Label("Online: \(appModel.onlineCount)", systemImage: "wifi")
        Label("Offline: \(offlineCount)", systemImage: "wifi.slash")
        Label("Unknown: \(appModel.unknownCount)", systemImage: "questionmark.circle")
        Label("Open ports: \(appModel.openPortCount)", systemImage: "point.3.connected.trianglepath.dotted")

        if let latestScan = appModel.latestScan {
            Label("Last scan: \(title(for: latestScan.status))", systemImage: "clock.arrow.circlepath")
        }

        Divider()

        Button {
            NSApp.terminate(nil)
        } label: {
            Label("Quit LanGuard", systemImage: "power")
        }
        .keyboardShortcut("q")
    }

    private func showMainWindow() {
        openWindow(id: "main")
        NSApp.activate(ignoringOtherApps: true)
    }

    private func showAboutWindow() {
        openWindow(id: "about")
        NSApp.activate(ignoringOtherApps: true)
    }

    private var offlineCount: Int {
        appModel.devices.filter { $0.status == .offline }.count
    }

    private func title(for status: ScanRecord.Status) -> String {
        switch status {
        case .running:
            "Running"
        case .completed:
            "Completed"
        case .failed:
            "Failed"
        }
    }
}

private struct AboutCommands: Commands {
    @Environment(\.openWindow) private var openWindow

    var body: some Commands {
        CommandGroup(replacing: .appInfo) {
            Button("About LanGuard") {
                openWindow(id: "about")
                NSApp.activate(ignoringOtherApps: true)
            }
        }
    }
}

private struct AboutWindowChrome: NSViewRepresentable {
    func makeNSView(context: Context) -> NSView {
        let view = NSView()
        DispatchQueue.main.async {
            configure(view.window)
        }
        return view
    }

    func updateNSView(_ nsView: NSView, context: Context) {
        DispatchQueue.main.async {
            configure(nsView.window)
        }
    }

    private func configure(_ window: NSWindow?) {
        guard let window else { return }
        window.styleMask.remove([.miniaturizable, .resizable])
        window.collectionBehavior.remove(.fullScreenPrimary)
        window.standardWindowButton(.miniaturizeButton)?.isHidden = true
        window.standardWindowButton(.zoomButton)?.isHidden = true
    }
}
