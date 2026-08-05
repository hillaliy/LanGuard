import SwiftUI

struct HeaderView: View {
    let title: String
    let subtitle: String
    var version: String?

    var body: some View {
        HStack(spacing: 14) {
            ZStack {
                RoundedRectangle(cornerRadius: 14)
                    .fill(.blue.opacity(0.16))
                    .frame(width: 58, height: 58)

                Image(systemName: "shield.lefthalf.filled.badge.checkmark")
                    .font(.system(size: 34, weight: .semibold))
                    .foregroundStyle(.blue)
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
}

enum AppVersion {
    static var current: String {
        let bundleVersion = Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String
        let normalizedVersion = bundleVersion?.trimmingCharacters(in: .whitespacesAndNewlines)
        return normalizedVersion?.isEmpty == false ? normalizedVersion! : "1.0.21"
    }
}

#Preview {
    HeaderView(title: "LanGuard", subtitle: "Local network watch for macOS", version: AppVersion.current)
        .padding()
}
