import SwiftUI

struct AboutView: View {
    private let projectURL = URL(string: "https://github.com/hillaliy/LanGuard")!
    private let donationURL = URL(string: "https://www.paypal.me/hillaliy")!

    var body: some View {
        ScrollView {
            VStack(alignment: .center, spacing: 24) {
                HeaderView(
                    title: "About",
                    subtitle: "LanGuard for macOS",
                    version: AppVersion.current
                )
                .frame(maxWidth: 900)

                VStack(alignment: .center, spacing: 24) {
                    VStack(spacing: 16) {
                        ZStack {
                            RoundedRectangle(cornerRadius: 18)
                                .fill(.blue.opacity(0.14))
                                .frame(width: 86, height: 86)

                            Image(systemName: "shield.lefthalf.filled.badge.checkmark")
                                .font(.system(size: 50, weight: .semibold))
                                .foregroundStyle(.blue)
                        }

                        VStack(spacing: 6) {
                            Text("LanGuard")
                                .font(.system(size: 36, weight: .semibold, design: .rounded))

                            Text("Local network watch for macOS")
                                .font(.title3)
                                .foregroundStyle(.secondary)
                        }
                    }

                    Text("LanGuard scans the local network, identifies devices, tracks changes, and highlights devices that may need attention.")
                        .font(.body)
                        .foregroundStyle(.secondary)
                        .multilineTextAlignment(.center)
                        .fixedSize(horizontal: false, vertical: true)

                    LazyVGrid(columns: [GridItem(.adaptive(minimum: 190), spacing: 12)], spacing: 12) {
                        AboutInfoCard(title: "Version", value: "v\(AppVersion.current)", systemImage: "tag")
                        AboutInfoCard(title: "Platform", value: "macOS 26+", systemImage: "macwindow")
                        AboutInfoCard(title: "Privacy", value: "Local data", systemImage: "lock.shield")
                    }

                    LazyVGrid(columns: [GridItem(.adaptive(minimum: 210), spacing: 14)], spacing: 14) {
                        AboutLinkButton(
                            title: "GitHub",
                            subtitle: "hillaliy/LanGuard",
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

                    VStack(alignment: .leading, spacing: 10) {
                        AboutFeatureRow(systemImage: "network", text: "Discovers local network devices")
                        AboutFeatureRow(systemImage: "clock.arrow.circlepath", text: "Tracks scan history and device changes")
                        AboutFeatureRow(systemImage: "exclamationmark.shield", text: "Highlights unknown and higher-risk devices")
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                }
                .padding(28)
                .frame(maxWidth: 900)
                .background(.background.secondary, in: RoundedRectangle(cornerRadius: 18))
                .overlay {
                    RoundedRectangle(cornerRadius: 18)
                        .stroke(.quaternary)
                }
            }
            .padding(32)
            .frame(maxWidth: .infinity, alignment: .center)
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
            .background(.background, in: RoundedRectangle(cornerRadius: 14))
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
        .background(.background, in: RoundedRectangle(cornerRadius: 14))
        .overlay {
            RoundedRectangle(cornerRadius: 14)
                .stroke(.quaternary)
        }
    }
}

private struct AboutFeatureRow: View {
    let systemImage: String
    let text: String

    var body: some View {
        Label(text, systemImage: systemImage)
            .font(.callout)
            .foregroundStyle(.secondary)
    }
}

#Preview {
    AboutView()
        .environment(AppModel())
}
