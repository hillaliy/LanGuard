import Foundation

struct AppSettings: Codable, Equatable, Sendable {
    var defaultScanRange: String
    var scanIntervalMinutes: Int
    var tcpPorts: [Int]
    var scheduledScanningEnabled: Bool
    var newDeviceNotificationsEnabled: Bool
    var riskyPortNotificationsEnabled: Bool

    static let defaultPorts = [22, 53, 80, 443, 554, 631, 8080, 8443, 9100]

    static let `default` = AppSettings(
        defaultScanRange: "192.168.0.0/24",
        scanIntervalMinutes: 5,
        tcpPorts: defaultPorts,
        scheduledScanningEnabled: false,
        newDeviceNotificationsEnabled: true,
        riskyPortNotificationsEnabled: true
    )

    var normalized: AppSettings {
        AppSettings(
            defaultScanRange: defaultScanRange.trimmingCharacters(in: .whitespacesAndNewlines),
            scanIntervalMinutes: min(max(scanIntervalMinutes, 1), 1440),
            tcpPorts: Self.normalizedPorts(tcpPorts),
            scheduledScanningEnabled: scheduledScanningEnabled,
            newDeviceNotificationsEnabled: newDeviceNotificationsEnabled,
            riskyPortNotificationsEnabled: riskyPortNotificationsEnabled
        )
    }

    static func parsePorts(_ rawValue: String) -> [Int]? {
        let parts = rawValue
            .split { character in
                character == "," || character == " " || character == "\n" || character == "\t"
            }

        guard !parts.isEmpty else { return nil }

        var ports: [Int] = []
        for part in parts {
            guard let port = Int(part), (1...65_535).contains(port) else {
                return nil
            }
            ports.append(port)
        }

        return normalizedPorts(ports)
    }

    enum CodingKeys: String, CodingKey {
        case defaultScanRange
        case scanIntervalMinutes
        case tcpPorts
        case scheduledScanningEnabled
        case newDeviceNotificationsEnabled
        case riskyPortNotificationsEnabled
    }

    init(
        defaultScanRange: String,
        scanIntervalMinutes: Int,
        tcpPorts: [Int],
        scheduledScanningEnabled: Bool,
        newDeviceNotificationsEnabled: Bool = Self.default.newDeviceNotificationsEnabled,
        riskyPortNotificationsEnabled: Bool = Self.default.riskyPortNotificationsEnabled
    ) {
        self.defaultScanRange = defaultScanRange
        self.scanIntervalMinutes = scanIntervalMinutes
        self.tcpPorts = tcpPorts
        self.scheduledScanningEnabled = scheduledScanningEnabled
        self.newDeviceNotificationsEnabled = newDeviceNotificationsEnabled
        self.riskyPortNotificationsEnabled = riskyPortNotificationsEnabled
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        defaultScanRange = try container.decodeIfPresent(String.self, forKey: .defaultScanRange) ?? Self.default.defaultScanRange
        scanIntervalMinutes = try container.decodeIfPresent(Int.self, forKey: .scanIntervalMinutes) ?? Self.default.scanIntervalMinutes
        tcpPorts = try container.decodeIfPresent([Int].self, forKey: .tcpPorts) ?? Self.default.tcpPorts
        scheduledScanningEnabled = try container.decodeIfPresent(Bool.self, forKey: .scheduledScanningEnabled) ?? Self.default.scheduledScanningEnabled
        newDeviceNotificationsEnabled = try container.decodeIfPresent(Bool.self, forKey: .newDeviceNotificationsEnabled) ?? Self.default.newDeviceNotificationsEnabled
        riskyPortNotificationsEnabled = try container.decodeIfPresent(Bool.self, forKey: .riskyPortNotificationsEnabled) ?? Self.default.riskyPortNotificationsEnabled
    }

    private static func normalizedPorts(_ ports: [Int]) -> [Int] {
        Array(Set(ports.filter { (1...65_535).contains($0) })).sorted()
    }
}
