import AppKit
import SwiftUI

@main
struct LanGuardMacApp: App {
    @State private var appModel = AppModel()

    var body: some Scene {
        WindowGroup("LanGuard", id: "main") {
            ContentView()
                .environment(appModel)
                .task {
                    await appModel.prepareNotifications()
                }
        }
        .windowStyle(.hiddenTitleBar)

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
            appModel.runScan()
        } label: {
            Label(appModel.isScanning ? "Scanning..." : "Run Scan", systemImage: "arrow.clockwise")
        }
        .disabled(appModel.isScanning)

        Divider()

        Text("Devices: \(appModel.devices.count)")
        Text("Online: \(appModel.onlineCount)")
        Text("Open ports: \(appModel.openPortCount)")

        if let latestScan = appModel.latestScan {
            Text("Last scan: \(title(for: latestScan.status))")
        }

        Divider()

        Button("Quit LanGuard") {
            NSApp.terminate(nil)
        }
        .keyboardShortcut("q")
    }

    private func showMainWindow() {
        openWindow(id: "main")
        NSApp.activate(ignoringOtherApps: true)
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
