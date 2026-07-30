import Foundation

enum DeviceRole: String, Codable, CaseIterable, Identifiable, Sendable {
    case device
    case gateway
    case router
    case meshRouter
    case hub
    case camera
    case computer
    case server
    case phone
    case tablet
    case tv
    case streamer
    case printer
    case speaker
    case light
    case climate
    case smartPlug
    case controller
    case lock
    case intercom
    case sensor
    case robotVacuum
    case watch
    case unknown

    var id: String { rawValue }

    static var alphabeticalCases: [DeviceRole] {
        allCases.sorted { $0.title.localizedStandardCompare($1.title) == .orderedAscending }
    }

    var title: String {
        switch self {
        case .device:
            "Device"
        case .gateway:
            "Gateway"
        case .router:
            "Router"
        case .meshRouter:
            "Mesh Router"
        case .hub:
            "Hub"
        case .camera:
            "Camera"
        case .computer:
            "Computer"
        case .server:
            "Server"
        case .phone:
            "Phone"
        case .tablet:
            "Tablet"
        case .tv:
            "TV"
        case .streamer:
            "Streamer"
        case .printer:
            "Printer"
        case .speaker:
            "Speaker"
        case .light:
            "Light"
        case .climate:
            "Climate"
        case .smartPlug:
            "Smart Plug"
        case .controller:
            "Controller"
        case .lock:
            "Lock"
        case .intercom:
            "Intercom"
        case .sensor:
            "Sensor"
        case .robotVacuum:
            "Robot Vacuum"
        case .watch:
            "Watch"
        case .unknown:
            "Unknown"
        }
    }

    var iconName: String {
        switch self {
        case .gateway, .router, .meshRouter:
            "wifi.router"
        case .hub:
            "point.3.connected.trianglepath.dotted"
        case .camera:
            "camera"
        case .computer:
            "desktopcomputer"
        case .server:
            "server.rack"
        case .phone:
            "iphone"
        case .tablet:
            "ipad"
        case .tv:
            "tv"
        case .streamer:
            "airplayvideo"
        case .printer:
            "printer"
        case .speaker:
            "homepod"
        case .light:
            "lightbulb"
        case .climate:
            "air.conditioner.horizontal"
        case .smartPlug:
            "poweroutlet.type.h"
        case .controller:
            "switch.2"
        case .lock:
            "lock"
        case .intercom:
            "video.doorbell"
        case .sensor:
            "sensor.tag.radiowaves.forward"
        case .robotVacuum:
            "robotic.vacuum"
        case .watch:
            "applewatch"
        case .device:
            "desktopcomputer"
        case .unknown:
            DeviceIconCatalog.fallback
        }
    }
}

extension NetworkDevice {
    var detectedRole: DeviceRole {
        DeviceProfiler.role(
            name: name,
            hostname: hostname,
            vendor: vendor,
            openPorts: openPorts,
            isGateway: isGateway
        )
    }

    var effectiveRole: DeviceRole {
        role ?? detectedRole
    }
}
