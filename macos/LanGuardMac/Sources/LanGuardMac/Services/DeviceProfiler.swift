import Foundation

enum DeviceProfiler {
    static func enrich(_ device: NetworkDevice) -> NetworkDevice {
        let resolvedVendor = MACVendorResolver.preferredVendor(
            macAddress: device.macAddress,
            observedVendor: device.vendor
        )
        let vendor = resolvedVendor ?? inferredVendor(name: device.name, hostname: device.hostname)
        let iconName = device.iconName ?? iconName(
            name: device.name,
            hostname: device.hostname,
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

    private static func inferredVendor(name: String?, hostname: String?) -> String? {
        let profileText = [name, hostname]
            .compactMap { $0?.lowercased() }
            .joined(separator: " ")
            .replacingOccurrences(of: "-", with: " ")
            .replacingOccurrences(of: "_", with: " ")

        let appleSignals = [
            "homepod",
            "apple watch",
            "apple tv",
            "iphone",
            "ipad",
            "imac",
            "macbook",
            "mac mini",
            "mac studio",
            "airpods",
        ]

        return appleSignals.contains(where: { profileText.contains($0) }) ? "Apple, Inc." : nil
    }

    static func iconName(vendor: String?, openPorts: [Int], isGateway: Bool) -> String {
        iconName(name: nil, hostname: nil, vendor: vendor, openPorts: openPorts, isGateway: isGateway)
    }

    static func role(
        name: String?,
        hostname: String?,
        vendor: String?,
        openPorts: [Int],
        isGateway: Bool
    ) -> DeviceRole {
        if isGateway {
            return .gateway
        }

        let profileText = [name, hostname, vendor]
            .compactMap { $0?.lowercased() }
            .joined(separator: " ")

        if profileText.contains("mesh") {
            return .meshRouter
        }

        if profileText.contains("router")
            || profileText.contains("gateway")
            || profileText.contains("access point")
            || profileText.contains("wifi ap")
            || profileText.contains("wireless ap") {
            return .router
        }

        if profileText.contains("hub")
            || profileText.contains("bridge") {
            return .hub
        }

        if openPorts.contains(554) || profileText.contains("camera") || profileText.contains("nvr") {
            return .camera
        }

        if openPorts.contains(9100) || profileText.contains("printer") {
            return .printer
        }

        if profileText.contains("server")
            || profileText.contains("nas") {
            return .server
        }

        if profileText.contains("desktop")
            || profileText.contains("computer")
            || profileText.contains("pc") {
            return .computer
        }

        if profileText.contains("phone") {
            return .phone
        }

        if profileText.contains("tablet") {
            return .tablet
        }

        if profileText.contains("watch") {
            return .watch
        }

        if profileText.contains("tv") || profileText.contains("television") {
            return .tv
        }

        if profileText.contains("streamer")
            || profileText.contains("streaming") {
            return .streamer
        }

        if profileText.contains("speaker")
            || profileText.contains("homepod")
            || profileText.contains("audio") {
            return .speaker
        }

        if profileText.contains("thermostat")
            || profileText.contains("temperature")
            || profileText.contains("air conditioner")
            || profileText.contains("air-conditioning")
            || profileText.contains("aircon")
            || profileText.contains("hvac") {
            return .climate
        }

        if profileText.contains("intercom") || profileText.contains("doorbell") {
            return .intercom
        }

        if profileText.contains("lock") {
            return .lock
        }

        if profileText.contains("sensor") {
            return .sensor
        }

        if profileText.contains("power strip")
            || profileText.contains("power outlet")
            || profileText.contains("smart outlet")
            || profileText.contains("smart socket")
            || profileText.contains("socket")
            || profileText.contains("plug") {
            return .smartPlug
        }

        if profileText.contains("controller")
            || profileText.contains("control")
            || profileText.contains("relay") {
            return .controller
        }

        if profileText.contains("vacuum")
            || profileText.contains("robotic cleaner") {
            return .robotVacuum
        }

        if profileText.contains("light")
            || profileText.contains("lamp")
            || profileText.contains("led")
            || profileText.contains("strip") {
            return .light
        }

        if profileText.contains("unknown") {
            return .unknown
        }

        return .device
    }

    static func iconName(
        name: String?,
        hostname: String?,
        vendor: String?,
        openPorts: [Int],
        isGateway: Bool
    ) -> String {
        if isGateway {
            return "wifi.router"
        }

        let profileText = [name, hostname, vendor]
            .compactMap { $0?.lowercased() }
            .joined(separator: " ")

        if profileText.contains("smart speaker")
            || profileText.contains("homepod")
            || profileText.contains("speaker")
            || profileText.contains("audio") {
            return "homepod"
        }

        if profileText.contains("power strip")
            || profileText.contains("powerstrip")
            || profileText.contains("power outlet")
            || profileText.contains("smart outlet")
            || profileText.contains("smart socket")
            || profileText.contains("multi plug")
            || profileText.contains("socket") {
            return "poweroutlet.strip"
        }

        if profileText.contains("robot vacuum")
            || profileText.contains("robotic vacuum")
            || profileText.contains("vacuum")
            || profileText.contains("robotic cleaner") {
            return "robotic.vacuum"
        }

        if profileText.contains("hub")
            || profileText.contains("bridge") {
            return "point.3.connected.trianglepath.dotted"
        }

        if profileText.contains("controller")
            || profileText.contains("control")
            || profileText.contains("relay") {
            return "switch.2"
        }

        if profileText.contains("thermostat") || profileText.contains("temperature") {
            return "thermometer.medium"
        }

        if profileText.contains("air conditioner")
            || profileText.contains("air-conditioning")
            || profileText.contains("aircon")
            || profileText.contains("hvac") {
            return "air.conditioner.horizontal"
        }

        if profileText.contains("intercom") || profileText.contains("doorbell") {
            return "video.doorbell"
        }

        if profileText.contains("shutter")
            || profileText.contains("blind")
            || profileText.contains("curtain")
            || profileText.contains("cover") {
            return "blinds.horizontal.closed"
        }

        if profileText.contains("desk lamp") {
            return "lamp.desk"
        }

        if profileText.contains("ceiling light") {
            return "lamp.ceiling"
        }

        if profileText.contains("led strip") || profileText.contains("light strip") || profileText.contains("strip light") {
            return "light.strip.2"
        }

        if profileText.contains("led") || profileText.contains("strip") {
            return "light.strip.2"
        }

        if profileText.contains("panel") {
            return "light.panel"
        }

        if profileText.contains("light") || profileText.contains("lamp") {
            return "lightbulb"
        }

        if openPorts.contains(9100) {
            return "printer"
        }

        if openPorts.contains(554) {
            return "camera"
        }

        return DeviceIconCatalog.fallback
    }
}
