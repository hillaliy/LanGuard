import Foundation

struct DeviceInventoryImportResult: Sendable {
    let created: Int
    let updated: Int
    let skipped: Int
}

struct DeviceInventoryDocument: Codable {
    static let format = "languard-device-inventory"

    var format: String
    var version: Int
    var exportedAt: Date
    var devices: [DeviceInventoryItem]

    init(devices: [NetworkDevice]) {
        self.format = Self.format
        self.version = 1
        self.exportedAt = .now
        self.devices = devices.map(DeviceInventoryItem.init(device:))
    }

    private enum CodingKeys: String, CodingKey {
        case format
        case version
        case exportedAt = "exported_at"
        case devices
    }
}

struct DeviceInventoryItem: Codable {
    var name: String
    var ip: String
    var mac: String
    var vendor: String?
    var hostname: String?
    var icon: String?
    var known: Bool
    var isGateway: Bool
    var status: String?
    var risk: String?
    var openPorts: [Int]
    var firstSeen: Date?
    var lastSeen: Date?

    init(device: NetworkDevice) {
        self.name = device.name
        self.ip = device.ipAddress
        self.mac = device.macAddress
        self.vendor = device.vendor
        self.hostname = device.hostname
        self.icon = device.iconName
        self.known = device.isKnown
        self.isGateway = device.isGateway
        self.status = device.status.rawValue
        self.risk = device.risk.rawValue
        self.openPorts = device.openPorts
        self.firstSeen = device.firstSeen
        self.lastSeen = device.lastSeen
    }

    var normalizedMAC: String? {
        let value = mac.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        return value.isEmpty ? nil : value
    }

    var normalizedIP: String? {
        let value = ip.trimmingCharacters(in: .whitespacesAndNewlines)
        return Self.isValidIPv4Address(value) ? value : nil
    }

    func merged(into existing: NetworkDevice?) -> NetworkDevice? {
        guard let normalizedMAC, let normalizedIP else {
            return nil
        }

        let importedFirstSeen = firstSeen ?? existing?.firstSeen ?? .now
        let importedLastSeen = lastSeen ?? existing?.lastSeen ?? importedFirstSeen
        let existingFirstSeen = existing?.firstSeen ?? importedFirstSeen
        let deviceStatus = DeviceStatus(rawValue: status ?? "") ?? existing?.status ?? .unknown
        let deviceRisk = DeviceRisk(rawValue: risk ?? "") ?? existing?.risk ?? DeviceRiskScorer.risk(
            for: normalizedPorts,
            isKnown: known
        )
        let displayName = name.trimmingCharacters(in: .whitespacesAndNewlines)

        return NetworkDevice(
            id: normalizedMAC,
            name: displayName.isEmpty ? existing?.name ?? DeviceNameGuesser.displayName(hostname: hostname, macAddress: normalizedMAC) : displayName,
            ipAddress: normalizedIP,
            macAddress: normalizedMAC,
            vendor: normalizedText(vendor) ?? existing?.vendor,
            hostname: normalizedText(hostname) ?? existing?.hostname,
            iconName: normalizedText(icon) ?? existing?.iconName,
            status: deviceStatus,
            risk: deviceRisk,
            isKnown: known,
            isGateway: isGateway,
            openPorts: normalizedPorts,
            firstSeen: min(existingFirstSeen, importedFirstSeen),
            lastSeen: max(importedLastSeen, existing?.lastSeen ?? importedLastSeen)
        )
    }

    private var normalizedPorts: [Int] {
        Array(Set(openPorts.filter { (1...65535).contains($0) })).sorted()
    }

    private func normalizedText(_ value: String?) -> String? {
        let trimmed = value?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        return trimmed.isEmpty ? nil : trimmed
    }

    private static func isValidIPv4Address(_ value: String) -> Bool {
        let octets = value.split(separator: ".")
        guard octets.count == 4 else { return false }
        return octets.allSatisfy { UInt8($0) != nil }
    }

    private enum CodingKeys: String, CodingKey {
        case name
        case ip
        case mac
        case vendor
        case hostname
        case icon
        case known
        case isGateway = "is_gateway"
        case status
        case risk
        case openPorts = "open_ports"
        case firstSeen = "first_seen"
        case lastSeen = "last_seen"
    }
}
