import SwiftUI

struct HeaderView: View {
    let title: String
    let subtitle: String

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
                Text(title)
                    .font(.system(size: 34, weight: .semibold, design: .rounded))

                Text(subtitle)
                    .font(.callout)
                    .foregroundStyle(.secondary)
            }

            Spacer()
        }
    }
}

#Preview {
    HeaderView(title: "LanGuard", subtitle: "Local network watch for macOS")
        .padding()
}
