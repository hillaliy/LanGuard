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

    #expect(result.devices == discovered)
    #expect(result.newDevices == discovered)
}

@Test
func deviceMergerPreservesCustomIcon() {
    let existing = NetworkDevice(
        id: "90:dd:5d:b7:bd:01",
        name: "Living Room TV",
        ipAddress: "192.168.0.51",
        macAddress: "90:dd:5d:b7:bd:01",
        iconName: "tv",
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
