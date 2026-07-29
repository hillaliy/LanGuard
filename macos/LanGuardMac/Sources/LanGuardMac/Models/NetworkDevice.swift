import Foundation

struct NetworkDevice: Codable, Identifiable, Hashable, Sendable {
    let id: String
    var name: String
    var ipAddress: String
    var macAddress: String
    var vendor: String?
    var hostname: String?
    var iconName: String?
    var status: DeviceStatus
    var risk: DeviceRisk
    var isKnown: Bool
    var isGateway: Bool
    var openPorts: [Int]
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
        status: DeviceStatus = .unknown,
        risk: DeviceRisk = .low,
        isKnown: Bool = false,
        isGateway: Bool = false,
        openPorts: [Int] = [],
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
        self.status = status
        self.risk = risk
        self.isKnown = isKnown
        self.isGateway = isGateway
        self.openPorts = openPorts.sorted()
        self.firstSeen = firstSeen
        self.lastSeen = lastSeen
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
