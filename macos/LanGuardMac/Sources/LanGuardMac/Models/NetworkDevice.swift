import Foundation

struct NetworkDevice: Codable, Identifiable, Hashable, Sendable {
    let id: String
    var name: String
    var ipAddress: String
    var macAddress: String
    var vendor: String?
    var hostname: String?
    var iconName: String?
    var secondaryIconName: String?
    var status: DeviceStatus
    var risk: DeviceRisk
    var role: DeviceRole?
    var room: String?
    var isKnown: Bool
    var isGateway: Bool
    var openPorts: [Int]
    var missedScans: Int
    var firstSeen: Date
    var lastSeen: Date

    init(
        id: String,
        name: String,
        ipAddress: String,
        macAddress: String,
        vendor: String? = nil,
        hostname: String? = nil,
        iconName: String? = nil,
        secondaryIconName: String? = nil,
        status: DeviceStatus = .unknown,
        risk: DeviceRisk = .low,
        role: DeviceRole? = nil,
        room: String? = nil,
        isKnown: Bool = false,
        isGateway: Bool = false,
        openPorts: [Int] = [],
        missedScans: Int = 0,
        firstSeen: Date = .now,
        lastSeen: Date = .now
    ) {
        self.id = id
        self.name = name
        self.ipAddress = ipAddress
        self.macAddress = macAddress
        self.vendor = vendor
        self.hostname = hostname
        self.iconName = iconName
        self.secondaryIconName = secondaryIconName
        self.status = status
        self.risk = risk
        self.role = role
        self.room = room
        self.isKnown = isKnown
        self.isGateway = isGateway
        self.openPorts = openPorts.sorted()
        self.missedScans = missedScans
        self.firstSeen = firstSeen
        self.lastSeen = lastSeen
    }

    private enum CodingKeys: String, CodingKey {
        case id
        case name
        case ipAddress
        case macAddress
        case vendor
        case hostname
        case iconName
        case secondaryIconName
        case status
        case risk
        case role
        case room
        case isKnown
        case isGateway
        case openPorts
        case missedScans
        case firstSeen
        case lastSeen
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        id = try container.decode(String.self, forKey: .id)
        name = try container.decode(String.self, forKey: .name)
        ipAddress = try container.decode(String.self, forKey: .ipAddress)
        macAddress = try container.decode(String.self, forKey: .macAddress)
        vendor = try container.decodeIfPresent(String.self, forKey: .vendor)
        hostname = try container.decodeIfPresent(String.self, forKey: .hostname)
        iconName = try container.decodeIfPresent(String.self, forKey: .iconName)
        secondaryIconName = try container.decodeIfPresent(String.self, forKey: .secondaryIconName)
        status = try container.decodeIfPresent(DeviceStatus.self, forKey: .status) ?? .unknown
        risk = try container.decodeIfPresent(DeviceRisk.self, forKey: .risk) ?? .low
        role = try container.decodeIfPresent(DeviceRole.self, forKey: .role)
        room = try container.decodeIfPresent(String.self, forKey: .room)
        isKnown = try container.decodeIfPresent(Bool.self, forKey: .isKnown) ?? false
        isGateway = try container.decodeIfPresent(Bool.self, forKey: .isGateway) ?? false
        openPorts = try container.decodeIfPresent([Int].self, forKey: .openPorts) ?? []
        missedScans = try container.decodeIfPresent(Int.self, forKey: .missedScans) ?? 0
        firstSeen = try container.decodeIfPresent(Date.self, forKey: .firstSeen) ?? .now
        lastSeen = try container.decodeIfPresent(Date.self, forKey: .lastSeen) ?? firstSeen
    }
}

extension NetworkDevice {
    static func discovered(
        hostname: String?,
        ipAddress: String,
        macAddress: String,
        gatewayAddress: String?,
        seenAt: Date = .now
    ) -> NetworkDevice {
        let normalizedMAC = macAddress.lowercased()
        let displayName = DeviceNameGuesser.displayName(hostname: hostname, macAddress: normalizedMAC)

        return NetworkDevice(
            id: normalizedMAC,
            name: displayName,
            ipAddress: ipAddress,
            macAddress: normalizedMAC,
            hostname: hostname,
            status: .online,
            risk: .low,
            isKnown: false,
            isGateway: ipAddress == gatewayAddress,
            firstSeen: seenAt,
            lastSeen: seenAt
        )
    }
}
