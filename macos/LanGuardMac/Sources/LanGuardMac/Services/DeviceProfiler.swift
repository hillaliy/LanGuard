import Foundation

enum DeviceProfiler {
    static func enrich(_ device: NetworkDevice) -> NetworkDevice {
        let vendor = device.vendor ?? MACVendorResolver.vendor(for: device.macAddress)
        let iconName = device.iconName ?? iconName(
            vendor: vendor,
            openPorts: device.openPorts,
            isGateway: device.isGateway
        )
        let name = DeviceNameGuesser.displayName(
            hostname: device.hostname,
            macAddress: device.macAddress,
            vendor: vendor,
            openPorts: device.openPorts,
            isGateway: device.isGateway
        )

        var enriched = device
        enriched.vendor = vendor
        enriched.iconName = iconName
        enriched.name = name
        return enriched
    }

    static func iconName(vendor: String?, openPorts: [Int], isGateway: Bool) -> String {
        if isGateway {
            return "wifi.router"
        }

        if openPorts.contains(9100) {
            return "printer"
        }

        if openPorts.contains(554) {
            return "camera"
        }

        switch vendor {
        case "Apple":
            return "apple.logo"
        case "Google", "Amazon", "Hon Hai":
            return "display"
        case "TP-Link", "Ubiquiti":
            return "wifi.router"
        case "Espressif", "Xiaomi", "Aqara", "Lumi":
            return "lightbulb"
        case "Raspberry Pi":
            return "server.rack"
        default:
            return DeviceIconCatalog.fallback
        }
    }
}
