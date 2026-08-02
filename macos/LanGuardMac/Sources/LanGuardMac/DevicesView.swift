import SwiftUI

enum DeviceRoomFilter {
    static let unassigned = "__languard_unassigned__"
}

struct DevicesView: View {
    @Environment(AppModel.self) private var appModel
    @Binding private var roleFilter: DeviceRole?
    @Binding private var roomFilter: String?
    @State private var editingDevice: NetworkDevice?
    @State private var searchText = ""
    @State private var statusFilter: DeviceStatus?
    @State private var knownFilter: KnownFilter = .all
    @State private var riskFilter: DeviceRisk?
    @State private var sortField: DeviceSortField = .name
    @State private var sortOrder: SortOrder = .forward

    init(
        roleFilter: Binding<DeviceRole?> = .constant(nil),
        roomFilter: Binding<String?> = .constant(nil)
    ) {
        _roleFilter = roleFilter
        _roomFilter = roomFilter
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 20) {
            HeaderView(
                title: "Devices",
                subtitle: "Discovered network devices will appear here."
            )

            if appModel.devices.isEmpty {
                emptyDevicesView
            } else {
                filterToolbar

                ViewThatFits(in: .horizontal) {
                    devicesTable
                        .frame(minWidth: 1280, maxWidth: .infinity)
                    compactDeviceList
                }
            }
        }
        .padding(28)
        .sheet(item: $editingDevice) { device in
            DeviceDetailView(device: device, rooms: appModel.settings.rooms) { updatedDevice in
                appModel.updateDevice(updatedDevice)
                editingDevice = nil
            } onDelete: { device in
                appModel.deleteDevice(device)
                editingDevice = nil
            }
        }
    }

    private var devicesTable: some View {
        Table(filteredAndSortedDevices) {
            TableColumn("Status") { device in
                HStack(spacing: 8) {
                    Circle()
                        .fill(device.status == .online ? .green : .gray)
                        .frame(width: 8, height: 8)
                    Text(device.status.title)
                        .lineLimit(1)
                        .fixedSize(horizontal: true, vertical: false)
                }
            }
            .width(min: 108, ideal: 118, max: 132)

            TableColumn("Name") { device in
                HStack(spacing: 8) {
                    DeviceIconStack(device: device, size: 17)
                    Text(device.name)
                        .lineLimit(2)
                        .fixedSize(horizontal: false, vertical: true)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
            }
            .width(min: 260, ideal: 360, max: 520)

            TableColumn("IP") { device in
                Text(device.ipAddress)
            }
            .width(min: 110, ideal: 130, max: 150)

            TableColumn("MAC", value: \.macAddress)
                .width(min: 150, ideal: 170, max: 190)

            TableColumn("Ports") { device in
                Text(portSummary(for: device.openPorts))
                    .foregroundStyle(device.openPorts.isEmpty ? .secondary : .primary)
            }
            .width(min: 80, ideal: 110, max: 160)

            TableColumn("Risk") { device in
                Text(device.risk.title)
                    .font(.caption.weight(.semibold))
                    .padding(.horizontal, 8)
                    .padding(.vertical, 4)
                    .background(riskColor(for: device.risk).opacity(0.18), in: Capsule())
                    .foregroundStyle(riskColor(for: device.risk))
            }
            .width(min: 70, ideal: 82, max: 96)

            TableColumn("Role") { device in
                Text(device.effectiveRole.title)
            }
            .width(min: 72, ideal: 86, max: 105)

            TableColumn("Known") { device in
                Text(device.isKnown ? "Known" : "New")
                    .lineLimit(1)
                    .fixedSize(horizontal: true, vertical: false)
            }
            .width(min: 88, ideal: 98, max: 112)

            TableColumn("") { device in
                Button("Edit") {
                    editingDevice = device
                }
            }
            .width(min: 56, ideal: 66, max: 76)
        }
    }

    private var filterToolbar: some View {
        ViewThatFits(in: .horizontal) {
            HStack(spacing: 8) {
                filterControls
            }

            VStack(alignment: .leading, spacing: 10) {
                HStack(spacing: 8) {
                    searchField
                        .frame(width: 320)

                    compactSortPicker
                    compactRoomPicker
                    sortDirectionButton
                    clearFiltersButton
                }

                HStack(spacing: 6) {
                    compactStatusPicker
                    compactKnownPicker
                    compactRiskPicker
                    compactRolePicker
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    @ViewBuilder
    private var filterControls: some View {
        searchField
            .frame(minWidth: 220, idealWidth: 280, maxWidth: 300)

        filterPickers
    }

    private var searchField: some View {
        ZStack(alignment: .trailing) {
            TextField("Search devices", text: $searchText)
                .textFieldStyle(.roundedBorder)
                .padding(.trailing, searchText.isEmpty ? 0 : 26)

            if !searchText.isEmpty {
                Button {
                    searchText = ""
                } label: {
                    Image(systemName: "xmark.circle.fill")
                        .font(.system(size: 13, weight: .semibold))
                        .foregroundStyle(.secondary)
                        .frame(width: 22, height: 22)
                }
                .buttonStyle(.plain)
                .help("Clear search")
                .padding(.trailing, 5)
            }
        }
    }

    @ViewBuilder
    private var filterPickers: some View {
        statusPicker
        knownPicker
        riskPicker
        rolePicker
        roomPicker
        sortPicker
        sortDirectionButton
        clearFiltersButton
    }

    private var statusPicker: some View {
        Picker("Status", selection: $statusFilter) {
            Text("All Statuses").tag(DeviceStatus?.none)
            ForEach(DeviceStatus.allCases) { status in
                Text(status.title).tag(DeviceStatus?.some(status))
            }
        }
        .frame(width: 178)
    }

    private var compactStatusPicker: some View {
        Picker("Status", selection: $statusFilter) {
            Text("All Statuses").tag(DeviceStatus?.none)
            ForEach(DeviceStatus.allCases) { status in
                Text(status.title).tag(DeviceStatus?.some(status))
            }
        }
        .frame(width: 188)
    }

    private var knownPicker: some View {
        Picker("Known", selection: $knownFilter) {
            ForEach(KnownFilter.allCases) { filter in
                Text(filter.title).tag(filter)
            }
        }
        .frame(width: 168)
    }

    private var compactKnownPicker: some View {
        Picker("Known", selection: $knownFilter) {
            ForEach(KnownFilter.allCases) { filter in
                Text(filter.title).tag(filter)
            }
        }
        .frame(width: 178)
    }

    private var riskPicker: some View {
        Picker("Risk", selection: $riskFilter) {
            Text("All Risks").tag(DeviceRisk?.none)
            ForEach(DeviceRisk.allCases) { risk in
                Text(risk.title).tag(DeviceRisk?.some(risk))
            }
        }
        .frame(width: 124)
    }

    private var compactRiskPicker: some View {
        Picker("Risk", selection: $riskFilter) {
            Text("All Risks").tag(DeviceRisk?.none)
            ForEach(DeviceRisk.allCases) { risk in
                Text(risk.title).tag(DeviceRisk?.some(risk))
            }
        }
        .frame(width: 132)
    }

    private var rolePicker: some View {
        Picker("Role", selection: $roleFilter) {
            Text("All Roles").tag(DeviceRole?.none)
            ForEach(DeviceRole.alphabeticalCases) { role in
                Text(role.title).tag(DeviceRole?.some(role))
            }
        }
        .frame(width: 140)
    }

    private var compactRolePicker: some View {
        Picker("Role", selection: $roleFilter) {
            Text("All Roles").tag(DeviceRole?.none)
            ForEach(DeviceRole.alphabeticalCases) { role in
                Text(role.title).tag(DeviceRole?.some(role))
            }
        }
        .frame(width: 150)
    }

    private var roomPicker: some View {
        Picker("Room", selection: $roomFilter) {
            Text("All Rooms").tag(String?.none)
            Text("Unassigned").tag(String?.some(DeviceRoomFilter.unassigned))
            ForEach(appModel.settings.rooms, id: \.self) { room in
                Text(room).tag(String?.some(room))
            }
        }
        .frame(width: 150)
    }

    private var compactRoomPicker: some View {
        Picker("Room", selection: $roomFilter) {
            Text("All Rooms").tag(String?.none)
            Text("Unassigned").tag(String?.some(DeviceRoomFilter.unassigned))
            ForEach(appModel.settings.rooms, id: \.self) { room in
                Text(room).tag(String?.some(room))
            }
        }
        .frame(width: 160)
    }

    private var sortPicker: some View {
        Picker("Sort", selection: $sortField) {
            ForEach(DeviceSortField.allCases) { field in
                Text(field.title).tag(field)
            }
        }
        .frame(width: 124)
    }

    private var compactSortPicker: some View {
        Picker("Sort", selection: $sortField) {
            ForEach(DeviceSortField.allCases) { field in
                Text(field.title).tag(field)
            }
        }
        .frame(width: 132)
    }

    private var sortDirectionButton: some View {
        Button {
            sortOrder = sortOrder == .forward ? .reverse : .forward
        } label: {
            Label(sortOrder == .forward ? "Ascending" : "Descending", systemImage: sortOrder == .forward ? "arrow.up" : "arrow.down")
                .labelStyle(.iconOnly)
        }
        .buttonStyle(.bordered)
    }

    @ViewBuilder
    private var clearFiltersButton: some View {
        if hasActiveFilters {
            Button("Clear") {
                searchText = ""
                statusFilter = nil
                knownFilter = .all
                riskFilter = nil
                roleFilter = nil
                roomFilter = nil
                sortField = .name
                sortOrder = .forward
            }
        }
    }

    private var compactDeviceList: some View {
        List(filteredAndSortedDevices) { device in
            Button {
                editingDevice = device
            } label: {
                CompactDeviceRow(device: device, portSummary: portSummary(for: device.openPorts), riskColor: riskColor(for: device.risk))
            }
            .buttonStyle(.plain)
            .listRowInsets(EdgeInsets(top: 8, leading: 10, bottom: 8, trailing: 10))
        }
        .listStyle(.plain)
    }

    private var filteredAndSortedDevices: [NetworkDevice] {
        let normalizedSearch = searchText.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        let filtered = appModel.devices.filter { device in
            if let statusFilter, device.status != statusFilter {
                return false
            }

            if let riskFilter, device.risk != riskFilter {
                return false
            }

            if let roleFilter, device.effectiveRole != roleFilter {
                return false
            }

            if let roomFilter {
                let currentRoom = device.room?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
                if roomFilter == DeviceRoomFilter.unassigned {
                    if !currentRoom.isEmpty { return false }
                } else if currentRoom != roomFilter {
                    return false
                }
            }

            switch knownFilter {
            case .all:
                break
            case .known:
                if !device.isKnown { return false }
            case .new:
                if device.isKnown { return false }
            }

            guard !normalizedSearch.isEmpty else { return true }
            return [
                device.name,
                device.ipAddress,
                device.macAddress,
                device.room ?? "",
                device.vendor ?? "",
                device.hostname ?? "",
            ].contains { $0.localizedCaseInsensitiveContains(normalizedSearch) }
        }

        return filtered.sorted { left, right in
            let result = compare(left, right)
            return sortOrder == .forward ? result : !result
        }
    }

    private var hasActiveFilters: Bool {
        !searchText.isEmpty || statusFilter != nil || knownFilter != .all || riskFilter != nil || roleFilter != nil || roomFilter != nil || sortField != .name || sortOrder != .forward
    }

    private func compare(_ left: NetworkDevice, _ right: NetworkDevice) -> Bool {
        switch sortField {
        case .name:
            return left.name.localizedStandardCompare(right.name) == .orderedAscending
        case .ip:
            return compareIPSafely(left.ipAddress, right.ipAddress)
        case .risk:
            return left.risk.sortRank < right.risk.sortRank
        case .lastSeen:
            return left.lastSeen < right.lastSeen
        }
    }

    private func ipSortKey(_ ipAddress: String) -> [Int] {
        ipAddress.split(separator: ".").map { Int($0) ?? 0 }
    }

    private func compareIPSafely(_ left: String, _ right: String) -> Bool {
        let leftParts = ipSortKey(left)
        let rightParts = ipSortKey(right)

        for index in 0..<max(leftParts.count, rightParts.count) {
            let leftValue = index < leftParts.count ? leftParts[index] : 0
            let rightValue = index < rightParts.count ? rightParts[index] : 0
            if leftValue != rightValue {
                return leftValue < rightValue
            }
        }

        return false
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

private enum KnownFilter: String, CaseIterable, Identifiable {
    case all
    case known
    case new

    var id: String { rawValue }

    var title: String {
        switch self {
        case .all:
            "All Devices"
        case .known:
            "Known"
        case .new:
            "New"
        }
    }
}

private enum DeviceSortField: String, CaseIterable, Identifiable {
    case name
    case ip
    case risk
    case lastSeen

    var id: String { rawValue }

    var title: String {
        switch self {
        case .name:
            "Name"
        case .ip:
            "IP"
        case .risk:
            "Risk"
        case .lastSeen:
            "Last Seen"
        }
    }
}

private struct CompactDeviceRow: View {
    let device: NetworkDevice
    let portSummary: String
    let riskColor: Color

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(alignment: .firstTextBaseline, spacing: 10) {
                Circle()
                    .fill(device.status == .online ? .green : .gray)
                    .frame(width: 8, height: 8)

                DeviceIconStack(device: device, size: 17)

                Text(device.name)
                    .font(.headline)
                    .lineLimit(2)
                    .frame(maxWidth: .infinity, alignment: .leading)

                Text(device.risk.title)
                    .font(.caption.weight(.semibold))
                    .padding(.horizontal, 8)
                    .padding(.vertical, 4)
                    .background(riskColor.opacity(0.18), in: Capsule())
                    .foregroundStyle(riskColor)
            }

            HStack(spacing: 12) {
                Text(device.status.title)
                    .lineLimit(1)
                    .fixedSize(horizontal: true, vertical: false)
                Text(device.ipAddress)
                    .monospacedDigit()
                    .lineLimit(1)
                    .fixedSize(horizontal: true, vertical: false)
                Text(device.macAddress)
                    .lineLimit(1)
                    .truncationMode(.middle)
                Text(portSummary)
                    .lineLimit(1)
                Text(device.isKnown ? "Known" : "New")
                    .lineLimit(1)
                    .fixedSize(horizontal: true, vertical: false)
            }
            .font(.caption)
            .foregroundStyle(.secondary)
        }
        .padding(.vertical, 4)
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

private struct DeviceDetailView: View {
    let originalDevice: NetworkDevice
    let rooms: [String]
    let onSave: (NetworkDevice) -> Void
    let onDelete: (NetworkDevice) -> Void

    @Environment(\.dismiss) private var dismiss
    @State private var name: String
    @State private var isKnown: Bool
    @State private var role: DeviceRole?
    @State private var room: String?
    @State private var iconName: String
    @State private var secondaryIconName: String
    @State private var isShowingDeleteConfirmation = false

    init(
        device: NetworkDevice,
        rooms: [String] = [],
        onSave: @escaping (NetworkDevice) -> Void,
        onDelete: @escaping (NetworkDevice) -> Void
    ) {
        self.originalDevice = device
        self.rooms = rooms
        self.onSave = onSave
        self.onDelete = onDelete
        _name = State(initialValue: device.name)
        _isKnown = State(initialValue: device.isKnown)
        _role = State(initialValue: device.role)
        _room = State(initialValue: device.room)
        _iconName = State(initialValue: device.displayIconName)
        _secondaryIconName = State(initialValue: device.secondaryIconName ?? "")
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
                    Picker("Role", selection: $role) {
                        Text("Automatic (\(originalDevice.detectedRole.title))")
                            .tag(DeviceRole?.none)
                        ForEach(DeviceRole.alphabeticalCases) { role in
                            Text(role.title)
                                .tag(DeviceRole?.some(role))
                        }
                    }
                    .pickerStyle(.menu)
                    Picker("Room", selection: $room) {
                        Text("Unassigned").tag(String?.none)
                        ForEach(rooms, id: \.self) { room in
                            Text(room).tag(String?.some(room))
                        }
                    }
                    .pickerStyle(.menu)
                    IconPicker("Primary icon", selection: $iconName)
                    IconPicker("Second icon", selection: $secondaryIconName, includesNone: true)
                }

                Section("Network") {
                    DetailRow(title: "Status", value: originalDevice.status.title)
                    DetailRow(title: "IP address", value: originalDevice.ipAddress)
                    DetailRow(title: "MAC address", value: originalDevice.macAddress)
                    DetailRow(title: "Hostname", value: originalDevice.hostname ?? "-")
                    DetailRow(title: "Vendor", value: originalDevice.vendor ?? "-")
                    DetailRow(title: "Role", value: originalDevice.effectiveRole.title)
                    DetailRow(title: "Detected role", value: originalDevice.detectedRole.title)
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
                Button(role: .destructive) {
                    isShowingDeleteConfirmation = true
                } label: {
                    Label("Delete", systemImage: "trash")
                }

                Spacer()

                Button("Cancel") {
                    dismiss()
                }

                Button("Save") {
                    var updatedDevice = originalDevice
                    updatedDevice.name = trimmedName
                    updatedDevice.isKnown = isKnown
                    updatedDevice.role = role
                    updatedDevice.room = room
                    updatedDevice.iconName = iconName
                    updatedDevice.secondaryIconName = sanitizedSecondaryIconName
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
        .alert("Delete \(originalDevice.name)?", isPresented: $isShowingDeleteConfirmation) {
            Button("Cancel", role: .cancel) {}
            Button("Delete Device", role: .destructive) {
                onDelete(originalDevice)
            }
        } message: {
            Text("This removes \(originalDevice.ipAddress) from your saved inventory. LanGuard can add it again if a future scan discovers it.")
        }
    }

    private var trimmedName: String {
        name.trimmingCharacters(in: .whitespacesAndNewlines)
    }

    private var sanitizedSecondaryIconName: String? {
        let trimmed = secondaryIconName.trimmingCharacters(in: .whitespacesAndNewlines)
        return trimmed.isEmpty || trimmed == iconName ? nil : trimmed
    }

    private func portSummary(for ports: [Int]) -> String {
        guard !ports.isEmpty else { return "-" }
        return ports.map(String.init).joined(separator: ", ")
    }
}

private struct IconPicker: View {
    let title: String
    @Binding var selection: String
    let includesNone: Bool

    init(_ title: String, selection: Binding<String>, includesNone: Bool = false) {
        self.title = title
        self._selection = selection
        self.includesNone = includesNone
    }

    var body: some View {
        Picker(title, selection: $selection) {
            if includesNone {
                Text("None")
                    .tag("")
            }
            ForEach(DeviceIconCatalog.options) { option in
                Label(option.title, systemImage: option.systemImage)
                    .tag(option.systemImage)
            }
        }
        .pickerStyle(.menu)
    }
}

private struct DeviceIconStack: View {
    let device: NetworkDevice
    let size: CGFloat

    var body: some View {
        HStack(spacing: 3) {
            ForEach(device.displayIconNames, id: \.self) { iconName in
                Image(systemName: iconName)
                    .foregroundStyle(.blue)
                    .frame(width: size, height: size)
            }
        }
        .frame(width: iconStackWidth, alignment: .leading)
    }

    private var iconStackWidth: CGFloat {
        device.displayIconNames.count > 1 ? (size * 2) + 3 : size
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
