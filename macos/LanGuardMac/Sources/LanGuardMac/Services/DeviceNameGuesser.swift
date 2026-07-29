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
            if vendor == "Espressif" {
                return "Espressif Smart Device"
            }
            if vendor == "Apple" {
                return "Apple Device"
            }
            if vendor == "Xiaomi" {
                return "Xiaomi Device"
            }
            return "\(vendor) Device"
        }

        let suffix = macAddress
            .split(separator: ":")
            .suffix(2)
            .joined()
            .uppercased()

        if suffix.isEmpty {
            return "Unknown Device"
        }

        return "Unknown Device \(suffix)"
    }
}
