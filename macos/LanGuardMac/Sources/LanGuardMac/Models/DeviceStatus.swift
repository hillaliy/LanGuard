import Foundation

enum DeviceStatus: String, Codable, CaseIterable, Identifiable, Sendable {
    case online
    case offline
    case unknown

    var id: String { rawValue }

    var title: String {
        switch self {
        case .online:
            "Online"
        case .offline:
            "Offline"
        case .unknown:
            "Unknown"
        }
    }
}
