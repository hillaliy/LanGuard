import SwiftUI

struct DevicesView: View {
    @Environment(AppModel.self) private var appModel
    @State private var editingDevice: NetworkDevice?

    var body: some View {
        VStack(alignment: .leading, spacing: 20) {
            HeaderView(
                title: "Devices",
                subtitle: "Discovered network devices will appear here."
            )

            if appModel.devices.isEmpty {
                emptyDevicesView
            } else {
                Table(appModel.devices) {
                    TableColumn("Status") { device in
                        HStack {
                            Circle()
                                .fill(device.status == .online ? .green : .gray)
                                .frame(width: 8, height: 8)
                            Text(device.status.title)
                        }
                    }

                    TableColumn("Name") { device in
                        HStack(spacing: 8) {
                            Image(systemName: device.displayIconName)
                                .foregroundStyle(.blue)
                                .frame(width: 20)
                            Text(device.name)
                        }
                    }
                    TableColumn("IP", value: \.ipAddress)
                    TableColumn("MAC", value: \.macAddress)

                    TableColumn("Ports") { device in
                        Text(portSummary(for: device.openPorts))
                            .foregroundStyle(device.openPorts.isEmpty ? .secondary : .primary)
                    }

                    TableColumn("Risk") { device in
                        Text(device.risk.title)
                            .font(.caption.weight(.semibold))
                            .padding(.horizontal, 8)
                            .padding(.vertical, 4)
                            .background(riskColor(for: device.risk).opacity(0.18), in: Capsule())
                            .foregroundStyle(riskColor(for: device.risk))
                    }

                    TableColumn("Role") { device in
                        Text(device.isGateway ? "Gateway" : "Device")
                    }

                    TableColumn("Known") { device in
                        Text(device.isKnown ? "Known" : "New")
                    }

                    TableColumn("") { device in
                        Button("Edit") {
                            editingDevice = device
                        }
                    }
                }
            }

            Spacer()
        }
        .padding(28)
        .sheet(item: $editingDevice) { device in
            DeviceDetailView(device: device) { updatedDevice in
                appModel.updateDevice(updatedDevice)
                editingDevice = nil
            }
        }
    }

    private var emptyDevicesView: some View {
        ZStack {
            Color.clear

            ContentUnavailableView(
                "No Devices",
                systemImage: "desktopcomputer.and.macbook",
                description: Text("Run a scan from the dashboard to read the local ARP table.")
            )
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    private func portSummary(for ports: [Int]) -> String {
        guard !ports.isEmpty else { return "-" }
        return ports.map(String.init).joined(separator: ", ")
    }

    private func riskColor(for risk: DeviceRisk) -> Color {
        switch risk {
        case .low:
            .green
        case .medium:
            .orange
        case .high:
            .red
        }
    }
}

private struct DeviceDetailView: View {
    let originalDevice: NetworkDevice
    let onSave: (NetworkDevice) -> Void

    @Environment(\.dismiss) private var dismiss
    @State private var name: String
    @State private var isKnown: Bool
    @State private var iconName: String

    init(device: NetworkDevice, onSave: @escaping (NetworkDevice) -> Void) {
        self.originalDevice = device
        self.onSave = onSave
        _name = State(initialValue: device.name)
        _isKnown = State(initialValue: device.isKnown)
        _iconName = State(initialValue: device.displayIconName)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 20) {
            HeaderView(
                title: originalDevice.name,
                subtitle: originalDevice.ipAddress
            )

            Form {
                Section("Editable") {
                    TextField("Name", text: $name)
                    Toggle("Known device", isOn: $isKnown)
                    IconPicker(selection: $iconName)
                }

                Section("Network") {
                    DetailRow(title: "Status", value: originalDevice.status.title)
                    DetailRow(title: "IP address", value: originalDevice.ipAddress)
                    DetailRow(title: "MAC address", value: originalDevice.macAddress)
                    DetailRow(title: "Hostname", value: originalDevice.hostname ?? "-")
                    DetailRow(title: "Vendor", value: originalDevice.vendor ?? "-")
                    DetailRow(title: "Role", value: originalDevice.isGateway ? "Gateway" : "Device")
                    DetailRow(title: "Open ports", value: portSummary(for: originalDevice.openPorts))
                    DetailRow(title: "Risk", value: originalDevice.risk.title)
                }

                Section("Timeline") {
                    DetailRow(title: "First seen", value: originalDevice.firstSeen.formatted(date: .abbreviated, time: .shortened))
                    DetailRow(title: "Last seen", value: originalDevice.lastSeen.formatted(date: .abbreviated, time: .shortened))
                }
            }
            .formStyle(.grouped)

            HStack {
                Spacer()

                Button("Cancel") {
                    dismiss()
                }

                Button("Save") {
                    var updatedDevice = originalDevice
                    updatedDevice.name = trimmedName
                    updatedDevice.isKnown = isKnown
                    updatedDevice.iconName = iconName
                    updatedDevice.risk = DeviceRiskScorer.risk(
                        for: updatedDevice.openPorts,
                        isKnown: updatedDevice.isKnown
                    )
                    onSave(updatedDevice)
                }
                .buttonStyle(.borderedProminent)
                .disabled(trimmedName.isEmpty)
            }
        }
        .padding(24)
        .frame(width: 560, height: 620)
    }

    private var trimmedName: String {
        name.trimmingCharacters(in: .whitespacesAndNewlines)
    }

    private func portSummary(for ports: [Int]) -> String {
        guard !ports.isEmpty else { return "-" }
        return ports.map(String.init).joined(separator: ", ")
    }
}

private struct IconPicker: View {
    @Binding var selection: String

    var body: some View {
        Picker("Icon", selection: $selection) {
            ForEach(DeviceIconCatalog.options) { option in
                Label(option.title, systemImage: option.systemImage)
                    .tag(option.systemImage)
            }
        }
        .pickerStyle(.menu)
    }
}

private struct DetailRow: View {
    let title: String
    let value: String

    var body: some View {
        HStack(alignment: .firstTextBaseline) {
            Text(title)
                .foregroundStyle(.secondary)
            Spacer()
            Text(value)
                .multilineTextAlignment(.trailing)
                .textSelection(.enabled)
        }
    }
}

#Preview {
    DevicesView()
        .environment(AppModel())
        .frame(width: 980, height: 640)
}
