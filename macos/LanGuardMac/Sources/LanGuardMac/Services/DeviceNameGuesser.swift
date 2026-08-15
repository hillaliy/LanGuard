import Foundation

enum DeviceNameGuesser {
    static func displayName(hostname: String?, macAddress: String) -> String {
        displayName(
            hostname: hostname,
            macAddress: macAddress,
            vendor: nil,
            openPorts: [],
            isGateway: false
        )
    }

    static func displayName(
        hostname: String?,
        macAddress: String,
        vendor: String?,
        openPorts: [Int],
        isGateway: Bool
    ) -> String {
        if let cleanedHostname = hostname?.trimmingCharacters(in: .whitespacesAndNewlines),
           !cleanedHostname.isEmpty,
           cleanedHostname != "?" {
            return cleanedHostname
        }

        if isGateway {
            if let vendor {
                return "\(vendor) Router"
            }
            return "Router"
        }

        if openPorts.contains(9100) {
            return vendor.map { "\($0) Printer" } ?? "Printer"
        }

        if openPorts.contains(554) {
            return vendor.map { "\($0) Camera" } ?? "Camera"
        }

        if let vendor {
            return "\(vendor) Device"
        }

        let suffix = macSuffix(macAddress)

        if suffix.isEmpty {
            return "Unknown Device"
        }

        if MACVendorResolver.isLocallyAdministered(macAddress) {
            return "Private Device \(suffix)"
        }

        return "Unknown Device \(suffix)"
    }

    static func isMACAddressText(_ value: String) -> Bool {
        let compact = value
            .trimmingCharacters(in: .whitespacesAndNewlines)
            .filter(\.isHexDigit)

        return compact.count == 12
    }

    static func macSuffix(_ macAddress: String) -> String {
        macAddress
            .filter(\.isHexDigit)
            .suffix(4)
            .uppercased()
    }
}
