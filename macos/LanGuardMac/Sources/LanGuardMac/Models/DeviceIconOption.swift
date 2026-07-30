import Foundation

struct DeviceIconOption: Identifiable, Hashable, Sendable {
    let id: String
    let title: String
    let systemImage: String
}

enum DeviceIconCatalog {
    static let fallback = "questionmark.circle"

    static let options: [DeviceIconOption] = [
        DeviceIconOption(id: fallback, title: "Unknown", systemImage: fallback),
        DeviceIconOption(id: "air.conditioner.horizontal", title: "Air Conditioner", systemImage: "air.conditioner.horizontal"),
        DeviceIconOption(id: "window.shade.closed", title: "Blinds", systemImage: "window.shade.closed"),
        DeviceIconOption(id: "lightbulb.max", title: "Bright Light", systemImage: "lightbulb.max"),
        DeviceIconOption(id: "camera", title: "Camera", systemImage: "camera"),
        DeviceIconOption(id: "fan.ceiling", title: "Ceiling Fan", systemImage: "fan.ceiling"),
        DeviceIconOption(id: "lamp.ceiling", title: "Ceiling Light", systemImage: "lamp.ceiling"),
        DeviceIconOption(id: "desktopcomputer", title: "Computer", systemImage: "desktopcomputer"),
        DeviceIconOption(id: "switch.2", title: "Controller", systemImage: "switch.2"),
        DeviceIconOption(id: "cpu", title: "Controller Board", systemImage: "cpu"),
        DeviceIconOption(id: "lamp.desk", title: "Desk Lamp", systemImage: "lamp.desk"),
        DeviceIconOption(id: "fan", title: "Fan", systemImage: "fan"),
        DeviceIconOption(id: "point.3.connected.trianglepath.dotted", title: "Hub", systemImage: "point.3.connected.trianglepath.dotted"),
        DeviceIconOption(id: "video.doorbell", title: "Intercom", systemImage: "video.doorbell"),
        DeviceIconOption(id: "macbook", title: "Laptop", systemImage: "macbook"),
        DeviceIconOption(id: "light.strip.2", title: "LED Strip", systemImage: "light.strip.2"),
        DeviceIconOption(id: "lightbulb", title: "Light", systemImage: "lightbulb"),
        DeviceIconOption(id: "light.panel", title: "Light Panel", systemImage: "light.panel"),
        DeviceIconOption(id: "light.recessed", title: "Recessed Light", systemImage: "light.recessed"),
        DeviceIconOption(id: "lightswitch.on", title: "Light Switch", systemImage: "lightswitch.on"),
        DeviceIconOption(id: "lock", title: "Lock", systemImage: "lock"),
        DeviceIconOption(id: "iphone", title: "Phone", systemImage: "iphone"),
        DeviceIconOption(id: "powerplug", title: "Plug", systemImage: "powerplug"),
        DeviceIconOption(id: "printer", title: "Printer", systemImage: "printer"),
        DeviceIconOption(id: "robotic.vacuum", title: "Robot Vacuum", systemImage: "robotic.vacuum"),
        DeviceIconOption(id: "wifi.router", title: "Router", systemImage: "wifi.router"),
        DeviceIconOption(id: "sensor.tag.radiowaves.forward", title: "Sensor Hub", systemImage: "sensor.tag.radiowaves.forward"),
        DeviceIconOption(id: "server.rack", title: "Server", systemImage: "server.rack"),
        DeviceIconOption(id: "blinds.horizontal.closed", title: "Shutter", systemImage: "blinds.horizontal.closed"),
        DeviceIconOption(id: "poweroutlet.type.h", title: "Smart Outlet", systemImage: "poweroutlet.type.h"),
        DeviceIconOption(id: "poweroutlet.strip", title: "Smart Power Strip", systemImage: "poweroutlet.strip"),
        DeviceIconOption(id: "homepod", title: "Smart Speaker", systemImage: "homepod"),
        DeviceIconOption(id: "hifispeaker", title: "Speaker", systemImage: "hifispeaker"),
        DeviceIconOption(id: "airplayvideo", title: "Streamer", systemImage: "airplayvideo"),
        DeviceIconOption(id: "ipad", title: "Tablet", systemImage: "ipad"),
        DeviceIconOption(id: "thermometer.medium", title: "Thermostat", systemImage: "thermometer.medium"),
        DeviceIconOption(id: "tv", title: "TV", systemImage: "tv"),
        DeviceIconOption(id: "applewatch", title: "Watch", systemImage: "applewatch"),
    ]
}

extension NetworkDevice {
    var displayIconName: String {
        if let iconName, !iconName.isEmpty {
            return iconName
        }

        if isGateway {
            return "wifi.router"
        }

        let roleIconName = effectiveRole.iconName
        if roleIconName != DeviceIconCatalog.fallback {
            return roleIconName
        }

        return DeviceIconCatalog.fallback
    }

    var displayIconNames: [String] {
        let primaryIcon = displayIconName
        let secondaryIcon = secondaryIconName?.trimmingCharacters(in: .whitespacesAndNewlines)

        guard let secondaryIcon, !secondaryIcon.isEmpty, secondaryIcon != primaryIcon else {
            return [primaryIcon]
        }

        return [primaryIcon, secondaryIcon]
    }
}
