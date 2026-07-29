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
        DeviceIconOption(id: "desktopcomputer", title: "Computer", systemImage: "desktopcomputer"),
        DeviceIconOption(id: "macbook", title: "Laptop", systemImage: "macbook"),
        DeviceIconOption(id: "iphone", title: "Phone", systemImage: "iphone"),
        DeviceIconOption(id: "ipad", title: "Tablet", systemImage: "ipad"),
        DeviceIconOption(id: "applewatch", title: "Watch", systemImage: "applewatch"),
        DeviceIconOption(id: "wifi.router", title: "Router", systemImage: "wifi.router"),
        DeviceIconOption(id: "server.rack", title: "Server", systemImage: "server.rack"),
        DeviceIconOption(id: "tv", title: "TV", systemImage: "tv"),
        DeviceIconOption(id: "airplayvideo", title: "Streamer", systemImage: "airplayvideo"),
        DeviceIconOption(id: "camera", title: "Camera", systemImage: "camera"),
        DeviceIconOption(id: "printer", title: "Printer", systemImage: "printer"),
        DeviceIconOption(id: "lightbulb", title: "Light", systemImage: "lightbulb"),
        DeviceIconOption(id: "lock", title: "Lock", systemImage: "lock"),
        DeviceIconOption(id: "fan", title: "Fan", systemImage: "fan"),
        DeviceIconOption(id: "powerplug", title: "Plug", systemImage: "powerplug"),
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

        return DeviceIconCatalog.fallback
    }
}
