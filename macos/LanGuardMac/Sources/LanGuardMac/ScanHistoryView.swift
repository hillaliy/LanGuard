import SwiftUI

struct ScanHistoryView: View {
    @Environment(AppModel.self) private var appModel
    @State private var isConfirmingClearHistory = false

    var body: some View {
        VStack(alignment: .leading, spacing: 20) {
            HStack(alignment: .center, spacing: 16) {
                HeaderView(
                    title: "Scan History",
                    subtitle: "Completed scans and changes will be tracked here."
                )

                if !appModel.scanHistory.isEmpty {
                    Button(role: .destructive) {
                        isConfirmingClearHistory = true
                    } label: {
                        Label("Clear History", systemImage: "trash")
                    }
                    .buttonStyle(.bordered)
                }
            }

            if appModel.scanHistory.isEmpty {
                emptyHistoryView
            } else {
                List(appModel.scanHistory) { scan in
                    HStack(spacing: 16) {
                        Image(systemName: iconName(for: scan.status))
                            .foregroundStyle(color(for: scan.status))

                        VStack(alignment: .leading, spacing: 4) {
                            Text(scan.startedAt.formatted(date: .abbreviated, time: .shortened))
                                .font(.headline)

                            Text(scan.errorMessage ?? "\(scan.discoveredCount) devices discovered")
                                .foregroundStyle(.secondary)
                        }

                        Spacer()

                        Text(scan.status.rawValue.capitalized)
                            .font(.caption.weight(.semibold))
                            .padding(.horizontal, 10)
                            .padding(.vertical, 5)
                            .background(.background.secondary, in: Capsule())
                    }
                    .padding(.vertical, 6)
                }
            }

            Spacer()
        }
        .padding(28)
        .confirmationDialog(
            "Clear scan history?",
            isPresented: $isConfirmingClearHistory,
            titleVisibility: .visible
        ) {
            Button("Clear History", role: .destructive) {
                appModel.clearScanHistory()
            }

            Button("Cancel", role: .cancel) {}
        } message: {
            Text("This removes all saved scan history. Devices and settings will not be deleted.")
        }
    }

    private var emptyHistoryView: some View {
        ZStack {
            Color.clear

            ContentUnavailableView(
                "No History",
                systemImage: "clock.arrow.circlepath",
                description: Text("Run a scan to start tracking scan history.")
            )
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    private func iconName(for status: ScanRecord.Status) -> String {
        switch status {
        case .running:
            "arrow.clockwise"
        case .completed:
            "checkmark.circle"
        case .failed:
            "exclamationmark.triangle"
        }
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
}

#Preview {
    ScanHistoryView()
        .environment(AppModel())
        .frame(width: 980, height: 640)
}
