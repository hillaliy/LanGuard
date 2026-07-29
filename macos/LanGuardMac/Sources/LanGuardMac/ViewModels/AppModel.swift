import Foundation
import Observation

@MainActor
@Observable
final class AppModel {
    private let scanner: NetworkScanning
    private let storage: AppStorageServicing
    private let notifications: NotificationServicing
    private var scheduleTask: Task<Void, Never>?

    var devices: [NetworkDevice] = []
    var scanHistory: [ScanRecord] = []
    var recentChanges: [DeviceChange] = []
    var settings: AppSettings = .default
    var isScanning = false
    var isLoading = false
    var nextScheduledScanAt: Date?
    var lastErrorMessage: String?
    private var didLoadSavedState = false

    init(
        scanner: NetworkScanning = LocalNetworkScanner(),
        storage: AppStorageServicing = AppStorageService(),
        notifications: NotificationServicing = NotificationServiceFactory.makeDefault()
    ) {
        self.scanner = scanner
        self.storage = storage
        self.notifications = notifications
        loadSavedState()
    }

    var onlineCount: Int {
        devices.filter { $0.status == .online }.count
    }

    var unknownCount: Int {
        devices.filter { !$0.isKnown }.count
    }

    var openPortCount: Int {
        devices.reduce(0) { $0 + $1.openPorts.count }
    }

    var latestScan: ScanRecord? {
        scanHistory.first
    }

    func runScan() {
        runScan(triggeredBySchedule: false)
    }

    private func runScan(triggeredBySchedule: Bool) {
        guard !isScanning else { return }

        if !triggeredBySchedule {
            scheduleTask?.cancel()
            scheduleTask = nil
        }

        isScanning = true
        lastErrorMessage = nil
        nextScheduledScanAt = nil

        let scanID = UUID()
        scanHistory.insert(ScanRecord(id: scanID), at: 0)

        Task {
            do {
                let discoveredDevices = try await scanner.scan(settings: settings)
                let mergeResult = DeviceMerger.merge(existing: devices, discovered: discoveredDevices)
                devices = mergeResult.devices
                recentChanges = Array((mergeResult.changes + recentChanges).prefix(50))
                completeScan(id: scanID, status: .completed, count: discoveredDevices.count)
                await notifyScanChanges(mergeResult)
                saveCurrentState()
            } catch {
                lastErrorMessage = error.localizedDescription
                completeScan(id: scanID, status: .failed, errorMessage: error.localizedDescription)
                saveCurrentState()
            }

            isScanning = false
            scheduleNextScanIfNeeded()
        }
    }

    func prepareNotifications() async {
        await notifications.requestAuthorization()
    }

    func updateDevice(_ updatedDevice: NetworkDevice) {
        guard let index = devices.firstIndex(where: { $0.id == updatedDevice.id }) else {
            return
        }

        devices[index] = updatedDevice
        saveCurrentState()
    }

    func updateSettings(_ updatedSettings: AppSettings) {
        settings = updatedSettings
        saveCurrentState()
        configureScheduledScanning()
    }

    func clearScanHistory() {
        scanHistory.removeAll()
        saveCurrentState()
    }

    func exportDeviceInventory(to url: URL) throws {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        encoder.dateEncodingStrategy = .iso8601
        let document = DeviceInventoryDocument(devices: devices)
        let data = try encoder.encode(document)
        try data.write(to: url, options: [.atomic])
    }

    func importDeviceInventory(from url: URL) throws -> DeviceInventoryImportResult {
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        let data = try Data(contentsOf: url)
        let document = try decoder.decode(DeviceInventoryDocument.self, from: data)

        guard document.format == DeviceInventoryDocument.format else {
            throw DeviceInventoryImportError.unsupportedFormat
        }

        var devicesByID = Dictionary(uniqueKeysWithValues: devices.map { ($0.id, $0) })
        var created = 0
        var updated = 0
        var skipped = 0

        for item in document.devices {
            guard let importedDevice = item.merged(into: item.normalizedMAC.flatMap({ devicesByID[$0] })) else {
                skipped += 1
                continue
            }

            if devicesByID[importedDevice.id] == nil {
                created += 1
            } else {
                updated += 1
            }
            devicesByID[importedDevice.id] = importedDevice
        }

        devices = devicesByID.values.sorted {
            IPv4AddressSortKey($0.ipAddress) < IPv4AddressSortKey($1.ipAddress)
        }
        saveCurrentState()
        return DeviceInventoryImportResult(created: created, updated: updated, skipped: skipped)
    }

    func loadSavedState() {
        guard !isLoading else { return }

        isLoading = true

        Task {
            do {
                let snapshot = try await storage.load()
                devices = snapshot.devices
                scanHistory = snapshot.scanHistory
                recentChanges = snapshot.recentChanges
                settings = snapshot.settings
                didLoadSavedState = true
                configureScheduledScanning()
                lastErrorMessage = nil
            } catch {
                lastErrorMessage = "Could not load saved LanGuard data: \(error.localizedDescription)"
            }

            isLoading = false
        }
    }

    private func configureScheduledScanning() {
        scheduleTask?.cancel()
        scheduleTask = nil
        nextScheduledScanAt = nil

        guard didLoadSavedState, settings.scheduledScanningEnabled else {
            return
        }

        scheduleNextScanIfNeeded()
    }

    private func scheduleNextScanIfNeeded() {
        guard settings.scheduledScanningEnabled else {
            nextScheduledScanAt = nil
            return
        }

        scheduleTask?.cancel()
        let nextScanDate = Date().addingTimeInterval(TimeInterval(settings.scanIntervalMinutes * 60))
        nextScheduledScanAt = nextScanDate

        scheduleTask = Task { [weak self] in
            let delay = await MainActor.run {
                UInt64(self?.settings.scanIntervalMinutes ?? 1) * 60 * 1_000_000_000
            }

            try? await Task.sleep(nanoseconds: delay)
            guard !Task.isCancelled else { return }

            await MainActor.run {
                self?.runScan(triggeredBySchedule: true)
            }
        }
    }

    private func saveCurrentState() {
        let snapshot = AppStorageSnapshot(
            devices: devices,
            scanHistory: Array(scanHistory.prefix(100)),
            settings: settings,
            recentChanges: Array(recentChanges.prefix(50))
        )

        Task {
            do {
                try await storage.save(snapshot)
            } catch {
                lastErrorMessage = "Could not save LanGuard data: \(error.localizedDescription)"
            }
        }
    }

    private func notifyScanChanges(_ mergeResult: DeviceMergeResult) async {
        if settings.newDeviceNotificationsEnabled {
            for device in mergeResult.newDevices where !device.isKnown {
                await notifications.notifyNewDevice(device)
            }
        }

        if settings.riskyPortNotificationsEnabled {
            for device in mergeResult.riskyDevices where !device.isKnown {
                await notifications.notifyRiskyDevice(device)
            }
        }
    }

    private func notifyNewDevices(_ devices: [NetworkDevice]) async {
        for device in devices where !device.isKnown {
            await notifications.notifyNewDevice(device)
        }
    }

    private func completeScan(
        id: UUID,
        status: ScanRecord.Status,
        count: Int = 0,
        errorMessage: String? = nil
    ) {
        guard let index = scanHistory.firstIndex(where: { $0.id == id }) else {
            return
        }

        scanHistory[index].finishedAt = .now
        scanHistory[index].status = status
        scanHistory[index].discoveredCount = count
        scanHistory[index].errorMessage = errorMessage
    }
}

enum DeviceInventoryImportError: LocalizedError {
    case unsupportedFormat

    var errorDescription: String? {
        switch self {
        case .unsupportedFormat:
            "Choose a LanGuard device inventory JSON file."
        }
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
