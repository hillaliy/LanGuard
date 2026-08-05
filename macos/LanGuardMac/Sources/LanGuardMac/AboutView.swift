import SwiftUI

struct AboutView: View {
    private let projectURL = URL(string: "https://github.com/hillaliy/LanGuard")!
    private let donationURL = URL(string: "https://www.paypal.me/hillaliy")!
    private let releasesURL = URL(string: "https://github.com/hillaliy/LanGuard/releases")!

    @Environment(AppModel.self) private var appModel
    @State private var updateState: AboutUpdateState = .idle

    var body: some View {
        VStack(spacing: 4) {
            ZStack {
                RoundedRectangle(cornerRadius: 30, style: .continuous)
                    .fill(.blue.gradient)
                    .frame(width: 96, height: 96)
                    .shadow(color: .blue.opacity(0.24), radius: 12, y: 6)

                Image(systemName: "shield.lefthalf.filled.badge.checkmark")
                    .font(.system(size: 56, weight: .semibold))
                    .foregroundStyle(.white)
            }

            Text("LanGuard")
                .font(.system(size: 26, weight: .semibold, design: .rounded))

            Text("Native local network watch for macOS")
                .font(.callout)
                .foregroundStyle(.secondary)

            Text("Version \(AppVersion.current)")
                .font(.callout)
                .foregroundStyle(.secondary)

            VStack(spacing: 2) {
                Text("© 2026 LanGuard")
                Text("All rights reserved.")
            }
            .font(.callout)
            .foregroundStyle(.secondary)

            Divider()
                .frame(maxWidth: 240)
                .padding(.vertical, 1)

            VStack(spacing: 3) {
                if case .checking = updateState {
                    ProgressView()
                        .controlSize(.small)
                        .frame(height: 20)
                } else {
                    Image(systemName: updateState.icon)
                        .font(.system(size: 19, weight: .semibold))
                        .foregroundStyle(updateState.tint)
                        .frame(height: 20)
                }

                VStack(spacing: 2) {
                    Text(updateState.title)
                        .font(.headline)
                    Text(updateState.message)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .lineLimit(2)
                }
                .multilineTextAlignment(.center)
            }
            .frame(width: 280)

            HStack(spacing: 12) {
                Button {
                    checkForUpdates()
                } label: {
                    Label("Check for Updates", systemImage: "arrow.triangle.2.circlepath")
                }
                .buttonStyle(.bordered)
                .controlSize(.small)
                .disabled(updateState == .checking)

                Link(destination: updateReleaseURL) {
                    Label(updateReleaseTitle, systemImage: "arrow.up.right.square")
                }
                .font(.callout)
            }

            HStack(spacing: 16) {
                Link(destination: projectURL) {
                    Label("GitHub", systemImage: "chevron.left.forwardslash.chevron.right")
                }

                Link(destination: donationURL) {
                    Label("PayPal", systemImage: "creditcard.fill")
                }
            }
            .font(.callout)

        }
        .frame(width: 340)
        .padding(16)
        .multilineTextAlignment(.center)
        .onAppear {
            syncUpdateStateFromSettings()
        }
        .onChange(of: appModel.settings.versionUpdate) { _, versionUpdate in
            guard updateState != .checking else { return }
            updateState = AboutUpdateState(versionUpdate)
        }
    }

    private var updateReleaseURL: URL {
        if case .updateAvailable(_, let url) = updateState {
            return url
        }

        return releasesURL
    }

    private var updateReleaseTitle: String {
        if case .updateAvailable = updateState {
            return "Open Release"
        }

        return "All Releases"
    }

    private func checkForUpdates() {
        updateState = .checking

        Task {
            let result = await appModel.checkForUpdates()

            await MainActor.run {
                switch result {
                case .success(let status):
                    updateState = status.isUpdateAvailable
                        ? .updateAvailable(version: status.latestVersion, url: status.releaseURL)
                        : .upToDate(version: status.latestVersion)
                case .failure:
                    updateState = .failed("Could not reach GitHub Releases.")
                }
            }
        }
    }

    private func syncUpdateStateFromSettings() {
        guard updateState != .checking else { return }
        updateState = AboutUpdateState(appModel.settings.versionUpdate)
    }
}

private extension AboutUpdateState {
    init(_ versionUpdate: AppVersionUpdate?) {
        guard let versionUpdate else {
            self = .idle
            return
        }

        self = versionUpdate.isUpdateAvailable
            ? .updateAvailable(version: versionUpdate.latestVersion, url: versionUpdate.releaseURL)
            : .upToDate(version: versionUpdate.latestVersion)
    }
}

private enum AboutUpdateState: Equatable {
    case idle
    case checking
    case upToDate(version: String)
    case updateAvailable(version: String, url: URL)
    case failed(String)

    var title: String {
        switch self {
        case .idle:
            "Check for updates"
        case .checking:
            "Checking for updates"
        case .upToDate:
            "LanGuard is up to date"
        case .updateAvailable:
            "New version available"
        case .failed:
            "Update check failed"
        }
    }

    var message: String {
        switch self {
        case .idle:
            "Check GitHub for the latest release."
        case .checking:
            "Looking for the newest LanGuard release."
        case .upToDate(let version):
            "v\(version) is the latest release."
        case .updateAvailable(let version, _):
            "v\(version) is available to download."
        case .failed(let message):
            message
        }
    }

    var icon: String {
        switch self {
        case .idle:
            "arrow.triangle.2.circlepath"
        case .checking:
            "clock"
        case .upToDate:
            "checkmark.seal"
        case .updateAvailable:
            "arrow.down.circle"
        case .failed:
            "exclamationmark.triangle"
        }
    }

    var tint: Color {
        switch self {
        case .idle, .checking:
            .blue
        case .upToDate:
            .green
        case .updateAvailable:
            .orange
        case .failed:
            .red
        }
    }
}

#Preview {
    AboutView()
        .environment(AppModel())
}
