import Foundation
import Testing
@testable import LanGuardMac

@Test
func storageLoadsEmptySnapshotWhenFileDoesNotExist() async throws {
    let fileURL = FileManager.default.temporaryDirectory
        .appending(path: "LanGuardMacTests-\(UUID().uuidString)")
        .appending(path: "state.json")
    let storage = AppStorageService(fileURL: fileURL)

    let snapshot = try await storage.load()

    #expect(snapshot == .empty)
}

@Test
func storagePersistsDevicesAndScanHistory() async throws {
    let directoryURL = FileManager.default.temporaryDirectory
        .appending(path: "LanGuardMacTests-\(UUID().uuidString)", directoryHint: .isDirectory)
    let fileURL = directoryURL.appending(path: "state.json")
    let storage = AppStorageService(fileURL: fileURL)
    let device = NetworkDevice(
        id: "90:dd:5d:b7:bd:01",
        name: "Apple TV",
        ipAddress: "192.168.0.51",
        macAddress: "90:dd:5d:b7:bd:01",
        hostname: "apple-tv.local",
        iconName: "tv",
        status: .online,
        risk: .low,
        isKnown: true,
        isGateway: false,
        firstSeen: Date(timeIntervalSince1970: 1_785_000_000),
        lastSeen: Date(timeIntervalSince1970: 1_785_000_100)
    )
    let scan = ScanRecord(
        id: UUID(uuidString: "11111111-1111-1111-1111-111111111111")!,
        startedAt: Date(timeIntervalSince1970: 1_785_000_000),
        finishedAt: Date(timeIntervalSince1970: 1_785_000_005),
        status: .completed,
        discoveredCount: 1
    )
    let change = DeviceChange(
        id: UUID(uuidString: "22222222-2222-2222-2222-222222222222")!,
        deviceID: device.id,
        deviceName: device.name,
        ipAddress: device.ipAddress,
        kind: .ports,
        changedAt: Date(timeIntervalSince1970: 1_785_000_200)
    )
    let snapshot = AppStorageSnapshot(devices: [device], scanHistory: [scan], recentChanges: [change])

    try await storage.save(snapshot)
    let loadedSnapshot = try await storage.load()

    #expect(loadedSnapshot == snapshot)
}
