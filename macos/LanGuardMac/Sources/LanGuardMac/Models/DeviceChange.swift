import Foundation

struct DeviceChange: Codable, Identifiable, Hashable, Sendable {
    enum ChangeKind: String, Codable, Sendable {
        case ipAddress
        case ports
        case risk

        var title: String {
            switch self {
            case .ipAddress:
                "IP Changed"
            case .ports:
                "Ports Changed"
            case .risk:
                "Risk Changed"
            }
        }
    }

    let id: UUID
    var deviceID: String
    var deviceName: String
    var ipAddress: String
    var kind: ChangeKind
    var changedAt: Date

    init(
        id: UUID = UUID(),
        deviceID: String,
        deviceName: String,
        ipAddress: String,
        kind: ChangeKind,
        changedAt: Date = .now
    ) {
        self.id = id
        self.deviceID = deviceID
        self.deviceName = deviceName
        self.ipAddress = ipAddress
        self.kind = kind
        self.changedAt = changedAt
    }
}
