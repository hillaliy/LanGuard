import SwiftUI

struct DashboardView: View {
    @Environment(AppModel.self) private var appModel
    @State private var editingDevice: NetworkDevice?
    @State private var showingLatestScanDetails = false

    var body: some View {
        ScrollView {
            ViewThatFits(in: .horizontal) {
                dashboardContent(isCompact: false)
                dashboardContent(isCompact: true)
            }
            .padding(32)
            .frame(maxWidth: 1540, alignment: .leading)
        }
        .sheet(item: $editingDevice) { device in
            DeviceDetailView(device: device, rooms: appModel.settings.rooms) { updatedDevice in
                appModel.updateDevice(updatedDevice)
                editingDevice = nil
            } onDelete: { device in
                appModel.deleteDevice(device)
                editingDevice = nil
            }
        }
        .sheet(isPresented: $showingLatestScanDetails) {
            if let latestScan = appModel.latestScan {
                ScanDetailsSheet(scan: latestScan)
            }
        }
    }

    private func dashboardContent(isCompact: Bool) -> some View {
        VStack(alignment: .leading, spacing: 24) {
            HeroPanel(
                isScanning: appModel.isScanning,
                latestScan: appModel.latestScan,
                runScan: appModel.runScan
            )
            .padding(.bottom, isCompact ? 0 : 6)

            if let lastErrorMessage = appModel.lastErrorMessage {
                ErrorBanner(message: lastErrorMessage)
            }

            if isCompact {
                compactMetricGrid
                compactLowerContent
            } else {
                wideDashboardGrid
            }
        }
    }

    private var wideDashboardGrid: some View {
        Grid(alignment: .topLeading, horizontalSpacing: 18, verticalSpacing: 18) {
            GridRow {
                metricCards

                NetworkHealthCard(
                    devices: appModel.devices.count,
                    online: appModel.onlineCount,
                    unknown: appModel.unknownCount,
                    openPorts: appModel.openPortCount
                )
                .gridCellColumns(1)
            }

            GridRow {
                RecentlyChangedCard(changes: visibleRecentChanges, maximumItems: 8, fixedHeight: 328)
                    .padding(.top, 12)
                    .gridCellColumns(2)

                WatchListCard(devices: appModel.devices, fixedHeight: 328) { device in
                    editingDevice = device
                }
                    .padding(.top, 12)
                    .gridCellAnchor(.topLeading)
                    .gridCellColumns(2)

                VStack(alignment: .leading, spacing: 18) {
                    scheduleCard
                    latestScanSummaryContent
                }
                .padding(.top, 12)
                .gridCellColumns(1)
            }
        }
        .frame(minWidth: 1420, maxWidth: .infinity, alignment: .leading)
    }

    private var compactMetricGrid: some View {
        VStack(alignment: .leading, spacing: 24) {
            LazyVGrid(
                columns: Array(repeating: GridItem(.flexible(minimum: 0), spacing: 14), count: 4),
                spacing: 14
            ) {
                compactMetricCards
            }

            compactOverviewRow
        }
    }

    private var compactOverviewRow: some View {
        HStack(alignment: .top, spacing: 14) {
            CompactNetworkHealthCard(
                devices: appModel.devices.count,
                online: appModel.onlineCount,
                unknown: appModel.unknownCount,
                openPorts: appModel.openPortCount
            )

            CompactScheduleCard(
                isEnabled: appModel.settings.scheduledScanningEnabled,
                intervalMinutes: appModel.settings.scanIntervalMinutes,
                nextScanAt: appModel.nextScheduledScanAt
            )

            compactLatestScanCard
        }
    }

    private var compactLowerContent: some View {
        HStack(alignment: .top, spacing: 14) {
            RecentlyChangedCard(changes: visibleRecentChanges, maximumItems: 8, fixedHeight: 292)
            WatchListCard(devices: appModel.devices, fixedHeight: 292) { device in
                editingDevice = device
            }
        }
    }

    private var visibleRecentChanges: [DeviceChange] {
        guard !appModel.devices.isEmpty else { return [] }
        let deviceIDs = Set(appModel.devices.map(\.id))
        return appModel.recentChanges.filter { deviceIDs.contains($0.deviceID) }
    }

    @ViewBuilder
    private var metricCards: some View {
        SummaryCard(
            title: "Devices",
            value: "\(appModel.devices.count)",
            systemImage: "desktopcomputer",
            tint: .blue
        )
        SummaryCard(
            title: "Online",
            value: "\(appModel.onlineCount)",
            systemImage: "wifi",
            tint: .green
        )
        SummaryCard(
            title: "Unknown",
            value: "\(appModel.unknownCount)",
            systemImage: "questionmark.circle",
            tint: .orange
        )
        SummaryCard(
            title: "Open Ports",
            value: "\(appModel.openPortCount)",
            systemImage: "point.3.connected.trianglepath.dotted",
            tint: .purple
        )
    }
    
    @ViewBuilder
    private var compactMetricCards: some View {
        CompactSummaryCard(
            title: "Devices",
            value: "\(appModel.devices.count)",
            systemImage: "desktopcomputer",
            tint: .blue
        )
        CompactSummaryCard(
            title: "Online",
            value: "\(appModel.onlineCount)",
            systemImage: "wifi",
            tint: .green
        )
        CompactSummaryCard(
            title: "Unknown",
            value: "\(appModel.unknownCount)",
            systemImage: "questionmark.circle",
            tint: .orange
        )
        CompactSummaryCard(
            title: "Open Ports",
            value: "\(appModel.openPortCount)",
            systemImage: "point.3.connected.trianglepath.dotted",
            tint: .purple
        )
    }

    @ViewBuilder
    private var latestScanContent: some View {
        if let latestScan = appModel.latestScan {
            LatestScanCard(scan: latestScan) {
                showingLatestScanDetails = true
            }
        } else {
            EmptyScanCard()
        }
    }

    @ViewBuilder
    private var latestScanSummaryContent: some View {
        if let latestScan = appModel.latestScan {
            LatestScanSummaryCard(scan: latestScan) {
                showingLatestScanDetails = true
            }
        } else {
            EmptyScanSummaryCard()
        }
    }

    @ViewBuilder
    private var compactLatestScanCard: some View {
        if let latestScan = appModel.latestScan {
            CompactLatestScanCard(scan: latestScan) {
                showingLatestScanDetails = true
            }
        } else {
            CompactEmptyScanCard()
        }
    }

    private var scheduleCard: some View {
        ScheduleCard(
            isEnabled: appModel.settings.scheduledScanningEnabled,
            intervalMinutes: appModel.settings.scanIntervalMinutes,
            nextScanAt: appModel.nextScheduledScanAt
        )
    }
}

private struct HeroPanel: View {
    let isScanning: Bool
    let latestScan: ScanRecord?
    let runScan: () -> Void

    var body: some View {
        ViewThatFits(in: .horizontal) {
            HStack(alignment: .center, spacing: 24) {
                header

                Spacer()

                scanButton
            }

            VStack(alignment: .leading, spacing: 18) {
                header

                scanButton
                    .frame(maxWidth: .infinity, alignment: .trailing)
            }
        }
        .padding(22)
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 18))
        .overlay {
            RoundedRectangle(cornerRadius: 18)
                .stroke(.quaternary)
        }
    }

    private var header: some View {
        HeaderView(
            title: "LanGuard",
            subtitle: "Local network watch for macOS",
            assetImage: "LanGuardIcon",
            version: AppVersion.current
        )
    }

    private var scanButton: some View {
        Button {
            runScan()
        } label: {
            Label(isScanning ? "Scanning" : "Run Scan", systemImage: "arrow.clockwise")
                .frame(minWidth: 118)
        }
        .controlSize(.large)
        .buttonStyle(.borderedProminent)
        .disabled(isScanning)
    }
}

private struct ScheduleCard: View {
    let isEnabled: Bool
    let intervalMinutes: Int
    let nextScanAt: Date?

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            HStack(spacing: 12) {
                Image(systemName: "calendar.badge.clock")
                    .font(.system(size: 22, weight: .semibold))
                    .foregroundStyle(isEnabled ? .blue : .secondary)
                    .frame(width: 38, height: 38)
                    .background((isEnabled ? Color.blue : Color.secondary).opacity(0.14), in: RoundedRectangle(cornerRadius: 10))

                VStack(alignment: .leading, spacing: 4) {
                    Text(isEnabled ? "Automatic Scanning" : "Automatic Scanning Off")
                        .font(.headline)
                    Text(isEnabled ? "Enabled" : "Disabled")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }

            Spacer()

            HStack(alignment: .bottom) {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Interval")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    Text(isEnabled ? "\(intervalMinutes) min" : "-")
                        .font(.headline)
                }

                Spacer()

                VStack(alignment: .trailing, spacing: 4) {
                    Text("Next Scan")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    Text(isEnabled ? nextScanAt?.formatted(date: .omitted, time: .shortened) ?? "-" : "-")
                        .font(.headline)
                        .monospacedDigit()
                }
            }
        }
        .padding(22)
        .frame(maxWidth: .infinity, minHeight: 160, maxHeight: 160, alignment: .leading)
        .background(.background.secondary, in: RoundedRectangle(cornerRadius: 18))
        .overlay {
            RoundedRectangle(cornerRadius: 18)
                .stroke(.quaternary)
        }
    }
}

private struct NetworkHealthCard: View {
    let devices: Int
    let online: Int
    let unknown: Int
    let openPorts: Int

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack {
                Label("Network Health", systemImage: "waveform.path.ecg.rectangle")
                    .font(.title3.weight(.semibold))
                Spacer()
                Text(healthTitle)
                    .font(.caption.weight(.bold))
                    .padding(.horizontal, 10)
                    .padding(.vertical, 5)
                    .background(healthColor.opacity(0.16), in: Capsule())
                    .foregroundStyle(healthColor)
            }

            ProgressView(value: knownCoverageScore)
                .tint(healthColor)

            VStack(spacing: 7) {
                HealthRow(title: "Known coverage", value: "\(knownPercent)%")
                HealthRow(title: "Online devices", value: "\(online)")
                HealthRow(title: "Open ports", value: "\(openPorts)")
            }
        }
        .padding(22)
        .frame(minHeight: 160, maxHeight: 160)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(.background.secondary, in: RoundedRectangle(cornerRadius: 18))
        .overlay {
            RoundedRectangle(cornerRadius: 18)
                .stroke(.quaternary)
        }
    }

    private var knownPercent: Int {
        guard devices > 0 else { return 0 }
        return Int((Double(devices - unknown) / Double(devices) * 100).rounded())
    }

    private var knownCoverageScore: Double {
        guard devices > 0 else { return 0 }
        return max(0.0, min(1.0, Double(devices - unknown) / Double(devices)))
    }

    private var healthScore: Double {
        guard devices > 0 else { return 0 }
        let unknownPenalty = Double(unknown) / Double(devices)
        let portPenalty = min(Double(openPorts) / 80.0, 1.0) * 0.35
        return max(0.0, min(1.0, 1.0 - unknownPenalty - portPenalty))
    }

    private var healthTitle: String {
        switch healthScore {
        case 0.75...:
            "Good"
        case 0.45..<0.75:
            "Review"
        default:
            "Needs Work"
        }
    }

    private var healthColor: Color {
        switch healthScore {
        case 0.75...:
            .green
        case 0.45..<0.75:
            .orange
        default:
            .red
        }
    }
}

private struct HealthRow: View {
    let title: String
    let value: String

    var body: some View {
        HStack {
            Text(title)
                .foregroundStyle(.secondary)
            Spacer()
            Text(value)
                .fontWeight(.semibold)
                .monospacedDigit()
        }
        .font(.subheadline)
    }
}

private struct CompactNetworkHealthCard: View {
    let devices: Int
    let online: Int
    let unknown: Int
    let openPorts: Int

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(alignment: .center, spacing: 8) {
                Image(systemName: "waveform.path.ecg.rectangle")
                    .font(.system(size: 17, weight: .semibold))
                    .frame(width: 24)

                Text("Network Health")
                    .font(.headline.weight(.semibold))
                    .lineLimit(1)
                    .minimumScaleFactor(0.7)

                Spacer(minLength: 4)

                Text(healthTitle)
                    .font(.caption.weight(.bold))
                    .padding(.horizontal, 8)
                    .padding(.vertical, 4)
                    .background(healthColor.opacity(0.16), in: Capsule())
                    .foregroundStyle(healthColor)
                    .lineLimit(1)
            }

            ProgressView(value: knownCoverageScore)
                .tint(healthColor)

            VStack(spacing: 7) {
                CompactHealthRow(title: "Known", value: "\(knownPercent)%")
                CompactHealthRow(title: "Online", value: "\(online)")
                CompactHealthRow(title: "Ports", value: "\(openPorts)")
            }
        }
        .padding(16)
        .frame(maxWidth: .infinity, minHeight: 150, maxHeight: 150, alignment: .leading)
        .background(.background.secondary, in: RoundedRectangle(cornerRadius: 18))
        .overlay {
            RoundedRectangle(cornerRadius: 18)
                .stroke(.quaternary)
        }
    }

    private var knownPercent: Int {
        guard devices > 0 else { return 0 }
        return Int((Double(devices - unknown) / Double(devices) * 100).rounded())
    }

    private var knownCoverageScore: Double {
        guard devices > 0 else { return 0 }
        return max(0.0, min(1.0, Double(devices - unknown) / Double(devices)))
    }

    private var healthScore: Double {
        guard devices > 0 else { return 0 }
        let unknownPenalty = Double(unknown) / Double(devices)
        let portPenalty = min(Double(openPorts) / 80.0, 1.0) * 0.35
        return max(0.0, min(1.0, 1.0 - unknownPenalty - portPenalty))
    }

    private var healthTitle: String {
        switch healthScore {
        case 0.75...:
            "Good"
        case 0.45..<0.75:
            "Review"
        default:
            "Needs Work"
        }
    }

    private var healthColor: Color {
        switch healthScore {
        case 0.75...:
            .green
        case 0.45..<0.75:
            .orange
        default:
            .red
        }
    }
}

private struct CompactHealthRow: View {
    let title: String
    let value: String

    var body: some View {
        HStack(spacing: 8) {
            Text(title)
                .foregroundStyle(.secondary)
                .lineLimit(1)
            Spacer(minLength: 4)
            Text(value)
                .fontWeight(.semibold)
                .monospacedDigit()
                .lineLimit(1)
        }
        .font(.caption)
    }
}

private struct CompactScheduleCard: View {
    let isEnabled: Bool
    let intervalMinutes: Int
    let nextScanAt: Date?

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 9) {
                Image(systemName: "calendar.badge.clock")
                    .font(.system(size: 18, weight: .semibold))
                    .foregroundStyle(isEnabled ? .blue : .secondary)
                    .frame(width: 34, height: 34)
                    .background((isEnabled ? Color.blue : Color.secondary).opacity(0.14), in: RoundedRectangle(cornerRadius: 10))

                VStack(alignment: .leading, spacing: 3) {
                    Text(isEnabled ? "Automatic Scanning" : "Scanning Off")
                        .font(.headline.weight(.semibold))
                        .lineLimit(1)
                        .minimumScaleFactor(0.65)
                    Text(isEnabled ? "Enabled" : "Disabled")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }

            Spacer(minLength: 4)

            HStack(alignment: .bottom, spacing: 10) {
                CompactScheduleMetric(title: "Interval", value: isEnabled ? "\(intervalMinutes) min" : "-")
                Spacer(minLength: 4)
                CompactScheduleMetric(
                    title: "Next",
                    value: isEnabled ? nextScanAt?.formatted(date: .omitted, time: .shortened) ?? "-" : "-",
                    alignment: .trailing
                )
            }
        }
        .padding(16)
        .frame(maxWidth: .infinity, minHeight: 150, maxHeight: 150, alignment: .leading)
        .background(.background.secondary, in: RoundedRectangle(cornerRadius: 18))
        .overlay {
            RoundedRectangle(cornerRadius: 18)
                .stroke(.quaternary)
        }
    }
}

private struct CompactScheduleMetric: View {
    let title: String
    let value: String
    var alignment: HorizontalAlignment = .leading

    var body: some View {
        VStack(alignment: alignment, spacing: 4) {
            Text(title)
                .font(.caption)
                .foregroundStyle(.secondary)
                .lineLimit(1)
            Text(value)
                .font(.headline)
                .monospacedDigit()
                .lineLimit(1)
                .minimumScaleFactor(0.8)
        }
    }
}

private struct WatchListCard: View {
    let devices: [NetworkDevice]
    private let maximumItems = 8
    var fixedHeight: CGFloat?
    var onSelectDevice: (NetworkDevice) -> Void = { _ in }

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                Label("Needs Attention", systemImage: "exclamationmark.shield")
                    .font(.title3.weight(.semibold))

                Spacer()

                Text("\(attentionDevices.count)")
                    .font(.caption.weight(.bold))
                    .padding(.horizontal, 10)
                    .padding(.vertical, 5)
                    .background(.orange.opacity(0.16), in: Capsule())
                    .foregroundStyle(.orange)
            }

            if attentionDevices.isEmpty {
                VStack(alignment: .leading, spacing: 8) {
                    Text("Nothing urgent")
                        .font(.headline)
                    Text("Unknown or high-risk devices will appear here.")
                        .font(.callout)
                        .foregroundStyle(.secondary)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.vertical, 6)
            } else {
                ScrollView {
                    VStack(alignment: .leading, spacing: 8) {
                        ForEach(attentionDevices) { device in
                            Button {
                                onSelectDevice(device)
                            } label: {
                                HStack(spacing: 12) {
                                    Image(systemName: device.risk == .high ? "exclamationmark.triangle" : "questionmark.circle")
                                        .foregroundStyle(device.risk == .high ? .red : .orange)
                                        .frame(width: 24)

                                    VStack(alignment: .leading, spacing: 3) {
                                        Text(device.name)
                                            .font(.headline)
                                            .lineLimit(1)
                                            .truncationMode(.tail)
                                        Text(device.ipAddress)
                                            .font(.caption)
                                            .foregroundStyle(.secondary)
                                    }

                                    Spacer()

                                    Text(device.risk.title)
                                        .font(.caption.weight(.bold))
                                        .padding(.horizontal, 8)
                                        .padding(.vertical, 4)
                                        .background((device.risk == .high ? Color.red : Color.orange).opacity(0.16), in: Capsule())
                                        .foregroundStyle(device.risk == .high ? .red : .orange)
                                }
                                .contentShape(Rectangle())
                            }
                            .buttonStyle(.plain)
                            .padding(.vertical, 1)
                        }
                    }
                    .padding(.bottom, 8)
                    .frame(maxWidth: .infinity, alignment: .leading)
                }
                .scrollIndicators(.visible)
            }
        }
        .padding(22)
        .frame(maxWidth: .infinity, minHeight: fixedHeight, maxHeight: fixedHeight, alignment: .leading)
        .background(.background.secondary, in: RoundedRectangle(cornerRadius: 18))
        .overlay {
            RoundedRectangle(cornerRadius: 18)
                .stroke(.quaternary)
        }
    }

    private var attentionDevices: [NetworkDevice] {
        devices
            .filter { !$0.isKnown || $0.risk == .high }
            .sorted { left, right in
                if left.risk != right.risk {
                    return left.risk.sortRank > right.risk.sortRank
                }
                return left.lastSeen > right.lastSeen
            }
            .prefix(maximumItems)
            .map { $0 }
    }
}

private struct RecentlyChangedCard: View {
    let changes: [DeviceChange]
    let maximumItems: Int
    var fixedHeight: CGFloat?

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack {
                Label("Recently Changed", systemImage: "clock.badge.exclamationmark")
                    .font(.title3.weight(.semibold))

                Spacer()

                Text("\(displayChanges.count)")
                    .font(.caption.weight(.bold))
                    .padding(.horizontal, 10)
                    .padding(.vertical, 5)
                    .background(.blue.opacity(0.16), in: Capsule())
                    .foregroundStyle(.blue)
            }

            if displayChanges.isEmpty {
                VStack(alignment: .leading, spacing: 8) {
                    Text("No recent changes")
                        .font(.headline)
                    Text("IP, port, and risk changes will appear here.")
                        .font(.callout)
                        .foregroundStyle(.secondary)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.vertical, 6)
            } else {
                ScrollView {
                    VStack(alignment: .leading, spacing: 8) {
                        ForEach(displayChanges) { change in
                            HStack(spacing: 12) {
                                Image(systemName: iconName(for: change.kind))
                                    .foregroundStyle(.blue)
                                    .frame(width: 24)

                                VStack(alignment: .leading, spacing: 3) {
                                    Text(change.deviceName)
                                        .font(.headline)
                                        .lineLimit(1)
                                        .truncationMode(.tail)
                                    Text("\(change.kind.title) • \(change.ipAddress)")
                                        .font(.caption)
                                        .foregroundStyle(.secondary)
                                }

                                Spacer()
                            }
                            .padding(.vertical, 1)
                        }
                    }
                    .padding(.bottom, 8)
                    .frame(maxWidth: .infinity, alignment: .leading)
                }
                .scrollIndicators(.visible)
            }
        }
        .padding(22)
        .frame(maxWidth: .infinity, minHeight: fixedHeight, maxHeight: fixedHeight, alignment: .leading)
        .background(.background.secondary, in: RoundedRectangle(cornerRadius: 18))
        .overlay {
            RoundedRectangle(cornerRadius: 18)
                .stroke(.quaternary)
        }
    }

    private var displayChanges: [DeviceChange] {
        Array(changes.prefix(maximumItems))
    }

    private func iconName(for kind: DeviceChange.ChangeKind) -> String {
        switch kind {
        case .ipAddress:
            "network"
        case .ports:
            "point.3.connected.trianglepath.dotted"
        case .risk:
            "exclamationmark.shield"
        }
    }
}

private struct ScanStatusBadge: View {
    let isScanning: Bool
    let latestScan: ScanRecord?

    var body: some View {
        Label(title, systemImage: systemImage)
            .font(.caption.weight(.semibold))
            .padding(.horizontal, 12)
            .padding(.vertical, 7)
            .background(color.opacity(0.16), in: Capsule())
            .foregroundStyle(color)
    }

    private var title: String {
        if isScanning { return "Scanning" }
        guard let latestScan else { return "Ready" }
        return latestScan.status.rawValue.capitalized
    }

    private var systemImage: String {
        if isScanning { return "arrow.clockwise" }
        switch latestScan?.status {
        case .completed:
            return "checkmark.circle"
        case .failed:
            return "exclamationmark.triangle"
        case .running:
            return "arrow.clockwise"
        case nil:
            return "circle.dotted"
        }
    }

    private var color: Color {
        if isScanning { return .blue }
        switch latestScan?.status {
        case .completed:
            return .green
        case .failed:
            return .red
        case .running:
            return .blue
        case nil:
            return .secondary
        }
    }
}

private struct ErrorBanner: View {
    let message: String

    var body: some View {
        Label(message, systemImage: "exclamationmark.triangle")
            .font(.callout)
            .foregroundStyle(.red)
            .padding(14)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(.red.opacity(0.1), in: RoundedRectangle(cornerRadius: 12))
    }
}

private struct EmptyScanCard: View {
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Image(systemName: "network")
                .font(.system(size: 32, weight: .semibold))
                .foregroundStyle(.secondary)

            Text("No Scans Yet")
                .font(.title3.weight(.semibold))

            Text("Run the first local scan to populate devices from the ARP table.")
                .foregroundStyle(.secondary)
        }
        .padding(22)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(.background.secondary, in: RoundedRectangle(cornerRadius: 18))
        .overlay {
            RoundedRectangle(cornerRadius: 18)
                .stroke(.quaternary)
        }
    }
}

private struct EmptyScanSummaryCard: View {
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Label("Latest Scan", systemImage: "clock")
                .font(.headline)

            Spacer(minLength: 4)

            Text("No scans yet")
                .font(.headline)

            Text("Run a scan to populate devices.")
                .font(.caption)
                .foregroundStyle(.secondary)
                .lineLimit(2)
        }
        .padding(20)
        .frame(maxWidth: .infinity, minHeight: 150, maxHeight: 150, alignment: .leading)
        .background(.background.secondary, in: RoundedRectangle(cornerRadius: 18))
        .overlay {
            RoundedRectangle(cornerRadius: 18)
                .stroke(.quaternary)
        }
    }
}

private struct SummaryCard: View {
    let title: String
    let value: String
    let systemImage: String
    let tint: Color

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(alignment: .top) {
                Image(systemName: systemImage)
                    .font(.system(size: 21, weight: .semibold))
                    .foregroundStyle(tint)
                    .frame(width: 38, height: 38)
                    .background(tint.opacity(0.14), in: RoundedRectangle(cornerRadius: 10))

                Spacer()
            }

            Spacer(minLength: 2)

            VStack(alignment: .leading, spacing: 6) {
                Text(title)
                    .font(.callout.weight(.semibold))
                    .foregroundStyle(.secondary)

                Text(value)
                    .font(.system(size: 36, weight: .semibold, design: .rounded))
                    .monospacedDigit()
            }
        }
        .padding(20)
        .frame(maxWidth: .infinity, minHeight: 160, maxHeight: 160, alignment: .leading)
        .background(.background.secondary, in: RoundedRectangle(cornerRadius: 18))
        .overlay {
            RoundedRectangle(cornerRadius: 18)
                .stroke(.quaternary)
        }
    }
}

private struct CompactSummaryCard: View {
    let title: String
    let value: String
    let systemImage: String
    let tint: Color

    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: systemImage)
                .font(.system(size: 18, weight: .semibold))
                .foregroundStyle(tint)
                .frame(width: 34, height: 34)
                .background(tint.opacity(0.14), in: RoundedRectangle(cornerRadius: 10))

            VStack(alignment: .leading, spacing: 3) {
                Text(title)
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
                    .minimumScaleFactor(0.8)

                Text(value)
                    .font(.system(size: 30, weight: .semibold, design: .rounded))
                    .monospacedDigit()
            }

            Spacer()
        }
        .padding(14)
        .frame(maxWidth: .infinity, minHeight: 86, alignment: .leading)
        .background(.background.secondary, in: RoundedRectangle(cornerRadius: 18))
        .overlay {
            RoundedRectangle(cornerRadius: 18)
                .stroke(.quaternary)
        }
    }
}

private struct LatestScanCard: View {
    let scan: ScanRecord
    let showDetails: () -> Void

    var body: some View {
        Button(action: showDetails) {
            VStack(alignment: .leading, spacing: 20) {
                HStack {
                    Label("Latest Scan", systemImage: "clock")
                        .font(.title3.weight(.semibold))

                    Spacer()

                    ScanStatusBadge(isScanning: scan.status == .running, latestScan: scan)
                }

                Grid(alignment: .leading, horizontalSpacing: 32, verticalSpacing: 14) {
                    GridRow {
                        ScanMetric(title: "Status", value: scan.status.rawValue.capitalized)
                        ScanMetric(title: "Devices", value: "\(scan.discoveredCount)")
                        ScanMetric(title: "Started", value: scan.startedAt.formatted(date: .abbreviated, time: .shortened))
                    }

                    GridRow {
                        ScanMetric(title: "Finished", value: scan.finishedAt?.formatted(date: .abbreviated, time: .shortened) ?? "-")
                        ScanMetric(title: "Duration", value: formattedDuration(scan.duration))
                        ScanMetric(title: "Error", value: scan.errorMessage ?? "-")
                    }
                }
            }
            .padding(22)
            .frame(minHeight: 192, maxHeight: 192)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(.background.secondary, in: RoundedRectangle(cornerRadius: 18))
            .overlay {
                RoundedRectangle(cornerRadius: 18)
                    .stroke(.quaternary)
            }
        }
        .buttonStyle(.plain)
    }

    private func formattedDuration(_ duration: TimeInterval?) -> String {
        guard let duration else { return "-" }
        return Duration.seconds(duration).formatted(.time(pattern: .minuteSecond))
    }
}

private struct LatestScanSummaryCard: View {
    let scan: ScanRecord
    let showDetails: () -> Void

    var body: some View {
        Button(action: showDetails) {
            VStack(alignment: .leading, spacing: 14) {
                HStack {
                    Label("Latest Scan", systemImage: "clock")
                        .font(.headline)

                    Spacer()

                    ScanStatusBadge(isScanning: scan.status == .running, latestScan: scan)
                }

                Grid(alignment: .leading, horizontalSpacing: 18, verticalSpacing: 10) {
                    GridRow {
                        ScanMetric(title: "Devices", value: "\(scan.discoveredCount)")
                        ScanMetric(title: "Duration", value: formattedDuration(scan.duration))
                    }

                    GridRow {
                        ScanMetric(title: "Started", value: scan.startedAt.formatted(date: .omitted, time: .shortened))
                        ScanMetric(title: "Finished", value: scan.finishedAt?.formatted(date: .omitted, time: .shortened) ?? "-")
                    }
                }
            }
            .padding(20)
            .frame(maxWidth: .infinity, minHeight: 150, maxHeight: 150, alignment: .leading)
            .background(.background.secondary, in: RoundedRectangle(cornerRadius: 18))
            .overlay {
                RoundedRectangle(cornerRadius: 18)
                    .stroke(.quaternary)
            }
        }
        .buttonStyle(.plain)
    }

    private func formattedDuration(_ duration: TimeInterval?) -> String {
        guard let duration else { return "-" }
        return Duration.seconds(duration).formatted(.time(pattern: .minuteSecond))
    }
}

private struct CompactLatestScanCard: View {
    let scan: ScanRecord
    let showDetails: () -> Void

    var body: some View {
        Button(action: showDetails) {
            VStack(alignment: .leading, spacing: 12) {
                HStack(spacing: 8) {
                    Image(systemName: "clock")
                        .font(.system(size: 17, weight: .semibold))
                        .frame(width: 24)

                    Text("Latest Scan")
                        .font(.headline.weight(.semibold))
                        .lineLimit(1)
                        .minimumScaleFactor(0.7)
                        .layoutPriority(0)

                    Spacer(minLength: 4)

                    CompactScanStatusBadge(isScanning: scan.status == .running, latestScan: scan)
                        .layoutPriority(1)
                }

                Spacer(minLength: 2)

                Grid(alignment: .leading, horizontalSpacing: 12, verticalSpacing: 8) {
                    GridRow {
                        ScanMetric(title: "Devices", value: "\(scan.discoveredCount)")
                        ScanMetric(title: "Duration", value: formattedDuration(scan.duration))
                    }

                    GridRow {
                        ScanMetric(title: "Started", value: scan.startedAt.formatted(date: .omitted, time: .shortened))
                        ScanMetric(title: "Finished", value: scan.finishedAt?.formatted(date: .omitted, time: .shortened) ?? "-")
                    }
                }
            }
            .padding(16)
            .frame(maxWidth: .infinity, minHeight: 150, maxHeight: 150, alignment: .leading)
            .background(.background.secondary, in: RoundedRectangle(cornerRadius: 18))
            .overlay {
                RoundedRectangle(cornerRadius: 18)
                    .stroke(.quaternary)
            }
        }
        .buttonStyle(.plain)
    }

    private func formattedDuration(_ duration: TimeInterval?) -> String {
        guard let duration else { return "-" }
        return Duration.seconds(duration).formatted(.time(pattern: .minuteSecond))
    }
}

private struct ScanDetailsSheet: View {
    @Environment(\.dismiss) private var dismiss
    let scan: ScanRecord

    private let checks = [
        "Device discovery and online status checks",
        "Open port scanning for the configured TCP ports",
        "Hostname discovery using local network name protocols",
        "Metadata probing from device services when available",
        "Offline confirmation before a device is marked unavailable",
    ]

    var body: some View {
        VStack(alignment: .leading, spacing: 22) {
            HStack {
                Label("Latest Scan Details", systemImage: "clock")
                    .font(.title2.weight(.semibold))

                Spacer()

                Button("Done") {
                    dismiss()
                }
                .keyboardShortcut(.defaultAction)
            }

            Grid(alignment: .leading, horizontalSpacing: 28, verticalSpacing: 14) {
                GridRow {
                    ScanMetric(title: "Status", value: scan.status.rawValue.capitalized)
                    ScanMetric(title: "Devices", value: "\(scan.discoveredCount)")
                }

                GridRow {
                    ScanMetric(title: "Duration", value: formattedDuration(scan.duration))
                    ScanMetric(title: "Started", value: scan.startedAt.formatted(date: .abbreviated, time: .shortened))
                }

                GridRow {
                    ScanMetric(title: "Finished", value: scan.finishedAt?.formatted(date: .abbreviated, time: .shortened) ?? "-")
                    ScanMetric(title: "Error", value: scan.errorMessage ?? "-")
                }
            }

            Divider()

            VStack(alignment: .leading, spacing: 12) {
                Text("Deep scan checks")
                    .font(.headline)

                ForEach(checks, id: \.self) { check in
                    Label(check, systemImage: "checkmark.shield")
                        .foregroundStyle(.secondary)
                }
            }

            Text("Longer scans are usually caused by devices that do not answer and force timeout-based checks.")
                .font(.subheadline)
                .foregroundStyle(.secondary)

            Spacer(minLength: 0)
        }
        .padding(28)
        .frame(minWidth: 520, minHeight: 440)
    }

    private func formattedDuration(_ duration: TimeInterval?) -> String {
        guard let duration else { return "-" }
        return Duration.seconds(duration).formatted(.time(pattern: .minuteSecond))
    }
}

private struct CompactEmptyScanCard: View {
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 8) {
                Image(systemName: "clock")
                    .font(.system(size: 17, weight: .semibold))
                    .frame(width: 24)

                Text("Latest Scan")
                    .font(.headline.weight(.semibold))
                    .lineLimit(1)
                    .minimumScaleFactor(0.7)
            }

            Spacer(minLength: 4)

            Text("No scans yet")
                .font(.headline)
                .lineLimit(1)

            Text("Run a scan to populate devices.")
                .font(.caption)
                .foregroundStyle(.secondary)
                .lineLimit(2)
        }
        .padding(16)
        .frame(maxWidth: .infinity, minHeight: 150, maxHeight: 150, alignment: .leading)
        .background(.background.secondary, in: RoundedRectangle(cornerRadius: 18))
        .overlay {
            RoundedRectangle(cornerRadius: 18)
                .stroke(.quaternary)
        }
    }
}

private struct CompactScanStatusBadge: View {
    let isScanning: Bool
    let latestScan: ScanRecord?

    var body: some View {
        HStack(spacing: 7) {
            Image(systemName: systemImage)
                .font(.caption.weight(.bold))
            Text(title)
                .font(.caption.weight(.bold))
                .lineLimit(1)
                .minimumScaleFactor(0.9)
        }
            .font(.caption.weight(.bold))
            .padding(.horizontal, 10)
            .padding(.vertical, 5)
            .frame(minWidth: 98)
            .background(color.opacity(0.16), in: Capsule())
            .foregroundStyle(color)
            .fixedSize(horizontal: true, vertical: false)
    }

    private var title: String {
        if isScanning { return "Scanning" }
        guard let latestScan else { return "Ready" }
        return latestScan.status.rawValue.capitalized
    }

    private var systemImage: String {
        if isScanning { return "arrow.clockwise" }
        switch latestScan?.status {
        case .completed:
            return "checkmark.circle"
        case .failed:
            return "exclamationmark.triangle"
        case .running:
            return "arrow.clockwise"
        case nil:
            return "circle.dotted"
        }
    }

    private var color: Color {
        if isScanning { return .blue }
        switch latestScan?.status {
        case .completed:
            return .green
        case .failed:
            return .red
        case .running:
            return .blue
        case nil:
            return .secondary
        }
    }
}

private extension DeviceRisk {
    var sortRank: Int {
        switch self {
        case .low:
            0
        case .medium:
            1
        case .high:
            2
        }
    }
}

private struct ScanMetric: View {
    let title: String
    let value: String

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(title)
                .font(.caption)
                .foregroundStyle(.secondary)

            Text(value)
                .font(.headline)
                .lineLimit(1)
        }
    }
}

#Preview {
    DashboardView()
        .environment(AppModel())
        .frame(width: 980, height: 640)
}
