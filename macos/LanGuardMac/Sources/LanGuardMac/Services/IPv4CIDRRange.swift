import Foundation

struct IPv4CIDRRange: Sendable {
    private let network: UInt32
    private let mask: UInt32
    private let prefix: Int

    init?(_ rawValue: String) {
        let parts = rawValue.trimmingCharacters(in: .whitespacesAndNewlines).split(separator: "/")
        guard
            parts.count == 2,
            let address = Self.ipv4Value(String(parts[0])),
            let prefix = Int(parts[1]),
            (0...32).contains(prefix)
        else {
            return nil
        }

        let mask = prefix == 0 ? 0 : UInt32.max << UInt32(32 - prefix)
        self.mask = mask
        self.network = address & mask
        self.prefix = prefix
    }

    func contains(_ ipAddress: String) -> Bool {
        guard let address = Self.ipv4Value(ipAddress) else {
            return false
        }

        return address & mask == network
    }

    func usableHosts(limit: Int = 4_096) -> [String] {
        let broadcast = network | ~mask
        let start: UInt32
        let end: UInt32

        if prefix >= 31 {
            start = network
            end = broadcast
        } else {
            start = network + 1
            end = broadcast - 1
        }

        guard start <= end else {
            return []
        }

        let total = Int(min(UInt64(end - start + 1), UInt64(limit)))
        return (0..<total).map { Self.ipv4String(start + UInt32($0)) }
    }

    private static func ipv4Value(_ rawValue: String) -> UInt32? {
        let octets = rawValue.split(separator: ".")
        guard octets.count == 4 else { return nil }

        var value: UInt32 = 0
        for octet in octets {
            guard let number = UInt8(octet) else {
                return nil
            }
            value = (value << 8) | UInt32(number)
        }

        return value
    }

    private static func ipv4String(_ value: UInt32) -> String {
        [
            (value >> 24) & 0xff,
            (value >> 16) & 0xff,
            (value >> 8) & 0xff,
            value & 0xff,
        ]
        .map(String.init)
        .joined(separator: ".")
    }
}
