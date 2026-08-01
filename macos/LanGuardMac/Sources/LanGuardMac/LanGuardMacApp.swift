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
