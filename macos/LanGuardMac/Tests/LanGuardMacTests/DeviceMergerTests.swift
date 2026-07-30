import Foundation
import Testing
@testable import LanGuardMac

@Test
func deviceMergerReportsOnlyNewDevices() {
    let existing = NetworkDevice(
        id: "90:dd:5d:b7:bd:01",
        name: "Living Room TV",
        ipAddress: "192.168.0.51",
        macAddress: "90:dd:5d:b7:bd:01",
        status: .online,
        risk: .low,
        isKnown: true,
        openPorts: [80],
        firstSeen: Date(timeIntervalSince1970: 100)
    )
    let rediscovered = NetworkDevice(
        id: "90:dd:5d:b7:bd:01",
        name: "Unknown Device BD01",
        ipAddress: "192.168.0.52",
        macAddress: "90:dd:5d:b7:bd:01",
        status: .online,
        risk: .medium,
        openPorts: [80],
        firstSeen: Date(timeIntervalSince1970: 200)
    )
    let newDevice = NetworkDevice(
        id: "24:a1:60:0a:9c:d6",
        name: "Unknown Device 9CD6",
        ipAddress: "192.168.0.122",
        macAddress: "24:a1:60:0a:9c:d6",
        status: .online,
        firstSeen: Date(timeIntervalSince1970: 200)
    )

    let result = DeviceMerger.merge(existing: [existing], discovered: [rediscovered, newDevice])

    #expect(result.newDevices == [newDevice])
    #expect(result.devices.count == 2)
    #expect(result.devices.first?.name == "Living Room TV")
    #expect(result.devices.first?.isKnown == true)
    #expect(result.devices.first?.risk == .low)
    #expect(result.devices.first?.firstSeen == Date(timeIntervalSince1970: 100))
    #expect(result.changes.map(\.kind) == [.ipAddress])
}

@Test
func deviceMergerReportsAllDevicesAsNewWhenNoExistingState() {
    let discovered = [
        NetworkDevice(
            id: "90:dd:5d:b7:bd:01",
            name: "Apple TV",
            ipAddress: "192.168.0.51",
            macAddress: "90:dd:5d:b7:bd:01"
        )
    ]

    let result = DeviceMerger.merge(existing: [], discovered: discovered)

    #expect(result.devices.count == 1)
    #expect(result.devices.first?.id == discovered.first?.id)
    #expect(result.devices.first?.status == .online)
    #expect(result.newDevices.count == 1)
    #expect(result.newDevices.first?.id == discovered.first?.id)
    #expect(result.newDevices.first?.status == .online)
}

@Test
func deviceMergerCoalescesDuplicateDiscoveredDevices() {
    let firstObservation = NetworkDevice(
        id: "90:dd:5d:b7:bd:01",
        name: "Apple Device",
        ipAddress: "192.168.0.51",
        macAddress: "90:dd:5d:b7:bd:01",
        openPorts: [80],
        firstSeen: Date(timeIntervalSince1970: 100),
        lastSeen: Date(timeIntervalSince1970: 100)
    )
    let secondObservation = NetworkDevice(
        id: "90:dd:5d:b7:bd:01",
        name: "Living Room TV",
        ipAddress: "192.168.0.52",
        macAddress: "90:dd:5d:b7:bd:01",
        vendor: "Apple",
        openPorts: [443],
        firstSeen: Date(timeIntervalSince1970: 120),
        lastSeen: Date(timeIntervalSince1970: 120)
    )

    let result = DeviceMerger.merge(existing: [], discovered: [firstObservation, secondObservation])

    #expect(result.devices.count == 1)
    #expect(result.newDevices.count == 1)
    #expect(result.devices.first?.name == "Living Room TV")
    #expect(result.devices.first?.ipAddress == "192.168.0.52")
    #expect(result.devices.first?.vendor == "Apple")
    #expect(result.devices.first?.openPorts == [80, 443])
}

@Test
func deviceMergerCoalescesDuplicateExistingDevices() {
    let olderExisting = NetworkDevice(
        id: "90:dd:5d:b7:bd:01",
        name: "Apple Device",
        ipAddress: "192.168.0.51",
        macAddress: "90:dd:5d:b7:bd:01",
        status: .online,
        openPorts: [80],
        firstSeen: Date(timeIntervalSince1970: 100),
        lastSeen: Date(timeIntervalSince1970: 100)
    )
    let newerExisting = NetworkDevice(
        id: "90:dd:5d:b7:bd:01",
        name: "Living Room TV",
        ipAddress: "192.168.0.52",
        macAddress: "90:dd:5d:b7:bd:01",
        status: .online,
        isKnown: true,
        openPorts: [443],
        firstSeen: Date(timeIntervalSince1970: 120),
        lastSeen: Date(timeIntervalSince1970: 120)
    )

    let result = DeviceMerger.merge(existing: [olderExisting, newerExisting], discovered: [])

    #expect(result.devices.count == 1)
    #expect(result.devices.first?.name == "Living Room TV")
    #expect(result.devices.first?.isKnown == true)
    #expect(result.devices.first?.openPorts == [80, 443])
}

@Test
func deviceMergerPreservesCustomIcon() {
    let existing = NetworkDevice(
        id: "90:dd:5d:b7:bd:01",
        name: "Living Room TV",
        ipAddress: "192.168.0.51",
        macAddress: "90:dd:5d:b7:bd:01",
        iconName: "tv",
        secondaryIconName: "airplayvideo",
        isKnown: true
    )
    let discovered = NetworkDevice(
        id: "90:dd:5d:b7:bd:01",
        name: "Unknown Device BD01",
        ipAddress: "192.168.0.51",
        macAddress: "90:dd:5d:b7:bd:01"
    )

    let result = DeviceMerger.merge(existing: [existing], discovered: [discovered])

    #expect(result.devices.first?.iconName == "tv")
    #expect(result.devices.first?.secondaryIconName == "airplayvideo")
}

@Test
func deviceMergerPreservesManualRole() {
    let existing = NetworkDevice(
        id: "90:dd:5d:b7:bd:01",
        name: "Living Room Mesh Node",
        ipAddress: "192.168.0.51",
        macAddress: "90:dd:5d:b7:bd:01",
        role: .meshRouter,
        isKnown: true
    )
    let discovered = NetworkDevice(
        id: "90:dd:5d:b7:bd:01",
        name: "Apple Device",
        ipAddress: "192.168.0.51",
        macAddress: "90:dd:5d:b7:bd:01",
        vendor: "Apple"
    )

    let result = DeviceMerger.merge(existing: [existing], discovered: [discovered])

    #expect(result.devices.first?.role == .meshRouter)
    #expect(result.devices.first?.effectiveRole == .meshRouter)
}

@Test
func deviceMergerRefreshesNameAndIconUntilDeviceIsKnown() {
    let existing = NetworkDevice(
        id: "90:dd:5d:b7:bd:01",
        name: "Unknown Device BD01",
        ipAddress: "192.168.0.51",
        macAddress: "90:dd:5d:b7:bd:01",
        iconName: "questionmark.circle",
        isKnown: false
    )
    let discovered = NetworkDevice(
        id: "90:dd:5d:b7:bd:01",
        name: "Apple Camera",
        ipAddress: "192.168.0.51",
        macAddress: "90:dd:5d:b7:bd:01",
        vendor: "Apple",
        iconName: "camera",
        openPorts: [554]
    )

    let result = DeviceMerger.merge(existing: [existing], discovered: [discovered])

    #expect(result.devices.first?.name == "Apple Camera")
    #expect(result.devices.first?.iconName == "camera")
    #expect(result.devices.first?.vendor == "Apple")
}

@Test
func deviceMergerClearsStaleVendorForLocallyAdministeredMacAddress() {
    let existing = NetworkDevice(
        id: "ba:e6:e0:17:66:94",
        name: "Apple Device",
        ipAddress: "192.168.0.54",
        macAddress: "ba:e6:e0:17:66:94",
        vendor: "Apple"
    )
    let discovered = NetworkDevice(
        id: "ba:e6:e0:17:66:94",
        name: "Unknown Device 6694",
        ipAddress: "192.168.0.54",
        macAddress: "ba:e6:e0:17:66:94"
    )

    let result = DeviceMerger.merge(existing: [existing], discovered: [discovered])

    #expect(result.devices.first?.vendor == nil)
    #expect(result.devices.first?.name == "Unknown Device 6694")
}

@Test
func deviceMergerReportsPortChanges() {
    let existing = NetworkDevice(
        id: "24:a1:60:0a:9c:d6",
        name: "Camera",
        ipAddress: "192.168.0.122",
        macAddress: "24:a1:60:0a:9c:d6",
        risk: .medium,
        openPorts: [80]
    )
    let discovered = NetworkDevice(
        id: "24:a1:60:0a:9c:d6",
        name: "Camera",
        ipAddress: "192.168.0.122",
        macAddress: "24:a1:60:0a:9c:d6",
        openPorts: [80, 554]
    )

    let result = DeviceMerger.merge(existing: [existing], discovered: [discovered])

    #expect(result.changes.map(\.kind) == [.ports])
}

@Test
func deviceMergerReportsUnknownDevicesThatBecomeHighRisk() {
    let existing = NetworkDevice(
        id: "24:a1:60:0a:9c:d6",
        name: "Unknown Device 9CD6",
        ipAddress: "192.168.0.122",
        macAddress: "24:a1:60:0a:9c:d6",
        risk: .low,
        isKnown: false
    )
    let discovered = NetworkDevice(
        id: "24:a1:60:0a:9c:d6",
        name: "Unknown Device 9CD6",
        ipAddress: "192.168.0.122",
        macAddress: "24:a1:60:0a:9c:d6",
        openPorts: [5900]
    )

    let result = DeviceMerger.merge(existing: [existing], discovered: [discovered])

    #expect(result.riskyDevices.count == 1)
    #expect(result.riskyDevices.first?.risk == .high)
}

@Test
func deviceMergerDoesNotReportKnownHighRiskDevices() {
    let existing = NetworkDevice(
        id: "24:a1:60:0a:9c:d6",
        name: "Known Device",
        ipAddress: "192.168.0.122",
        macAddress: "24:a1:60:0a:9c:d6",
        risk: .low,
        isKnown: true
    )
    let discovered = NetworkDevice(
        id: "24:a1:60:0a:9c:d6",
        name: "Known Device",
        ipAddress: "192.168.0.122",
        macAddress: "24:a1:60:0a:9c:d6",
        openPorts: [5900]
    )

    let result = DeviceMerger.merge(existing: [existing], discovered: [discovered])

    #expect(result.riskyDevices.isEmpty)
}

@Test
func deviceMergerKeepsMissingDevicesInRecentlySeenGracePeriod() {
    let existing = NetworkDevice(
        id: "90:dd:5d:b7:bd:01",
        name: "Living Room TV",
        ipAddress: "192.168.0.51",
        macAddress: "90:dd:5d:b7:bd:01",
        status: .online,
        missedScans: 0
    )

    let result = DeviceMerger.merge(existing: [existing], discovered: [])

    #expect(result.devices.count == 1)
    #expect(result.devices.first?.status == .recentlySeen)
    #expect(result.devices.first?.missedScans == 1)
}

@Test
func deviceMergerMarksMissingDeviceOfflineAfterGraceLimit() {
    let existing = NetworkDevice(
        id: "90:dd:5d:b7:bd:01",
        name: "Living Room TV",
        ipAddress: "192.168.0.51",
        macAddress: "90:dd:5d:b7:bd:01",
        status: .recentlySeen,
        missedScans: 2
    )

    let result = DeviceMerger.merge(existing: [existing], discovered: [])

    #expect(result.devices.count == 1)
    #expect(result.devices.first?.status == .offline)
    #expect(result.devices.first?.missedScans == 3)
}

@Test
func deviceMergerResetsMissedScansWhenDeviceReturns() {
    let existing = NetworkDevice(
        id: "90:dd:5d:b7:bd:01",
        name: "Living Room TV",
        ipAddress: "192.168.0.51",
        macAddress: "90:dd:5d:b7:bd:01",
        status: .recentlySeen,
        isKnown: true,
        missedScans: 2
    )
    let discovered = NetworkDevice(
        id: "90:dd:5d:b7:bd:01",
        name: "Apple TV",
        ipAddress: "192.168.0.51",
        macAddress: "90:dd:5d:b7:bd:01",
        status: .online
    )

    let result = DeviceMerger.merge(existing: [existing], discovered: [discovered])

    #expect(result.devices.count == 1)
    #expect(result.devices.first?.status == .online)
    #expect(result.devices.first?.missedScans == 0)
    #expect(result.devices.first?.name == "Living Room TV")
}
