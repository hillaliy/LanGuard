import AppKit
import SwiftUI
import UniformTypeIdentifiers

struct SettingsView: View {
    @Environment(AppModel.self) private var appModel
    @State private var defaultScanRange = AppSettings.default.defaultScanRange
    @State private var scanIntervalMinutes = AppSettings.default.scanIntervalMinutes
    @State private var tcpPorts = AppSettings.default.defaultPortsText
    @State private var rooms = AppSettings.default.rooms
    @State private var newRoomName = ""
    @State private var scheduledScanningEnabled = AppSettings.default.scheduledScanningEnabled
    @State private var newDeviceNotificationsEnabled = AppSettings.default.newDeviceNotificationsEnabled
    @State private var riskyPortNotificationsEnabled = AppSettings.default.riskyPortNotificationsEnabled
    @State private var cloudBackupEnabled = AppSettings.default.cloudBackupEnabled
    @State private var cloudBackupFolderPath = AppSettings.default.cloudBackupFolderPath ?? ""
    @State private var launchAtLoginEnabled = LaunchAtLoginService.isEnabled
    @State private var validationMessage: String?
    @State private var validationMessageIsError = false
    @State private var inventoryTransferMessage: String?
    @State private var inventoryTransferIsError = false
    @State private var isSendingTestNotification = false

    var body: some View {
        VStack(alignment: .leading, spacing: 20) {
            HeaderView(
                title: "Settings",
                subtitle: "Control how LanGuard scans this Mac's local network.",
                systemImage: "gearshape"
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

                Section("Rooms") {
                    Text("Create rooms to organize devices and filter the inventory.")
                        .font(.footnote)
                        .foregroundStyle(.secondary)

                    HStack {
                        TextField("Room name", text: $newRoomName)
                            .textFieldStyle(.roundedBorder)

                        Button("Add", systemImage: "plus") {
                            addRoom()
                        }
                        .disabled(newRoomName.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                    }

                    if rooms.isEmpty {
                        Text("No rooms configured yet.")
                            .foregroundStyle(.secondary)
                    } else {
                        ForEach(rooms, id: \.self) { room in
                            HStack {
                                Text(room)
                                Spacer()
                                Button(role: .destructive) {
                                    removeRoom(room)
                                } label: {
                                    Image(systemName: "trash")
                                }
                                .buttonStyle(.borderless)
                                .help("Remove room")
                            }
                        }
                    }
                }

                Section("System") {
                    Toggle(
                        "Open LanGuard at login",
                        isOn: Binding(
                            get: { launchAtLoginEnabled },
                            set: { updateLaunchAtLogin($0) }
                        )
                    )

                    Text(LaunchAtLoginService.statusText)
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }

                Section("Notifications") {
                    Toggle("New unknown devices", isOn: $newDeviceNotificationsEnabled)
                    Toggle("High-risk open ports", isOn: $riskyPortNotificationsEnabled)

                    Button {
                        sendTestNotification()
                    } label: {
                        Label(
                            isSendingTestNotification ? "Sending Test..." : "Send Test Notification",
                            systemImage: "bell.badge"
                        )
                    }
                    .disabled(isSendingTestNotification)

                    Button {
                        requestNotificationPermission()
                    } label: {
                        Label("Request Notification Permission", systemImage: "bell.badge.fill")
                    }

                    Button {
                        openNotificationSettings()
                    } label: {
                        Label("Open Notification Settings", systemImage: "gear.badge")
                    }

                    Text("Scan alerts are sent only for new unknown devices and unknown devices with risky ports.")
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }

                Section("Device Inventory") {
                    Text("Export or import device names, icons, rooms, vendors, IP addresses, MAC addresses, and open ports.")
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

                    if let inventoryTransferMessage {
                        Label(
                            inventoryTransferMessage,
                            systemImage: inventoryTransferIsError ? "xmark.circle.fill" : "checkmark.circle.fill"
                        )
                        .font(.callout.weight(.semibold))
                        .foregroundStyle(inventoryTransferIsError ? .red : .green)
                        .padding(.vertical, 8)
                        .padding(.horizontal, 10)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .background(
                            (inventoryTransferIsError ? Color.red : Color.green).opacity(0.12),
                            in: RoundedRectangle(cornerRadius: 8)
                        )
                    }
                }

                Section("Cloud Backup") {
                    Toggle("Backup to cloud folder", isOn: $cloudBackupEnabled)

                    Text("Choose an iCloud Drive, Dropbox, OneDrive, or other synced folder. LanGuard writes languard-devices-backup.json there after changes.")
                        .font(.footnote)
                        .foregroundStyle(.secondary)

                    HStack(spacing: 10) {
                        Text(cloudBackupFolderPath.isEmpty ? "No folder selected" : cloudBackupFolderPath)
                            .font(.footnote)
                            .foregroundStyle(cloudBackupFolderPath.isEmpty ? .secondary : .primary)
                            .lineLimit(1)
                            .truncationMode(.middle)
                            .frame(maxWidth: .infinity, alignment: .leading)

                        Button {
                            chooseCloudBackupFolder()
                        } label: {
                            Label("Choose", systemImage: "folder")
                        }
                    }

                    HStack {
                        Button {
                            backupInventoryNow()
                        } label: {
                            Label("Backup Now", systemImage: "icloud.and.arrow.up")
                        }
                        .disabled(!cloudBackupEnabled || cloudBackupFolderPath.isEmpty)

                        Button {
                            cloudBackupFolderPath = ""
                        } label: {
                            Label("Clear Folder", systemImage: "xmark.circle")
                        }
                        .disabled(cloudBackupFolderPath.isEmpty)
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
            launchAtLoginEnabled = LaunchAtLoginService.isEnabled
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

        let backupPath = cloudBackupFolderPath.trimmingCharacters(in: .whitespacesAndNewlines)
        if cloudBackupEnabled && backupPath.isEmpty {
            validationMessage = "Choose a cloud backup folder or turn cloud backup off."
            validationMessageIsError = true
            return
        }

        appModel.updateSettings(AppSettings(
            defaultScanRange: range,
            scanIntervalMinutes: scanIntervalMinutes,
            tcpPorts: ports,
            scheduledScanningEnabled: scheduledScanningEnabled,
            newDeviceNotificationsEnabled: newDeviceNotificationsEnabled,
            riskyPortNotificationsEnabled: riskyPortNotificationsEnabled,
            cloudBackupEnabled: cloudBackupEnabled,
            cloudBackupFolderPath: backupPath.isEmpty ? nil : backupPath,
            rooms: rooms
        ).normalized)
        apply(appModel.settings)
        validationMessage = nil
        validationMessageIsError = false

        if newDeviceNotificationsEnabled || riskyPortNotificationsEnabled {
            Task {
                await appModel.prepareNotifications()
                await updateNotificationPermissionMessage()
            }
        }
    }

    private func apply(_ settings: AppSettings) {
        defaultScanRange = settings.defaultScanRange
        scanIntervalMinutes = settings.scanIntervalMinutes
        tcpPorts = settings.portsText
        rooms = settings.rooms
        scheduledScanningEnabled = settings.scheduledScanningEnabled
        newDeviceNotificationsEnabled = settings.newDeviceNotificationsEnabled
        riskyPortNotificationsEnabled = settings.riskyPortNotificationsEnabled
        cloudBackupEnabled = settings.cloudBackupEnabled
        cloudBackupFolderPath = settings.cloudBackupFolderPath ?? ""
    }

    private func addRoom() {
        let value = newRoomName.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !value.isEmpty,
              !rooms.contains(where: { $0.caseInsensitiveCompare(value) == .orderedSame }) else {
            return
        }

        rooms.append(value)
        rooms.sort { $0.localizedStandardCompare($1) == .orderedAscending }
        newRoomName = ""
    }

    private func removeRoom(_ room: String) {
        rooms.removeAll { $0 == room }
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
            inventoryTransferMessage = "Device inventory exported successfully."
            inventoryTransferIsError = false
        } catch {
            validationMessage = "Could not export device inventory: \(error.localizedDescription)"
            validationMessageIsError = true
            inventoryTransferMessage = "Export failed: \(error.localizedDescription)"
            inventoryTransferIsError = true
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
            inventoryTransferMessage = "Import completed: \(result.created) new, \(result.updated) updated, \(result.skipped) skipped."
            inventoryTransferIsError = false
        } catch {
            validationMessage = "Could not import device inventory: \(error.localizedDescription)"
            validationMessageIsError = true
            inventoryTransferMessage = "Import failed: \(error.localizedDescription)"
            inventoryTransferIsError = true
        }
    }

    private func chooseCloudBackupFolder() {
        let panel = NSOpenPanel()
        panel.message = "Choose an iCloud Drive, Dropbox, OneDrive, or other synced folder."
        panel.prompt = "Choose Folder"
        panel.allowsMultipleSelection = false
        panel.canChooseDirectories = true
        panel.canChooseFiles = false
        panel.canCreateDirectories = true

        guard panel.runModal() == .OK, let url = panel.url else {
            return
        }

        cloudBackupFolderPath = url.path
        validationMessage = "Cloud backup folder selected."
        validationMessageIsError = false
    }

    private func backupInventoryNow() {
        saveSettings()
        guard !validationMessageIsError else { return }

        do {
            try appModel.backupDeviceInventoryNow()
            validationMessage = "Cloud backup written."
            validationMessageIsError = false
        } catch {
            validationMessage = "Could not write cloud backup: \(error.localizedDescription)"
            validationMessageIsError = true
        }
    }

    private func sendTestNotification() {
        isSendingTestNotification = true

        Task {
            let result = await appModel.sendTestNotification()
            validationMessage = result.isError
                ? "\(result.message) Open Notification Settings, allow LanGuard, then send another test."
                : result.message
            validationMessageIsError = result.isError
            isSendingTestNotification = false
        }
    }

    private func requestNotificationPermission() {
        Task {
            await appModel.prepareNotifications()
            await updateNotificationPermissionMessage()
        }
    }

    private func updateNotificationPermissionMessage() async {
        switch await appModel.notificationPermissionStatus() {
        case .authorized:
            validationMessage = "Notifications are allowed for LanGuard."
            validationMessageIsError = false
        case .notDetermined:
            validationMessage = "macOS has not recorded a notification decision yet. Launch the installed LanGuard.app, then request permission again."
            validationMessageIsError = true
        case .denied:
            validationMessage = "Notifications are blocked for LanGuard. Open Notification Settings and allow LanGuard."
            validationMessageIsError = true
        case .disabledInDevelopment:
            validationMessage = "Notifications require the packaged LanGuard.app. They are disabled when running with swift run."
            validationMessageIsError = true
        }
    }

    private func openNotificationSettings() {
        let settingsURLs = [
            "x-apple.systempreferences:com.apple.Notifications-Settings.extension?id=com.hillaliy.LanGuardMac",
            "x-apple.systempreferences:com.apple.Notifications-Settings.extension",
            "x-apple.systempreferences:com.apple.preference.notifications"
        ]

        for settingsURL in settingsURLs {
            guard let url = URL(string: settingsURL) else { continue }
            if NSWorkspace.shared.open(url) {
                validationMessage = "Opened macOS Notification Settings. Allow notifications for LanGuard, then send another test."
                validationMessageIsError = false
                return
            }
        }

        validationMessage = "Open macOS System Settings > Notifications > LanGuard and allow notifications."
        validationMessageIsError = true
    }

    private func updateLaunchAtLogin(_ enabled: Bool) {
        do {
            try LaunchAtLoginService.setEnabled(enabled)
            launchAtLoginEnabled = LaunchAtLoginService.isEnabled
            validationMessage = enabled ? "LanGuard will open when you sign in." : "LanGuard will not open when you sign in."
            validationMessageIsError = false
        } catch {
            launchAtLoginEnabled = LaunchAtLoginService.isEnabled
            validationMessage = "Could not update login item: \(error.localizedDescription)"
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
