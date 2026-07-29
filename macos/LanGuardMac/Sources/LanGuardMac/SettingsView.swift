import AppKit
import SwiftUI
import UniformTypeIdentifiers

struct SettingsView: View {
    @Environment(AppModel.self) private var appModel
    @State private var defaultScanRange = AppSettings.default.defaultScanRange
    @State private var scanIntervalMinutes = AppSettings.default.scanIntervalMinutes
    @State private var tcpPorts = AppSettings.default.defaultPortsText
    @State private var scheduledScanningEnabled = AppSettings.default.scheduledScanningEnabled
    @State private var newDeviceNotificationsEnabled = AppSettings.default.newDeviceNotificationsEnabled
    @State private var riskyPortNotificationsEnabled = AppSettings.default.riskyPortNotificationsEnabled
    @State private var validationMessage: String?
    @State private var validationMessageIsError = false

    var body: some View {
        VStack(alignment: .leading, spacing: 20) {
            HeaderView(
                title: "Settings",
                subtitle: "Control how LanGuard scans this Mac's local network."
            )

            Form {
                Section("Scanning") {
                    Toggle("Automatic scanning", isOn: $scheduledScanningEnabled)

                    TextField("Default scan range", text: $defaultScanRange)
                        .textFieldStyle(.roundedBorder)

                    Stepper(value: $scanIntervalMinutes, in: 1...1440) {
                        Text("Scan interval: \(scanIntervalMinutes) min")
                    }

                    TextField("TCP ports", text: $tcpPorts, axis: .vertical)
                        .lineLimit(2...4)
                        .textFieldStyle(.roundedBorder)
                }

                Section("Notifications") {
                    Toggle("New unknown devices", isOn: $newDeviceNotificationsEnabled)
                    Toggle("High-risk open ports", isOn: $riskyPortNotificationsEnabled)
                }

                Section("Device Inventory") {
                    Text("Export or import device names, icons, vendors, IP addresses, MAC addresses, and open ports.")
                        .foregroundStyle(.secondary)

                    HStack {
                        Button {
                            exportInventory()
                        } label: {
                            Label("Export Devices", systemImage: "square.and.arrow.down")
                        }

                        Button {
                            importInventory()
                        } label: {
                            Label("Import Devices", systemImage: "square.and.arrow.up")
                        }
                    }
                }
            }
            .formStyle(.grouped)

            if let validationMessage {
                Text(validationMessage)
                    .font(.callout)
                    .foregroundStyle(validationMessageIsError ? .red : .secondary)
            }

            HStack {
                Button("Reset Defaults") {
                    apply(AppSettings.default)
                    validationMessage = nil
                    validationMessageIsError = false
                }

                Spacer()

                Button("Save") {
                    saveSettings()
                }
                .buttonStyle(.borderedProminent)
            }
        }
        .frame(width: 520)
        .padding(28)
        .onAppear {
            apply(appModel.settings)
        }
    }

    private func saveSettings() {
        let range = defaultScanRange.trimmingCharacters(in: .whitespacesAndNewlines)
        guard IPv4CIDRRange(range) != nil else {
            validationMessage = "Enter a valid IPv4 CIDR range, like 192.168.0.0/24."
            validationMessageIsError = true
            return
        }

        guard let ports = AppSettings.parsePorts(tcpPorts) else {
            validationMessage = "Enter valid TCP ports between 1 and 65535."
            validationMessageIsError = true
            return
        }

        appModel.updateSettings(AppSettings(
            defaultScanRange: range,
            scanIntervalMinutes: scanIntervalMinutes,
            tcpPorts: ports,
            scheduledScanningEnabled: scheduledScanningEnabled,
            newDeviceNotificationsEnabled: newDeviceNotificationsEnabled,
            riskyPortNotificationsEnabled: riskyPortNotificationsEnabled
        ).normalized)
        apply(appModel.settings)
        validationMessage = nil
        validationMessageIsError = false
    }

    private func apply(_ settings: AppSettings) {
        defaultScanRange = settings.defaultScanRange
        scanIntervalMinutes = settings.scanIntervalMinutes
        tcpPorts = settings.portsText
        scheduledScanningEnabled = settings.scheduledScanningEnabled
        newDeviceNotificationsEnabled = settings.newDeviceNotificationsEnabled
        riskyPortNotificationsEnabled = settings.riskyPortNotificationsEnabled
    }

    private func exportInventory() {
        let panel = NSSavePanel()
        panel.allowedContentTypes = [.json]
        panel.nameFieldStringValue = "languard-inventory-\(Self.exportDateFormatter.string(from: .now)).json"
        panel.canCreateDirectories = true

        guard panel.runModal() == .OK, let url = panel.url else {
            return
        }

        do {
            try appModel.exportDeviceInventory(to: url)
            validationMessage = "Device inventory exported."
            validationMessageIsError = false
        } catch {
            validationMessage = "Could not export device inventory: \(error.localizedDescription)"
            validationMessageIsError = true
        }
    }

    private func importInventory() {
        let panel = NSOpenPanel()
        panel.allowedContentTypes = [.json]
        panel.allowsMultipleSelection = false
        panel.canChooseDirectories = false
        panel.canChooseFiles = true

        guard panel.runModal() == .OK, let url = panel.url else {
            return
        }

        do {
            let result = try appModel.importDeviceInventory(from: url)
            validationMessage = "Imported \(result.created) new, updated \(result.updated), skipped \(result.skipped)."
            validationMessageIsError = false
        } catch {
            validationMessage = "Could not import device inventory: \(error.localizedDescription)"
            validationMessageIsError = true
        }
    }

    private static let exportDateFormatter: DateFormatter = {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        return formatter
    }()
}

private extension AppSettings {
    var portsText: String {
        tcpPorts.map(String.init).joined(separator: ", ")
    }

    var defaultPortsText: String {
        Self.defaultPorts.map(String.init).joined(separator: ", ")
    }
}

#Preview {
    SettingsView()
        .environment(AppModel())
}
