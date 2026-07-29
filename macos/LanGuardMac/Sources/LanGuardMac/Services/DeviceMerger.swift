import Foundation

struct DeviceMergeResult: Equatable, Sendable {
    var devices: [NetworkDevice]
    var newDevices: [NetworkDevice]
    var riskyDevices: [NetworkDevice]
    var changes: [DeviceChange]
}

enum DeviceMerger {
    static func merge(existing: [NetworkDevice], discovered: [NetworkDevice]) -> DeviceMergeResult {
        let existingByID = Dictionary(uniqueKeysWithValues: existing.map { ($0.id, $0) })
        var newDevices: [NetworkDevice] = []
        var riskyDevices: [NetworkDevice] = []
        var changes: [DeviceChange] = []

        let mergedDevices = discovered.map { device in
            guard let previous = existingByID[device.id] else {
                newDevices.append(device)
                if !device.isKnown, device.risk == .high {
                    riskyDevices.append(device)
                }
                return device
            }

            var merged = device
            if previous.isKnown {
                merged.name = previous.name
                merged.iconName = previous.iconName
            } else {
                merged.name = device.name
                merged.iconName = device.iconName
            }
            merged.vendor = device.vendor ?? previous.vendor
            merged.isKnown = previous.isKnown
            merged.firstSeen = previous.firstSeen
            merged.risk = DeviceRiskScorer.risk(for: merged.openPorts, isKnown: merged.isKnown)

            if previous.ipAddress != merged.ipAddress {
                changes.append(DeviceChange(deviceID: merged.id, deviceName: merged.name, ipAddress: merged.ipAddress, kind: .ipAddress))
            }
            if previous.openPorts != merged.openPorts {
                changes.append(DeviceChange(deviceID: merged.id, deviceName: merged.name, ipAddress: merged.ipAddress, kind: .ports))
            }
            if previous.risk != merged.risk {
                changes.append(DeviceChange(deviceID: merged.id, deviceName: merged.name, ipAddress: merged.ipAddress, kind: .risk))
            }

            if !merged.isKnown, previous.risk != .high, merged.risk == .high {
                riskyDevices.append(merged)
            }
            return merged
        }

        return DeviceMergeResult(devices: mergedDevices, newDevices: newDevices, riskyDevices: riskyDevices, changes: changes)
    }
}
