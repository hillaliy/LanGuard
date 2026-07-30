import Foundation

enum DeviceProfiler {
    static func enrich(_ device: NetworkDevice) -> NetworkDevice {
        let resolvedVendor = MACVendorResolver.vendor(for: device.macAddress)
        let vendor = resolvedVendor ?? (MACVendorResolver.isLocallyAdministered(device.macAddress) ? nil : device.vendor)
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

        if profileText.contains("deco") || profileText.contains("mesh") {
            return .meshRouter
        }

        if profileText.contains("router")
            || profileText.contains("gateway")
            || profileText.contains("access point")
            || profileText.contains("wifi ap")
            || profileText.contains("wireless ap")
            || profileText.contains("ubiquiti")
            || profileText.contains("unifi") {
            return .router
        }

        if profileText.contains("hub")
            || profileText.contains("bridge")
            || profileText.contains("aqara")
            || profileText.contains("lumi gateway")
            || profileText.contains("hue bridge")
            || profileText.contains("smartthings") {
            return .hub
        }

        if openPorts.contains(554) || profileText.contains("camera") || profileText.contains("nvr") {
            return .camera
        }

        if openPorts.contains(9100) || profileText.contains("printer") {
            return .printer
        }

        if profileText.contains("server")
            || profileText.contains("raspberry pi")
            || profileText.contains("nas") {
            return .server
        }

        if profileText.contains("macbook")
            || profileText.contains("imac")
            || profileText.contains("desktop")
            || profileText.contains("computer")
            || profileText.contains("pc") {
            return .computer
        }

        if profileText.contains("iphone") || profileText.contains("phone") {
            return .phone
        }

        if profileText.contains("ipad") || profileText.contains("tablet") {
            return .tablet
        }

        if profileText.contains("watch") {
            return .watch
        }

        if profileText.contains("apple tv") || profileText.contains("tv") || profileText.contains("television") {
            return .tv
        }

        if profileText.contains("streamer")
            || profileText.contains("chromecast")
            || profileText.contains("fire tv")
            || profileText.contains("airplay") {
            return .streamer
        }

        if profileText.contains("homepod")
            || profileText.contains("speaker")
            || profileText.contains("sonos")
            || profileText.contains("echo")
            || profileText.contains("alexa")
            || profileText.contains("google home") {
            return .speaker
        }

        if profileText.contains("thermostat")
            || profileText.contains("temperature")
            || profileText.contains("air conditioner")
            || profileText.contains("air-conditioning")
            || profileText.contains("aircon")
            || profileText.contains("midea")
            || profileText.contains("gree")
            || profileText.contains("daikin") {
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
            || profileText.contains("relay")
            || profileText.contains("shelly")
            || profileText.contains("switchbot") {
            return .controller
        }

        if profileText.contains("vacuum")
            || profileText.contains("roborock")
            || profileText.contains("roomba")
            || profileText.contains("irobot")
            || profileText.contains("dreame")
            || profileText.contains("ecovacs") {
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

        if profileText.contains("homepod")
            || profileText.contains("smart speaker")
            || profileText.contains("speaker")
            || profileText.contains("sonos")
            || profileText.contains("echo")
            || profileText.contains("alexa")
            || profileText.contains("nest audio")
            || profileText.contains("google home") {
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
            || profileText.contains("roborock")
            || profileText.contains("roomba")
            || profileText.contains("irobot")
            || profileText.contains("dreame")
            || profileText.contains("ecovacs")
            || profileText.contains("deebot")
            || profileText.contains("robovac") {
            return "robotic.vacuum"
        }

        if profileText.contains("hub")
            || profileText.contains("bridge")
            || profileText.contains("aqara hub")
            || profileText.contains("lumi gateway")
            || profileText.contains("hue bridge")
            || profileText.contains("smartthings") {
            return "point.3.connected.trianglepath.dotted"
        }

        if profileText.contains("controller")
            || profileText.contains("control")
            || profileText.contains("relay")
            || profileText.contains("shelly")
            || profileText.contains("switchbot") {
            return "switch.2"
        }

        if profileText.contains("thermostat") || profileText.contains("temperature") || profileText.contains("ecobee") {
            return "thermometer.medium"
        }

        if profileText.contains("air conditioner")
            || profileText.contains("air-conditioning")
            || profileText.contains("aircon")
            || profileText.contains("midea")
            || profileText.contains("gree")
            || profileText.contains("daikin") {
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
