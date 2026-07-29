import Foundation

struct AppStorageSnapshot: Codable, Equatable, Sendable {
    var devices: [NetworkDevice]
    var scanHistory: [ScanRecord]
    var settings: AppSettings
    var recentChanges: [DeviceChange]

    static let empty = AppStorageSnapshot(devices: [], scanHistory: [], settings: .default, recentChanges: [])

    init(
        devices: [NetworkDevice],
        scanHistory: [ScanRecord],
        settings: AppSettings = .default,
        recentChanges: [DeviceChange] = []
    ) {
        self.devices = devices
        self.scanHistory = scanHistory
        self.settings = settings
        self.recentChanges = recentChanges
    }

    enum CodingKeys: String, CodingKey {
        case devices
        case scanHistory
        case settings
        case recentChanges
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        devices = try container.decode([NetworkDevice].self, forKey: .devices)
        scanHistory = try container.decode([ScanRecord].self, forKey: .scanHistory)
        settings = try container.decodeIfPresent(AppSettings.self, forKey: .settings) ?? .default
        recentChanges = try container.decodeIfPresent([DeviceChange].self, forKey: .recentChanges) ?? []
    }
}
