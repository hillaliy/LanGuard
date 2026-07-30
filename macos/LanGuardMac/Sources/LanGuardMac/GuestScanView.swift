import SwiftUI

struct GuestScanView: View {
    @Environment(AppModel.self) private var appModel
    @State private var scanRange = AppSettings.default.defaultScanRange
    @State private var tcpPorts = AppSettings.default.defaultPortsText
    @State private var validationMessage: String?
    private let guestNetworkCardHeight: CGFloat = 172
    private let guestSummaryCardHeight: CGFloat = 190

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 24) {
                HeaderView(
                    title: "Guest Scan",
                    subtitle: "Scan a temporary network without saving devices."
                )

                guestNotice

                HStack(alignment: .top, spacing: 18) {
                    scanControls
                        .frame(minWidth: 360, idealWidth: 440, maxWidth: 520)
                        .frame(height: guestNetworkCardHeight)
                        .offset(y: 4)

                    guestScanSummary
                        .frame(minWidth: 300, maxWidth: .infinity)
                        .frame(height: guestSummaryCardHeight)
                        .offset(y: -4)
                }
                .padding(.top, 8)

                resultsSection
            }
            .frame(maxWidth: 1320, alignment: .leading)
            .padding(28)
        }
        .onAppear {
            scanRange = appModel.settings.defaultScanRange
            tcpPorts = appModel.settings.portsText
        }
    }

    private var guestNotice: some View {
        HStack(alignment: .top, spacing: 12) {
            Image(systemName: "info.circle")
                .foregroundStyle(.blue)
                .font(.title3)

            VStack(alignment: .leading, spacing: 4) {
                Text("Temporary scan")
                    .font(.headline)
                Text("Guest scan results stay in memory only. They are not merged into your saved devices, do not create history, and are cleared when LanGuard closes.")
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(.blue.opacity(0.08), in: RoundedRectangle(cornerRadius: 16))
        .overlay {
            RoundedRectangle(cornerRadius: 16)
                .stroke(.blue.opacity(0.18))
        }
    }

    private var scanControls: some View {
        VStack(alignment: .leading, spacing: 11) {
            Label("Guest network", systemImage: "person.crop.circle")
                .font(.headline)

            VStack(alignment: .leading, spacing: 5) {
                Text("CIDR range")
                    .font(.caption.weight(.semibold))
                TextField("192.168.0.0/24", text: $scanRange)
                    .textFieldStyle(.roundedBorder)
            }

            VStack(alignment: .leading, spacing: 5) {
                Text("TCP ports")
                    .font(.caption.weight(.semibold))
                TextField("22, 80, 443", text: $tcpPorts)
                    .lineLimit(1)
                    .textFieldStyle(.roundedBorder)
            }

            if let validationMessage {
                Text(validationMessage)
                    .font(.caption)
                    .foregroundStyle(.red)
            }

            HStack {
                Button {
                    runGuestScan()
                } label: {
                    Label(appModel.isGuestScanning ? "Scanning" : "Run Guest Scan", systemImage: "arrow.clockwise")
                }
                .buttonStyle(.borderedProminent)
                .disabled(appModel.isScanning || appModel.isGuestScanning)

                Button {
                    appModel.clearGuestScan()
                    validationMessage = nil
                } label: {
                    Label("Clear", systemImage: "trash")
                }
                .buttonStyle(.bordered)
                .disabled(appModel.guestDevices.isEmpty && appModel.guestScan == nil)
            }
        }
        .padding(16)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        .background(.background.secondary, in: RoundedRectangle(cornerRadius: 18))
        .overlay {
            RoundedRectangle(cornerRadius: 18)
                .stroke(.quaternary)
        }
    }

    private var guestScanSummary: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack {
                Label("Latest Guest Scan", systemImage: "clock")
                    .font(.headline)

                Spacer()

                if let scan = appModel.guestScan {
                    Text(scan.status.rawValue.capitalized)
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(color(for: scan.status))
                        .padding(.horizontal, 10)
                        .padding(.vertical, 5)
                        .background(color(for: scan.status).opacity(0.14), in: Capsule())
                }
            }

            if let scan = appModel.guestScan {
                VStack(alignment: .leading, spacing: 10) {
                    SummaryLine(title: "Devices", value: "\(scan.discoveredCount)")
                    SummaryLine(title: "Duration", value: formattedDuration(scan.duration))
                    SummaryLine(title: "Started", value: scan.startedAt.formatted(date: .abbreviated, time: .shortened))
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .leading)

                if let errorMessage = scan.errorMessage ?? appModel.guestErrorMessage {
                    Text(errorMessage)
                        .font(.callout)
                        .foregroundStyle(.red)
                }
            } else {
                ContentUnavailableView(
                    "No guest scan yet",
                    systemImage: "network",
                    description: Text("Run a scan against a guest or client network.")
                )
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            }
        }
        .padding(16)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        .background(.background.secondary, in: RoundedRectangle(cornerRadius: 18))
        .overlay {
            RoundedRectangle(cornerRadius: 18)
                .stroke(.quaternary)
        }
    }

    private var resultsSection: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack {
                Label("Guest Results", systemImage: "list.bullet.rectangle")
                    .font(.title3.weight(.semibold))

                Spacer()

                Text("\(appModel.guestDevices.count)")
                    .font(.caption.weight(.bold))
                    .foregroundStyle(.blue)
                    .padding(.horizontal, 10)
                    .padding(.vertical, 6)
                    .background(.blue.opacity(0.14), in: Capsule())
            }

            if appModel.guestDevices.isEmpty {
                ContentUnavailableView(
                    "No Guest Devices",
                    systemImage: "desktopcomputer.and.macbook",
                    description: Text("Discovered devices from the temporary scan will appear here.")
                )
                .frame(maxWidth: .infinity, minHeight: 280)
                .background(.background.secondary, in: RoundedRectangle(cornerRadius: 18))
                .overlay {
                    RoundedRectangle(cornerRadius: 18)
                        .stroke(.quaternary)
                }
            } else {
                VStack(spacing: 0) {
                    ForEach(appModel.guestDevices) { device in
                        GuestDeviceRow(device: device)

                        if device.id != appModel.guestDevices.last?.id {
                            Divider()
                                .padding(.leading, 52)
                        }
                    }
                }
                .padding(.vertical, 8)
                .background(.background.secondary, in: RoundedRectangle(cornerRadius: 18))
                .overlay {
                    RoundedRectangle(cornerRadius: 18)
                        .stroke(.quaternary)
                }
            }
        }
    }

    private func runGuestScan() {
        let range = scanRange.trimmingCharacters(in: .whitespacesAndNewlines)
        guard IPv4CIDRRange(range) != nil else {
            validationMessage = "Enter a valid IPv4 CIDR range, like 192.168.0.0/24."
            return
        }

        guard let ports = AppSettings.parsePorts(tcpPorts) else {
            validationMessage = "Enter valid TCP ports between 1 and 65535."
            return
        }

        validationMessage = nil
        appModel.runGuestScan(range: range, ports: ports)
    }

    private func color(for status: ScanRecord.Status) -> Color {
        switch status {
        case .running:
            .blue
        case .completed:
            .green
        case .failed:
            .red
        }
    }

    private func formattedDuration(_ duration: TimeInterval?) -> String {
        guard let duration else { return "-" }
        return Self.durationFormatter.string(from: duration) ?? "-"
    }

    private static let durationFormatter: DateComponentsFormatter = {
        let formatter = DateComponentsFormatter()
        formatter.allowedUnits = [.hour, .minute, .second]
        formatter.unitsStyle = .abbreviated
        return formatter
    }()
}

private struct SummaryLine: View {
    let title: String
    let value: String

    var body: some View {
        HStack(alignment: .firstTextBaseline, spacing: 4) {
            Text("\(title):")
                .foregroundStyle(.secondary)
            Text(value)
                .fontWeight(.semibold)
        }
        .font(.callout)
        .lineLimit(1)
        .minimumScaleFactor(0.82)
    }
}

private struct GuestDeviceRow: View {
    let device: NetworkDevice

    var body: some View {
        HStack(alignment: .center, spacing: 14) {
            Image(systemName: device.iconName ?? "questionmark.circle")
                .font(.system(size: 20, weight: .medium))
                .foregroundStyle(.blue)
                .frame(width: 28)

            VStack(alignment: .leading, spacing: 6) {
                HStack(spacing: 8) {
                    Circle()
                        .fill(device.status == .online ? .green : .secondary)
                        .frame(width: 8, height: 8)

                    Text(device.name)
                        .font(.headline)
                        .lineLimit(1)

                    if device.isGateway {
                        Text("Gateway")
                            .font(.caption.weight(.semibold))
                            .foregroundStyle(.blue)
                            .padding(.horizontal, 8)
                            .padding(.vertical, 3)
                            .background(.blue.opacity(0.12), in: Capsule())
                    }
                }

                HStack(spacing: 10) {
                    Text(device.ipAddress)
                    Text(device.macAddress)
                    Text(portSummary(for: device.openPorts))
                    if let vendor = device.vendor, !vendor.isEmpty {
                        Text(vendor)
                            .lineLimit(1)
                            .truncationMode(.tail)
                    }
                }
                .font(.caption)
                .foregroundStyle(.secondary)
            }

            Spacer(minLength: 12)

            Text(device.risk.title)
                .font(.caption.weight(.bold))
                .foregroundStyle(riskColor(for: device.risk))
                .padding(.horizontal, 10)
                .padding(.vertical, 5)
                .background(riskColor(for: device.risk).opacity(0.14), in: Capsule())
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 10)
    }

    private func portSummary(for ports: [Int]) -> String {
        ports.isEmpty ? "-" : ports.map(String.init).joined(separator: ", ")
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

private extension AppSettings {
    var portsText: String {
        tcpPorts.map(String.init).joined(separator: ", ")
    }

    var defaultPortsText: String {
        tcpPorts.map(String.init).joined(separator: ", ")
    }
}

#Preview {
    GuestScanView()
        .environment(AppModel())
        .frame(width: 1100, height: 720)
}
