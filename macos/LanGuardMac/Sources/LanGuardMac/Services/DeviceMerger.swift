import Foundation

struct DeviceMergeResult: Equatable, Sendable {
    var devices: [NetworkDevice]
    var newDevices: [NetworkDevice]
    var riskyDevices: [NetworkDevice]
    var changes: [DeviceChange]
}

enum DeviceMerger {
    private static let offlineAfterMissedScans = 3

    static func merge(existing: [NetworkDevice], discovered: [NetworkDevice]) -> DeviceMergeResult {
        let normalizedExisting = coalescedDevices(existing)
        let normalizedDiscovered = coalescedDevices(discovered)
        let existingByID = Dictionary(uniqueKeysWithValues: normalizedExisting.map { ($0.id, $0) })
        let discoveredIDs = Set(normalizedDiscovered.map(\.id))
        var newDevices: [NetworkDevice] = []
        var riskyDevices: [NetworkDevice] = []
        var changes: [DeviceChange] = []

        var mergedDevices = normalizedDiscovered.map { device in
            guard let previous = existingByID[device.id] else {
                var newDevice = device
                newDevice.status = .online
                newDevice.missedScans = 0
                newDevice.risk = DeviceRiskScorer.risk(
                    for: newDevice.openPorts,
                    isKnown: newDevice.isKnown,
                    role: newDevice.role ?? .device
                )
                newDevices.append(newDevice)
                if !newDevice.isKnown, newDevice.risk == .high {
                    riskyDevices.append(newDevice)
                }
                return newDevice
            }

            var merged = device
            if previous.isKnown {
                merged.name = previous.name
                merged.iconName = previous.iconName
                merged.secondaryIconName = previous.secondaryIconName
            } else {
                merged.name = device.name
                merged.iconName = device.iconName
                merged.secondaryIconName = device.secondaryIconName
            }
            merged.hostname = HostnameResolver.clean(device.hostname)
            merged.hostnameSource = merged.hostname == nil ? nil : device.hostnameSource
            merged.vendor = MACVendorResolver.displayVendor(device.vendor)
            merged.vendorSource = merged.vendor == nil ? nil : device.vendorSource
            merged.comments = previous.comments
            merged.externalURL = previous.externalURL
            merged.attentionAcknowledgedRiskSignature = previous.attentionAcknowledgedRiskSignature
            merged.role = previous.role
            merged.room = previous.room
            merged.isKnown = previous.isKnown
            merged.firstSeen = previous.firstSeen
            merged.status = .online
            merged.missedScans = 0
            merged.risk = DeviceRiskScorer.risk(
                for: merged.openPorts,
                isKnown: merged.isKnown,
                role: merged.role ?? .device
            )

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

        for previous in normalizedExisting where !discoveredIDs.contains(previous.id) {
            var missingDevice = previous
            missingDevice.missedScans += 1
            missingDevice.status = missingDevice.missedScans >= offlineAfterMissedScans ? .offline : .recentlySeen
            mergedDevices.append(missingDevice)
        }

        let sortedDevices = mergedDevices.sorted {
            IPv4AddressSortKey($0.ipAddress) < IPv4AddressSortKey($1.ipAddress)
        }

        return DeviceMergeResult(devices: sortedDevices, newDevices: newDevices, riskyDevices: riskyDevices, changes: changes)
    }

    private static func coalescedDevices(_ devices: [NetworkDevice]) -> [NetworkDevice] {
        var devicesByID: [String: NetworkDevice] = [:]

        for device in devices {
            guard var current = devicesByID[device.id] else {
                devicesByID[device.id] = device
                continue
            }

            let latest = device.lastSeen >= current.lastSeen ? device : current
            current.name = latest.name
            current.ipAddress = latest.ipAddress
            current.macAddress = latest.macAddress
            current.vendor = latest.vendor ?? current.vendor
            if latest.vendor != nil { current.vendorSource = latest.vendorSource }
            current.hostname = preferredHostname(latest.hostname, fallback: current.hostname)
            if latest.hostname != nil { current.hostnameSource = latest.hostnameSource }
            current.comments = latest.comments.isEmpty ? current.comments : latest.comments
            current.externalURL = latest.externalURL ?? current.externalURL
            current.attentionAcknowledgedRiskSignature = (
                latest.attentionAcknowledgedRiskSignature
                    ?? current.attentionAcknowledgedRiskSignature
            )
            current.iconName = latest.iconName ?? current.iconName
            current.secondaryIconName = latest.secondaryIconName ?? current.secondaryIconName
            current.status = latest.status
            current.risk = latest.risk
            current.role = current.role ?? latest.role
            current.room = current.room ?? latest.room
            current.isKnown = current.isKnown || latest.isKnown
            current.isGateway = current.isGateway || latest.isGateway
            current.openPorts = Array(Set(current.openPorts).union(latest.openPorts)).sorted()
            current.missedScans = min(current.missedScans, latest.missedScans)
            current.firstSeen = min(current.firstSeen, latest.firstSeen)
            current.lastSeen = max(current.lastSeen, latest.lastSeen)

            devicesByID[device.id] = current
        }

        return Array(devicesByID.values)
    }

    private static func preferredHostname(_ candidate: String?, fallback: String?) -> String? {
        if let cleanedCandidate = HostnameResolver.clean(candidate) {
            return cleanedCandidate
        }
        return HostnameResolver.clean(fallback)
    }
}

private struct IPv4AddressSortKey: Comparable {
    private let parts: [Int]
    private let rawValue: String

    init(_ rawValue: String) {
        self.rawValue = rawValue
        self.parts = rawValue.split(separator: ".").map { Int($0) ?? 0 }
    }

    static func < (lhs: IPv4AddressSortKey, rhs: IPv4AddressSortKey) -> Bool {
        guard lhs.parts.count == 4, rhs.parts.count == 4 else {
            return lhs.rawValue < rhs.rawValue
        }

        return lhs.parts.lexicographicallyPrecedes(rhs.parts)
    }
}
