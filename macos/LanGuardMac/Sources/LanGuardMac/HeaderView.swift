import AppKit
import SwiftUI

struct HeaderView: View {
    @Environment(\.colorScheme) private var colorScheme

    let title: String
    let subtitle: String
    var systemImage: String = "shield.lefthalf.filled.badge.checkmark"
    var assetImage: String?
    var version: String?

    var body: some View {
        HStack(spacing: 14) {
            ZStack {
                if let assetImage, let image = HeaderIconImage.load(named: assetImage) {
                    Image(nsImage: image)
                        .resizable()
                        .scaledToFit()
                        .frame(width: 58, height: 58)
                        .shadow(color: assetIconShadowColor, radius: 6, y: 2)
                } else {
                    RoundedRectangle(cornerRadius: 14)
                        .fill(.blue.opacity(0.16))
                        .frame(width: 58, height: 58)

                    Image(systemName: systemImage)
                        .font(.system(size: 34, weight: .semibold))
                        .foregroundStyle(.blue)
                }
            }

            VStack(alignment: .leading, spacing: 4) {
                HStack(alignment: .firstTextBaseline, spacing: 10) {
                    Text(title)
                        .font(.system(size: 34, weight: .semibold, design: .rounded))

                    if let version {
                        Text("v\(version)")
                            .font(.system(size: 15, weight: .semibold, design: .rounded))
                            .foregroundStyle(.secondary)
                            .padding(.horizontal, 10)
                            .padding(.vertical, 4)
                            .background(.quaternary.opacity(0.7), in: Capsule())
                            .overlay {
                                Capsule()
                                    .stroke(.quaternary)
                            }
                            .offset(y: -5)
                    }
                }

                Text(subtitle)
                    .font(.callout)
                    .foregroundStyle(.secondary)
            }

            Spacer()
        }
    }

    private var assetIconShadowColor: Color {
        colorScheme == .dark ? .black.opacity(0.35) : .clear
    }
}

private enum HeaderIconImage {
    static func load(named name: String) -> NSImage? {
        if let bundledImage = NSImage(named: name) {
            return bundledImage
        }

        let resourceCandidates = [
            Bundle.main.resourceURL,
            Bundle.main.bundleURL.appending(path: "Contents/Resources", directoryHint: .isDirectory),
            URL(fileURLWithPath: #filePath)
                .deletingLastPathComponent()
                .deletingLastPathComponent()
                .deletingLastPathComponent()
                .appending(path: "Resources", directoryHint: .isDirectory),
        ].compactMap(\.self)

        for resourceURL in resourceCandidates {
            let imageURL = resourceURL.appending(path: "\(name).png")
            if let image = NSImage(contentsOf: imageURL) {
                return image
            }
        }

        return nil
    }
}

enum AppVersion {
    static var current: String {
        let bundleVersion = Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String
        let normalizedVersion = bundleVersion?.trimmingCharacters(in: .whitespacesAndNewlines)
        return normalizedVersion?.isEmpty == false ? normalizedVersion! : "1.1.4"
    }
}

#Preview {
    HeaderView(
        title: "LanGuard",
        subtitle: "Local network watch for macOS",
        assetImage: "LanGuardIcon",
        version: AppVersion.current
    )
        .padding()
}
