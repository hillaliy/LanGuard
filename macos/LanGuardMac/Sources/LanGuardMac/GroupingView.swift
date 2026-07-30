import SwiftUI

struct GroupingView: View {
    @Environment(AppModel.self) private var appModel
    let onSelectGroup: (DeviceRole) -> Void

    init(onSelectGroup: @escaping (DeviceRole) -> Void = { _ in }) {
        self.onSelectGroup = onSelectGroup
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 24) {
                HeaderView(
                    title: "Grouping",
                    subtitle: "Devices grouped by role and network function."
                )

                if appModel.devices.isEmpty {
                    emptyState
                } else {
                    LazyVStack(spacing: 18) {
                        ForEach(deviceGroups) { group in
                            DeviceGroupCard(group: group) {
                                onSelectGroup(group.role)
                            }
                        }
                    }
                }
            }
            .frame(maxWidth: 1320, alignment: .leading)
            .padding(28)
        }
        .background(Color(nsColor: .windowBackgroundColor))
    }

    private var emptyState: some View {
        ZStack {
            RoundedRectangle(cornerRadius: 18)
                .fill(.background.secondary)
                .overlay {
                    RoundedRectangle(cornerRadius: 18)
                        .stroke(.quaternary)
                }

            ContentUnavailableView(
                "No Groups Yet",
                systemImage: "network",
                description: Text("Run a scan to group devices by role.")
            )
            .padding(40)
        }
        .frame(minHeight: 360)
    }

    private var deviceGroups: [DeviceGroup] {
        let groupedDevices = Dictionary(grouping: appModel.devices, by: \.effectiveRole)

        return groupedDevices.map { role, devices in
            DeviceGroup(
                role: role,
                devices: devices.sorted(by: sortDevices)
            )
        }
        .sorted(by: sortGroups)
    }

    private func sortGroups(_ left: DeviceGroup, _ right: DeviceGroup) -> Bool {
        let leftRank = groupRank(for: left.role)
        let rightRank = groupRank(for: right.role)

        if leftRank != rightRank {
            return leftRank < rightRank
        }

        return left.role.title.localizedStandardCompare(right.role.title) == .orderedAscending
    }

    private func groupRank(for role: DeviceRole) -> Int {
        switch role {
        case .gateway:
            0
        case .router:
            1
        case .meshRouter:
            2
        case .hub:
            3
        case .camera:
            4
        case .server:
            5
        case .unknown:
            99
        default:
            20
        }
    }

    private func sortDevices(_ left: NetworkDevice, _ right: NetworkDevice) -> Bool {
        let leftStatusRank = statusRank(for: left.status)
        let rightStatusRank = statusRank(for: right.status)

        if leftStatusRank != rightStatusRank {
            return leftStatusRank < rightStatusRank
        }

        if left.name != right.name {
            return left.name.localizedStandardCompare(right.name) == .orderedAscending
        }

        return GroupingIPv4AddressSortKey(left.ipAddress) < GroupingIPv4AddressSortKey(right.ipAddress)
    }

    private func statusRank(for status: DeviceStatus) -> Int {
        switch status {
        case .online:
            0
        case .recentlySeen:
            1
        case .unknown:
            2
        case .offline:
            3
        }
    }
}

private struct GroupingIPv4AddressSortKey: Comparable {
    private let parts: [Int]
    private let rawValue: String

    init(_ address: String) {
        rawValue = address
        parts = address.split(separator: ".").map { Int($0) ?? 0 }
    }

    static func < (left: GroupingIPv4AddressSortKey, right: GroupingIPv4AddressSortKey) -> Bool {
        if left.parts.count == 4, right.parts.count == 4, left.parts != right.parts {
            return left.parts.lexicographicallyPrecedes(right.parts)
        }

        return left.rawValue.localizedStandardCompare(right.rawValue) == .orderedAscending
    }
}

private struct DeviceGroup: Identifiable {
    let role: DeviceRole
    let devices: [NetworkDevice]

    var id: String { role.rawValue }
    var onlineCount: Int { devices.filter { $0.status == .online }.count }
    var knownCount: Int { devices.filter(\.isKnown).count }
    var openPortCount: Int { devices.reduce(0) { $0 + $1.openPorts.count } }
}

private struct DeviceGroupCard: View {
    let group: DeviceGroup
    let onOpen: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack(spacing: 12) {
                RoleIcon(role: group.role)

                VStack(alignment: .leading, spacing: 3) {
                    Text(group.role.title)
                        .font(.title3.weight(.bold))
                        .lineLimit(1)

                    Text(groupSummary)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }

                Spacer(minLength: 8)

                Text("\(group.devices.count)")
                    .font(.caption.weight(.bold))
                    .foregroundStyle(.blue)
                    .padding(.horizontal, 10)
                    .padding(.vertical, 6)
                    .background(.blue.opacity(0.12), in: Capsule())

                Button {
                    onOpen()
                } label: {
                    Label("View Devices", systemImage: "arrow.right")
                        .labelStyle(.titleAndIcon)
                }
                .buttonStyle(.bordered)
                .controlSize(.small)
                .help("Show \(group.role.title.lowercased()) devices")
            }

            HStack(spacing: 10) {
                GroupMetricBlock(title: "Online", value: group.onlineCount, color: .green)
                GroupMetricBlock(title: "Known", value: group.knownCount, color: .blue)
                GroupMetricBlock(title: "Open ports", value: group.openPortCount, color: .orange)
            }

            Divider()

            ScrollView {
                LazyVGrid(
                    columns: [GridItem(.adaptive(minimum: 260), spacing: 10, alignment: .top)],
                    alignment: .leading,
                    spacing: 10
                ) {
                    ForEach(group.devices) { device in
                        GroupingDeviceTile(device: device)
                    }
                }
                .padding(.trailing, 2)
            }
            .scrollIndicators(.visible)
        }
        .padding(18)
        .frame(maxWidth: .infinity, minHeight: 330, maxHeight: 330, alignment: .topLeading)
        .background(.background.secondary, in: RoundedRectangle(cornerRadius: 18))
        .overlay {
            RoundedRectangle(cornerRadius: 18)
                .stroke(.quaternary)
        }
    }

    private var groupSummary: String {
        let onlineText = group.onlineCount == 1 ? "1 online" : "\(group.onlineCount) online"
        let knownText = group.knownCount == 1 ? "1 known" : "\(group.knownCount) known"
        return "\(onlineText) · \(knownText)"
    }
}

private struct RoleIcon: View {
    let role: DeviceRole

    var body: some View {
        Image(systemName: role.iconName)
            .font(.system(size: 22, weight: .semibold))
            .foregroundStyle(.blue)
            .frame(width: 44, height: 44)
            .background(.blue.opacity(0.12), in: RoundedRectangle(cornerRadius: 12))
    }
}

private struct GroupMetricBlock: View {
    let title: String
    let value: Int
    let color: Color

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(spacing: 6) {
                Circle()
                    .fill(color)
                    .frame(width: 7, height: 7)

                Text(title)
                    .font(.caption.weight(.semibold))
                    .lineLimit(1)
            }
            .foregroundStyle(.secondary)

            Text("\(value)")
                .font(.title3.weight(.bold))
                .foregroundStyle(.secondary)
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 10)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(color.opacity(0.10), in: RoundedRectangle(cornerRadius: 12))
    }
}

private struct GroupingDeviceTile: View {
    let device: NetworkDevice

    var body: some View {
        HStack(spacing: 10) {
            ZStack(alignment: .bottomTrailing) {
                Image(systemName: device.displayIconName)
                    .font(.system(size: 19, weight: .semibold))
                    .foregroundStyle(.blue)
                    .frame(width: 38, height: 38)
                    .background(.blue.opacity(0.10), in: RoundedRectangle(cornerRadius: 10))

                Circle()
                    .fill(statusColor)
                    .frame(width: 10, height: 10)
                    .overlay {
                        Circle()
                            .stroke(Color(nsColor: .windowBackgroundColor), lineWidth: 1.5)
                    }
            }

            VStack(alignment: .leading, spacing: 4) {
                Text(device.name)
                    .font(.headline)
                    .lineLimit(1)
                    .truncationMode(.tail)

                HStack(spacing: 6) {
                    Text(device.ipAddress)

                    if !device.openPorts.isEmpty {
                        Text("·")
                        Text(portSummary)
                    }
                }
                .font(.caption)
                .foregroundStyle(.secondary)
                .lineLimit(1)
            }

            Spacer(minLength: 8)

            Text(device.risk.title)
                .font(.caption.weight(.bold))
                .foregroundStyle(riskColor)
                .padding(.horizontal, 8)
                .padding(.vertical, 5)
                .background(riskColor.opacity(0.14), in: Capsule())
                .lineLimit(1)
        }
        .padding(10)
        .background(Color(nsColor: .controlBackgroundColor).opacity(0.65), in: RoundedRectangle(cornerRadius: 12))
        .overlay {
            RoundedRectangle(cornerRadius: 12)
                .stroke(.quaternary)
        }
    }

    private var statusColor: Color {
        switch device.status {
        case .online:
            .green
        case .recentlySeen:
            .blue
        case .offline:
            .gray
        case .unknown:
            .secondary
        }
    }

    private var riskColor: Color {
        switch device.risk {
        case .low:
            .green
        case .medium:
            .orange
        case .high:
            .red
        }
    }

    private var portSummary: String {
        let sortedPorts = device.openPorts.sorted()

        guard sortedPorts.count > 2 else {
            return sortedPorts.map(String.init).joined(separator: ", ")
        }

        return sortedPorts.prefix(2).map(String.init).joined(separator: ", ") + " +\(sortedPorts.count - 2)"
    }
}

#Preview {
    GroupingView()
        .environment(AppModel())
}
