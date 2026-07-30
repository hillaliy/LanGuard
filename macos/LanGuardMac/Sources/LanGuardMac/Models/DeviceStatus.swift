import Foundation

enum DeviceStatus: String, Codable, CaseIterable, Identifiable, Sendable {
    case online
    case recentlySeen = "recently_seen"
    case offline
    case unknown

    var id: String { rawValue }

    var title: String {
        switch self {
        case .online:
            "Online"
        case .recentlySeen:
            "Recently Seen"
        case .offline:
            "Offline"
        case .unknown:
            "Unknown"
        }
    }
}
