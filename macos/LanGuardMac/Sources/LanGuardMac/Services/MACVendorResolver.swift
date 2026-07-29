import Foundation

enum MACVendorResolver {
    static func vendor(for macAddress: String) -> String? {
        let prefix = normalizedPrefix(macAddress)
        return BundledVendorDatabase.shared.vendor(forPrefix: prefix) ?? vendors[prefix]
    }

    private static func normalizedPrefix(_ macAddress: String) -> String {
        macAddress
            .lowercased()
            .split(separator: ":")
            .prefix(3)
            .joined(separator: ":")
    }

    private static let vendors: [String: String] = [
        "00:1a:11": "Google",
        "00:1b:63": "Apple",
        "00:1e:c2": "Apple",
        "00:25:00": "Apple",
        "04:bc:6d": "Apple",
        "0c:db:ea": "Apple",
        "24:a1:60": "Espressif",
        "28:6c:07": "Apple",
        "38:e1:3d": "Apple",
        "3c:5a:b4": "Google",
        "44:65:0d": "Amazon",
        "50:c7:bf": "TP-Link",
        "54:ef:44": "Samsung",
        "5c:e5:0c": "Xiaomi",
        "68:ff:7b": "TP-Link",
        "70:03:9f": "Apple",
        "74:da:88": "TP-Link",
        "8c:85:90": "Apple",
        "90:dd:5d": "Apple",
        "94:9f:3e": "Sonos",
        "9c:93:4e": "Hon Hai",
        "a4:ae:12": "Espressif",
        "b8:27:eb": "Raspberry Pi",
        "bc:5e:33": "Apple",
        "c0:6d:ed": "Apple",
        "d8:3a:dd": "Raspberry Pi",
        "dc:a6:32": "Raspberry Pi",
        "e4:5f:01": "Raspberry Pi",
        "ec:71:db": "Apple",
        "f0:c9:d1": "Midea",
        "f4:34:f0": "Apple",
    ]
}

final class BundledVendorDatabase: @unchecked Sendable {
    static let shared = BundledVendorDatabase()

    private let vendors: [String: String]

    private init(bundle: Bundle = .main) {
        guard
            bundle.bundleURL.pathExtension == "app",
            let url = bundle.url(forResource: "manuf", withExtension: nil),
            let contents = try? String(contentsOf: url, encoding: .utf8)
        else {
            vendors = [:]
            return
        }

        vendors = Self.parse(contents)
    }

    func vendor(forPrefix prefix: String) -> String? {
        vendors[prefix]
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

            let prefix = normalizeManufPrefix(String(parts[0]))
            guard prefix.split(separator: ":").count == 3 else {
                continue
            }

            parsedVendors[prefix] = String(parts[1])
        }

        return parsedVendors
    }

    private static func normalizeManufPrefix(_ rawPrefix: String) -> String {
        let prefixWithoutMask = rawPrefix
            .split(separator: "/")
            .first
            .map(String.init) ?? rawPrefix

        let normalized = prefixWithoutMask
            .replacingOccurrences(of: "-", with: ":")
            .lowercased()

        return normalized
            .split(separator: ":")
            .prefix(3)
            .map { part in
                part.count == 1 ? "0\(part)" : String(part)
            }
            .joined(separator: ":")
    }
}
