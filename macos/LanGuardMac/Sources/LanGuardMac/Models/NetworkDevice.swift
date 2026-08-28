import Foundation

enum DeviceIdentitySource: String, Codable, Hashable, Sendable {
    case reverseDNS = "reverse_dns"
    case mdns
    case llmnr
    case netBIOS = "netbios"
    case ssdp
    case snmp
    case http
    case arp
    case manuf
    case inferred
    case imported

    var title: String {
        switch self {
        case .reverseDNS: "Reverse DNS"
        case .mdns: "mDNS"
        case .llmnr: "LLMNR"
        case .netBIOS: "NetBIOS"
        case .ssdp: "SSDP / UPnP"
        case .snmp: "SNMP"
        case .http: "Device web interface"
        case .arp: "ARP"
        case .manuf: "Wireshark manuf"
        case .inferred: "Inferred"
        case .imported: "Imported inventory"
        }
    }

    var confidence: DeviceIdentityConfidence {
        switch self {
        case .reverseDNS, .mdns, .llmnr, .netBIOS, .snmp, .manuf:
            .high
        case .ssdp, .http, .arp, .imported:
            .medium
        case .inferred:
            .low
        }
    }
}

enum DeviceIdentityConfidence: String, Codable, Hashable, Sendable {
    case none
    case low
    case medium
    case high

    var title: String { rawValue.capitalized }
}

struct NetworkDevice: Codable, Identifiable, Hashable, Sendable {
    let id: String
    var name: String
    var ipAddress: String
    var macAddress: String
    var vendor: String?
    var vendorSource: DeviceIdentitySource?
    var hostname: String?
    var hostnameSource: DeviceIdentitySource?
    var comments: String
    var externalURL: String?
    var attentionAcknowledgedRiskSignature: String?
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
        vendorSource: DeviceIdentitySource? = nil,
        hostname: String? = nil,
        hostnameSource: DeviceIdentitySource? = nil,
        comments: String = "",
        externalURL: String? = nil,
        attentionAcknowledgedRiskSignature: String? = nil,
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
        self.vendorSource = vendor == nil ? nil : vendorSource
        self.hostname = HostnameResolver.clean(hostname, ipAddress: ipAddress)
        self.hostnameSource = self.hostname == nil ? nil : hostnameSource
        self.comments = comments
        self.externalURL = ExternalLinkValidator.normalizedString(externalURL)
        self.attentionAcknowledgedRiskSignature = attentionAcknowledgedRiskSignature
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
        case vendorSource
        case hostname
        case hostnameSource
        case comments
        case externalURL
        case attentionAcknowledgedRiskSignature
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
        vendorSource = try container.decodeIfPresent(DeviceIdentitySource.self, forKey: .vendorSource)
        let decodedHostname = try container.decodeIfPresent(String.self, forKey: .hostname)
        hostname = HostnameResolver.clean(decodedHostname, ipAddress: ipAddress)
        hostnameSource = try container.decodeIfPresent(DeviceIdentitySource.self, forKey: .hostnameSource)
        if vendor == nil { vendorSource = nil }
        if hostname == nil { hostnameSource = nil }
        comments = try container.decodeIfPresent(String.self, forKey: .comments) ?? ""
        externalURL = ExternalLinkValidator.normalizedString(
            try container.decodeIfPresent(String.self, forKey: .externalURL)
        )
        attentionAcknowledgedRiskSignature = try container.decodeIfPresent(
            String.self,
            forKey: .attentionAcknowledgedRiskSignature
        )
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
    var hostnameConfidence: DeviceIdentityConfidence {
        guard hostname != nil else { return .none }
        return hostnameSource?.confidence ?? .low
    }

    var vendorConfidence: DeviceIdentityConfidence {
        guard vendor != nil else { return .none }
        return vendorSource?.confidence ?? .low
    }

    var identityConfidence: DeviceIdentityConfidence {
        if hostnameConfidence == .high, vendorConfidence == .high {
            return .high
        }
        if hostnameConfidence == .high || vendorConfidence == .high
            || (hostnameConfidence == .medium && vendorConfidence == .medium) {
            return .medium
        }
        return .low
    }

    var riskFingerprint: String {
        [
            isKnown ? "known" : "unknown",
            effectiveRole.rawValue,
            risk.rawValue,
            openPorts.sorted().map(String.init).joined(separator: ","),
        ].joined(separator: "|")
    }

    var isAttentionAcknowledged: Bool {
        isKnown && attentionAcknowledgedRiskSignature == riskFingerprint
    }

    var needsAttention: Bool {
        (!isKnown || risk == .medium || risk == .high) && !isAttentionAcknowledged
    }

    mutating func setAttentionAcknowledged(_ acknowledged: Bool) {
        attentionAcknowledgedRiskSignature = acknowledged && isKnown ? riskFingerprint : nil
    }

    static func discovered(
        hostname: String?,
        hostnameSource: DeviceIdentitySource? = nil,
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
            hostnameSource: hostnameSource,
            status: .online,
            risk: .low,
            isKnown: false,
            isGateway: ipAddress == gatewayAddress,
            firstSeen: seenAt,
            lastSeen: seenAt
        )
    }
}
