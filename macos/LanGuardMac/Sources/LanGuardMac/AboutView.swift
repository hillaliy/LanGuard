import SwiftUI

struct AboutView: View {
    private let projectURL = URL(string: "https://github.com/hillaliy/LanGuard")!
    private let donationURL = URL(string: "https://www.paypal.me/hillaliy")!
    private let releasesURL = URL(string: "https://github.com/hillaliy/LanGuard/releases")!

    @State private var updateState: AboutUpdateState = .idle

    var body: some View {
        ScrollView {
            VStack(spacing: 24) {
                VStack(spacing: 12) {
                    ZStack {
                        RoundedRectangle(cornerRadius: 22)
                            .fill(.blue.opacity(0.14))
                            .frame(width: 104, height: 104)

                        Image(systemName: "shield.lefthalf.filled.badge.checkmark")
                            .font(.system(size: 60, weight: .semibold))
                            .foregroundStyle(.blue)
                    }

                    HStack(alignment: .firstTextBaseline, spacing: 10) {
                        Text("LanGuard")
                            .font(.system(size: 40, weight: .semibold, design: .rounded))

                        Text("v\(AppVersion.current)")
                            .font(.system(size: 15, weight: .semibold, design: .rounded))
                            .foregroundStyle(.secondary)
                            .padding(.horizontal, 11)
                            .padding(.vertical, 5)
                            .background(.quaternary.opacity(0.7), in: Capsule())
                            .overlay {
                                Capsule()
                                    .stroke(.quaternary)
                            }
                            .offset(y: -5)
                    }

                    Text("Native local network watch for macOS")
                        .font(.title3)
                        .foregroundStyle(.secondary)
                }
                .frame(maxWidth: .infinity)
                .padding(.top, 14)

                VStack(spacing: 16) {
                    AboutSummaryCard()

                    AboutUpdateCard(
                        updateState: updateState,
                        releasesURL: releasesURL,
                        onCheck: checkForUpdates
                    )

                    LazyVGrid(columns: [GridItem(.adaptive(minimum: 220), spacing: 14)], spacing: 14) {
                        AboutInfoCard(title: "Platform", value: "macOS 26+", systemImage: "macwindow")
                        AboutInfoCard(title: "Data", value: "Stored locally", systemImage: "lock.shield")
                        AboutInfoCard(title: "Mode", value: "Home and client scans", systemImage: "network")
                    }

                    LazyVGrid(columns: [GridItem(.adaptive(minimum: 240), spacing: 14)], spacing: 14) {
                        AboutLinkButton(
                            title: "GitHub",
                            subtitle: "Source code and releases",
                            icon: .github,
                            tint: .primary,
                            url: projectURL
                        )

                        AboutLinkButton(
                            title: "PayPal",
                            subtitle: "Support development",
                            icon: .paypal,
                            tint: .blue,
                            url: donationURL
                        )
                    }
                }
                .frame(maxWidth: 820)
            }
            .padding(.horizontal, 34)
            .padding(.vertical, 34)
            .frame(maxWidth: .infinity, alignment: .center)
        }
    }

    private func checkForUpdates() {
        updateState = .checking

        Task {
            do {
                let result = try await VersionUpdateChecker.check(currentVersion: AppVersion.current)
                await MainActor.run {
                    updateState = result.isUpdateAvailable
                        ? .updateAvailable(version: result.latestVersion, url: result.releaseURL)
                        : .upToDate(version: result.latestVersion)
                }
            } catch {
                await MainActor.run {
                    updateState = .failed("Could not reach GitHub Releases.")
                }
            }
        }
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
            "Checking GitHub Releases"
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
            "Compare this app with the latest release on GitHub."
        case .checking:
            "Looking for the newest LanGuard release."
        case .upToDate(let version):
            "v\(version) is the latest release."
        case .updateAvailable(let version, _):
            "v\(version) is available."
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

private struct AboutSummaryCard: View {
    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text("About LanGuard")
                .font(.title3.weight(.semibold))

            Text("LanGuard discovers devices on your local network, keeps a local inventory, tracks scan changes, and highlights unknown or risky devices without sending your device list to a server.")
                .font(.body)
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)

            LazyVGrid(columns: [GridItem(.adaptive(minimum: 220), spacing: 12)], spacing: 12) {
                AboutFeaturePill(systemImage: "desktopcomputer", text: "Device inventory")
                AboutFeaturePill(systemImage: "clock.arrow.circlepath", text: "Scan history")
                AboutFeaturePill(systemImage: "exclamationmark.shield", text: "Risk badges")
                AboutFeaturePill(systemImage: "person.crop.circle", text: "Guest scan")
            }
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

private struct AboutUpdateCard: View {
    let updateState: AboutUpdateState
    let releasesURL: URL
    let onCheck: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack(alignment: .center, spacing: 12) {
                Image(systemName: updateState.icon)
                    .font(.system(size: 18, weight: .semibold))
                    .foregroundStyle(updateState.tint)
                    .frame(width: 38, height: 38)
                    .background(updateState.tint.opacity(0.12), in: RoundedRectangle(cornerRadius: 11))

                VStack(alignment: .leading, spacing: 3) {
                    Text(updateState.title)
                        .font(.headline)
                    Text(updateState.message)
                        .font(.callout)
                        .foregroundStyle(.secondary)
                        .fixedSize(horizontal: false, vertical: true)
                }

                Spacer(minLength: 12)

                if case .checking = updateState {
                    ProgressView()
                        .controlSize(.small)
                }
            }

            HStack(spacing: 10) {
                Button {
                    onCheck()
                } label: {
                    Label("Check for Updates", systemImage: "arrow.triangle.2.circlepath")
                }
                .disabled(updateState == .checking)

                Link(destination: updateReleaseURL) {
                    Label(updateReleaseTitle, systemImage: "arrow.up.right.square")
                }
            }
        }
        .padding(18)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(.background.secondary, in: RoundedRectangle(cornerRadius: 18))
        .overlay {
            RoundedRectangle(cornerRadius: 18)
                .stroke(.quaternary)
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
}

private struct AboutFeaturePill: View {
    let systemImage: String
    let text: String

    var body: some View {
        Label(text, systemImage: systemImage)
            .font(.callout.weight(.medium))
            .foregroundStyle(.secondary)
            .padding(.horizontal, 12)
            .padding(.vertical, 10)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(.background, in: RoundedRectangle(cornerRadius: 12))
            .overlay {
                RoundedRectangle(cornerRadius: 12)
                    .stroke(.quaternary)
            }
    }
}

private struct AboutLinkButton: View {
    let title: String
    let subtitle: String
    let icon: AboutBrandIcon.Kind
    let tint: Color
    let url: URL

    var body: some View {
        Link(destination: url) {
            HStack(spacing: 12) {
                AboutBrandIcon(kind: icon, tint: tint)

                VStack(alignment: .leading, spacing: 3) {
                    Text(title)
                        .font(.headline)
                        .foregroundStyle(.primary)

                    Text(subtitle)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .lineLimit(1)
                }

                Spacer(minLength: 0)

                Image(systemName: "arrow.up.right")
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(.secondary)
            }
            .padding(14)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(.background.secondary, in: RoundedRectangle(cornerRadius: 14))
            .overlay {
                RoundedRectangle(cornerRadius: 14)
                    .stroke(.quaternary)
            }
        }
        .buttonStyle(.plain)
        .help(url.absoluteString)
    }
}

private struct AboutBrandIcon: View {
    enum Kind {
        case github
        case paypal
    }

    let kind: Kind
    let tint: Color

    var body: some View {
        ZStack {
            RoundedRectangle(cornerRadius: 10)
                .fill(tint.opacity(0.12))

            switch kind {
            case .github:
                Image(systemName: "chevron.left.forwardslash.chevron.right")
                    .font(.system(size: 18, weight: .bold))
                    .foregroundStyle(tint)
            case .paypal:
                Image(systemName: "creditcard.fill")
                    .font(.system(size: 18, weight: .bold))
                    .foregroundStyle(tint)
            }
        }
        .frame(width: 40, height: 40)
    }
}

private struct AboutInfoCard: View {
    let title: String
    let value: String
    let systemImage: String

    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: systemImage)
                .font(.system(size: 17, weight: .semibold))
                .foregroundStyle(.blue)
                .frame(width: 34, height: 34)
                .background(.blue.opacity(0.12), in: RoundedRectangle(cornerRadius: 9))

            VStack(alignment: .leading, spacing: 2) {
                Text(title)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                Text(value)
                    .font(.headline)
            }

            Spacer(minLength: 0)
        }
        .padding(12)
        .background(.background.secondary, in: RoundedRectangle(cornerRadius: 14))
        .overlay {
            RoundedRectangle(cornerRadius: 14)
                .stroke(.quaternary)
        }
    }
}

#Preview {
    AboutView()
        .environment(AppModel())
}
