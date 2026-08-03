import SwiftUI
import AppKit

struct ContentView: View {
    @Environment(AppModel.self) private var appModel
    @State private var selectedSection: AppSection = .dashboard
    @State private var isSidebarCompact = false
    @State private var selectedDeviceRoleFilter: DeviceRole?
    @State private var selectedDeviceRoomFilter: String?
    @State private var dismissedUpdateVersion: String?

    var body: some View {
        ZStack {
            HStack(spacing: 0) {
                AppSidebar(
                    selectedSection: $selectedSection,
                    isCompact: $isSidebarCompact
                )
                .fixedSize(horizontal: true, vertical: false)
                .layoutPriority(1)

                Divider()

                selectedContent
                    .frame(minWidth: 0, maxWidth: .infinity, maxHeight: .infinity)
                    .clipped()
                    .layoutPriority(0)
            }

            if let update = appModel.settings.versionUpdate,
               update.isUpdateAvailable,
               dismissedUpdateVersion != update.latestVersion {
                Color.black.opacity(0.28).ignoresSafeArea()
                VStack(spacing: 14) {
                    Image(systemName: "shield.lefthalf.filled.badge.checkmark")
                        .font(.system(size: 42))
                        .foregroundStyle(.blue)
                    Text("LanGuard")
                        .font(.title2.weight(.semibold))
                    Text("A new version is available")
                        .font(.headline)
                    Text("Version \(update.latestVersion) is ready. Click below to download the new version.")
                        .multilineTextAlignment(.center)
                        .foregroundStyle(.secondary)
                    HStack {
                        Button("Later") { dismissedUpdateVersion = update.latestVersion }
                        Button("Download update") {
                            NSWorkspace.shared.open(update.releaseURL)
                        }
                        .buttonStyle(.borderedProminent)
                    }
                }
                .padding(28)
                .frame(width: 380)
                .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 18))
                .shadow(radius: 24)
            }
        }
        .frame(minWidth: 780, minHeight: 640)
    }

    @ViewBuilder
    private var selectedContent: some View {
        switch selectedSection {
        case .dashboard:
            DashboardView()
        case .devices:
            DevicesView(
                roleFilter: $selectedDeviceRoleFilter,
                roomFilter: $selectedDeviceRoomFilter
            )
        case .grouping:
            GroupingView { selection in
                switch selection {
                case .role(let role):
                    selectedDeviceRoleFilter = role
                    selectedDeviceRoomFilter = nil
                case .room(let room):
                    selectedDeviceRoleFilter = nil
                    selectedDeviceRoomFilter = room
                }
                selectedSection = .devices
            }
        case .guestScan:
            GuestScanView()
        case .scanHistory:
            ScanHistoryView()
        case .settings:
            SettingsView()
        case .about:
            AboutView()
        }
    }
}

private enum AppSection: String, CaseIterable, Identifiable {
    case dashboard
    case devices
    case grouping
    case guestScan
    case scanHistory
    case settings
    case about

    var id: String { rawValue }

    var title: String {
        switch self {
        case .dashboard: "Dashboard"
        case .devices: "Devices"
        case .grouping: "Grouping"
        case .guestScan: "Guest Scan"
        case .scanHistory: "Scan History"
        case .settings: "Settings"
        case .about: "About"
        }
    }

    var systemImage: String {
        switch self {
        case .dashboard: "gauge.with.dots.needle.67percent"
        case .devices: "network"
        case .grouping: "point.3.connected.trianglepath.dotted"
        case .guestScan: "person.crop.circle"
        case .scanHistory: "clock.arrow.circlepath"
        case .settings: "gearshape"
        case .about: "info.circle"
        }
    }
}

private struct AppSidebar: View {
    @Binding var selectedSection: AppSection
    @Binding var isCompact: Bool

    var body: some View {
        VStack(alignment: isCompact ? .center : .leading, spacing: 18) {
            HStack {
                if !isCompact {
                    Spacer(minLength: 0)
                }

                Button {
                    withAnimation(.snappy(duration: 0.18)) {
                        isCompact.toggle()
                    }
                } label: {
                    Image(systemName: isCompact ? "sidebar.leading" : "sidebar.left")
                        .font(.system(size: 18, weight: .medium))
                        .frame(width: 34, height: 34)
                }
                .buttonStyle(.plain)
                .foregroundStyle(.secondary)
                .help(isCompact ? "Expand sidebar" : "Collapse sidebar")
            }
            .padding(.top, 18)
            .padding(.horizontal, isCompact ? 0 : 14)

            VStack(spacing: 8) {
                ForEach(AppSection.allCases) { section in
                    SidebarItem(
                        section: section,
                        isSelected: selectedSection == section,
                        isCompact: isCompact
                    ) {
                        selectedSection = section
                    }
                }
            }
            .padding(.horizontal, isCompact ? 10 : 14)

            Spacer()
        }
        .frame(
            minWidth: isCompact ? 72 : 240,
            idealWidth: isCompact ? 72 : 240,
            maxWidth: isCompact ? 72 : 240
        )
        .frame(maxHeight: .infinity)
        .background(.regularMaterial)
        .animation(.snappy(duration: 0.18), value: isCompact)
    }
}

private struct SidebarItem: View {
    let section: AppSection
    let isSelected: Bool
    let isCompact: Bool
    let action: () -> Void
    @State private var isHovering = false

    var body: some View {
        ZStack(alignment: .leading) {
            Button(action: action) {
                HStack(spacing: 12) {
                    Image(systemName: section.systemImage)
                        .font(.system(size: 16, weight: .medium))
                        .frame(width: 22)

                    if !isCompact {
                        Text(section.title)
                            .font(.headline)
                            .lineLimit(1)

                        Spacer(minLength: 0)
                    }
                }
                .foregroundStyle(isSelected ? .white : .primary)
                .padding(.horizontal, isCompact ? 0 : 12)
                .frame(width: isCompact ? 44 : nil, height: 38, alignment: isCompact ? .center : .leading)
                .background(isSelected ? Color.accentColor : Color.clear, in: RoundedRectangle(cornerRadius: 8))
                .contentShape(RoundedRectangle(cornerRadius: 8))
            }
            .buttonStyle(.plain)
            .help(section.title)

            if isCompact && isHovering {
                Text(section.title)
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(.primary)
                    .padding(.horizontal, 10)
                    .padding(.vertical, 6)
                    .background(.regularMaterial, in: Capsule())
                    .overlay {
                        Capsule()
                            .stroke(.quaternary)
                    }
                    .fixedSize()
                    .offset(y: -36)
                    .shadow(color: .black.opacity(0.12), radius: 8, y: 4)
                    .allowsHitTesting(false)
                    .transition(.opacity.combined(with: .move(edge: .bottom)))
                    .zIndex(1)
            }
        }
        .onHover { hovering in
            withAnimation(.easeOut(duration: 0.12)) {
                isHovering = hovering
            }
        }
    }
}

#Preview {
    ContentView()
}
