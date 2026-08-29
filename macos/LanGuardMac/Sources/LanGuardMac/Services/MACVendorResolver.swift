import Foundation

enum MACVendorResolver {
    static func vendor(for macAddress: String) -> String? {
        guard canResolveHardwareVendor(for: macAddress) else {
            return nil
        }

        let macHex = normalizedHex(macAddress)
        let prefix = normalizedPrefix(macAddress)
        return displayVendor(BundledVendorDatabase.shared.vendor(forMACHex: macHex) ?? vendors[prefix])
    }

    static func preferredVendor(
        macAddress: String,
        observedVendor: String?
    ) -> String? {
        if isLocallyAdministered(macAddress) {
            return nil
        }

        if let observedDisplayVendor = displayVendor(observedVendor) {
            return observedDisplayVendor
        }

        if let resolved = vendor(for: macAddress) {
            return resolved
        }

        return nil
    }

    static func displayVendor(_ vendor: String?) -> String? {
        guard let cleaned = vendor?.trimmingCharacters(in: .whitespacesAndNewlines), !cleaned.isEmpty else {
            return nil
        }
        guard !isMACAddressText(cleaned) else {
            return nil
        }
        return cleaned
    }

    private static func isMACAddressText(_ value: String) -> Bool {
        let compact = value.filter(\.isHexDigit)
        let separators = value.filter { $0 == ":" || $0 == "-" }
        return compact.count == 12 && separators.count == 5
    }

    static func isLocallyAdministered(_ macAddress: String) -> Bool {
        guard
            let firstOctet = macAddress.split(separator: ":").first,
            let value = UInt8(firstOctet, radix: 16)
        else {
            return false
        }

        return value & 0x02 != 0
    }

    private static func canResolveHardwareVendor(for macAddress: String) -> Bool {
        guard
            let firstOctet = macAddress.split(separator: ":").first,
            let value = UInt8(firstOctet, radix: 16)
        else {
            return false
        }

        let isMulticast = value & 0x01 != 0
        return !isMulticast && !isLocallyAdministered(macAddress)
    }

    private static func normalizedPrefix(_ macAddress: String) -> String {
        macAddress
            .lowercased()
            .split(separator: ":")
            .prefix(3)
            .joined(separator: ":")
    }

    private static func normalizedHex(_ macAddress: String) -> String {
        macAddress
            .lowercased()
            .filter(\.isHexDigit)
    }

    private static let vendors: [String: String] = [
        "00:1a:11": "Google, Inc.",
        "00:1b:63": "Apple, Inc.",
        "00:1e:c2": "Apple, Inc.",
        "00:25:00": "Apple, Inc.",
        "04:bc:6d": "Apple, Inc.",
        "0c:db:ea": "Apple, Inc.",
        "24:a1:60": "Espressif Inc.",
        "28:6c:07": "Apple, Inc.",
        "38:e1:3d": "Apple, Inc.",
        "3c:5a:b4": "Google, Inc.",
        "44:65:0d": "Amazon Technologies Inc.",
        "50:c7:bf": "TP-Link Technologies Co., Ltd.",
        "54:ef:44": "Samsung Electronics Co., Ltd.",
        "5c:e5:0c": "Xiaomi Communications Co., Ltd.",
        "68:ff:7b": "TP-Link Technologies Co., Ltd.",
        "70:03:9f": "Apple, Inc.",
        "74:da:88": "TP-Link Technologies Co., Ltd.",
        "8c:85:90": "Apple, Inc.",
        "90:dd:5d": "Apple, Inc.",
        "90:ee:c7": "Samsung Electronics Co., Ltd.",
        "94:9f:3e": "Sonos, Inc.",
        "9c:93:4e": "Hon Hai Precision Industry Co., Ltd.",
        "a4:ae:12": "Espressif Inc.",
        "b8:27:eb": "Raspberry Pi Foundation",
        "bc:5e:33": "Hangzhou Hikvision Digital Technology Co., Ltd.",
        "c0:6d:ed": "Hangzhou Hikvision Digital Technology Co., Ltd.",
        "d8:3a:dd": "Raspberry Pi Foundation",
        "dc:a6:32": "Raspberry Pi Trading Ltd.",
        "e4:5f:01": "Raspberry Pi Trading Ltd.",
        "ec:71:db": "Apple, Inc.",
        "f0:c9:d1": "GD Midea Air-Conditioning Equipment Co., Ltd.",
        "f4:34:f0": "Apple, Inc.",
    ]

}

final class BundledVendorDatabase: @unchecked Sendable {
    static let shared = BundledVendorDatabase()

    private let vendors: [String: String]

    init(vendors: [String: String]) {
        self.vendors = vendors
    }

    private init(bundle: Bundle = .main) {
        guard
            let url = bundle.url(forResource: "manuf", withExtension: nil),
            let contents = try? String(contentsOf: url, encoding: .utf8)
        else {
            vendors = [:]
            return
        }

        vendors = Self.parse(contents)
    }

    func vendor(forMACHex macHex: String) -> String? {
        for length in stride(from: min(macHex.count, 12), through: 6, by: -1) {
            let prefix = String(macHex.prefix(length))
            if let vendor = vendors[prefix] {
                return vendor
            }
        }
        return nil
    }

    static func parse(_ contents: String) -> [String: String] {
        var parsedVendors: [String: String] = [:]

        for rawLine in contents.split(whereSeparator: \.isNewline) {
            let trimmedLine = rawLine.trimmingCharacters(in: .whitespaces)
            guard !trimmedLine.isEmpty, !trimmedLine.hasPrefix("#") else {
                continue
            }

            let parts = trimmedLine.split(whereSeparator: \.isWhitespace)
            guard parts.count >= 2 else {
                continue
            }

            guard let prefix = normalizeManufPrefix(String(parts[0])) else {
                continue
            }

            if parts.count > 2 {
                parsedVendors[prefix] = parts.dropFirst(2).joined(separator: " ")
            } else {
                parsedVendors[prefix] = String(parts[1])
            }
        }

        return parsedVendors
    }

    private static func normalizeManufPrefix(_ rawPrefix: String) -> String? {
        let parts = rawPrefix.split(separator: "/", maxSplits: 1).map(String.init)
        let addressHex = parts.first?
            .lowercased()
            .filter(\.isHexDigit) ?? ""
        guard addressHex.count >= 6 else {
            return nil
        }

        if parts.count == 2, let mask = Int(parts[1]), mask > 0 {
            let significantNibbles = min(addressHex.count, max(6, Int(ceil(Double(mask) / 4.0))))
            return String(addressHex.prefix(significantNibbles))
        }

        return String(addressHex.prefix(6))
    }
}
