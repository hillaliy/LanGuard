import Foundation

enum QuietHoursWeekday: String, Codable, CaseIterable, Identifiable, Sendable {
    case monday
    case tuesday
    case wednesday
    case thursday
    case friday
    case saturday
    case sunday

    var id: String { rawValue }

    var shortTitle: String {
        switch self {
        case .monday: "Mon"
        case .tuesday: "Tue"
        case .wednesday: "Wed"
        case .thursday: "Thu"
        case .friday: "Fri"
        case .saturday: "Sat"
        case .sunday: "Sun"
        }
    }

    static func from(calendarWeekday: Int) -> Self? {
        switch calendarWeekday {
        case 1: .sunday
        case 2: .monday
        case 3: .tuesday
        case 4: .wednesday
        case 5: .thursday
        case 6: .friday
        case 7: .saturday
        default: nil
        }
    }
}

struct AppSettings: Codable, Equatable, Sendable {
    var defaultScanRange: String
    var scanIntervalMinutes: Int
    var tcpPorts: [Int]
    var scheduledScanningEnabled: Bool
    var newDeviceNotificationsEnabled: Bool
    var riskyPortNotificationsEnabled: Bool
    var quietHoursEnabled: Bool
    var quietHoursStart: String
    var quietHoursEnd: String
    var quietHoursDays: [QuietHoursWeekday]
    var cloudBackupEnabled: Bool
    var cloudBackupFolderPath: String?
    var rooms: [String]
    var didRunInitialVersionCheck: Bool
    var versionUpdate: AppVersionUpdate?

    static let defaultPorts = [22, 53, 80, 443, 554, 631, 8080, 8443, 9100]

    static let `default` = AppSettings(
        defaultScanRange: "192.168.0.0/24",
        scanIntervalMinutes: 5,
        tcpPorts: defaultPorts,
        scheduledScanningEnabled: false,
        newDeviceNotificationsEnabled: true,
        riskyPortNotificationsEnabled: true,
        quietHoursEnabled: false,
        quietHoursStart: "22:00",
        quietHoursEnd: "07:00",
        quietHoursDays: QuietHoursWeekday.allCases,
        cloudBackupEnabled: false,
        cloudBackupFolderPath: nil,
        rooms: [],
        didRunInitialVersionCheck: false,
        versionUpdate: nil
    )

    var normalized: AppSettings {
        let normalizedBackupPath = cloudBackupFolderPath?
            .trimmingCharacters(in: .whitespacesAndNewlines)

        return AppSettings(
            defaultScanRange: defaultScanRange.trimmingCharacters(in: .whitespacesAndNewlines),
            scanIntervalMinutes: min(max(scanIntervalMinutes, 1), 1440),
            tcpPorts: Self.normalizedPorts(tcpPorts),
            scheduledScanningEnabled: scheduledScanningEnabled,
            newDeviceNotificationsEnabled: newDeviceNotificationsEnabled,
            riskyPortNotificationsEnabled: riskyPortNotificationsEnabled,
            quietHoursEnabled: quietHoursEnabled,
            quietHoursStart: Self.normalizedTime(quietHoursStart, fallback: Self.default.quietHoursStart),
            quietHoursEnd: Self.normalizedTime(quietHoursEnd, fallback: Self.default.quietHoursEnd),
            quietHoursDays: QuietHoursWeekday.allCases.filter { quietHoursDays.contains($0) },
            cloudBackupEnabled: cloudBackupEnabled,
            cloudBackupFolderPath: normalizedBackupPath?.isEmpty == false ? normalizedBackupPath : nil,
            rooms: Self.normalizedRooms(rooms),
            didRunInitialVersionCheck: didRunInitialVersionCheck,
            versionUpdate: versionUpdate
        )
    }

    static func parsePorts(_ rawValue: String) -> [Int]? {
        let parts = rawValue
            .split { character in
                character == "," || character == " " || character == "\n" || character == "\t"
            }

        guard !parts.isEmpty else { return nil }

        var ports: [Int] = []
        for part in parts {
            guard let port = Int(part), (1...65_535).contains(port) else {
                return nil
            }
            ports.append(port)
        }

        return normalizedPorts(ports)
    }

    enum CodingKeys: String, CodingKey {
        case defaultScanRange
        case scanIntervalMinutes
        case tcpPorts
        case scheduledScanningEnabled
        case newDeviceNotificationsEnabled
        case riskyPortNotificationsEnabled
        case quietHoursEnabled
        case quietHoursStart
        case quietHoursEnd
        case quietHoursDays
        case cloudBackupEnabled
        case cloudBackupFolderPath
        case rooms
        case didRunInitialVersionCheck
        case versionUpdate
    }

    init(
        defaultScanRange: String,
        scanIntervalMinutes: Int,
        tcpPorts: [Int],
        scheduledScanningEnabled: Bool,
        newDeviceNotificationsEnabled: Bool = Self.default.newDeviceNotificationsEnabled,
        riskyPortNotificationsEnabled: Bool = Self.default.riskyPortNotificationsEnabled,
        quietHoursEnabled: Bool = Self.default.quietHoursEnabled,
        quietHoursStart: String = Self.default.quietHoursStart,
        quietHoursEnd: String = Self.default.quietHoursEnd,
        quietHoursDays: [QuietHoursWeekday] = Self.default.quietHoursDays,
        cloudBackupEnabled: Bool = Self.default.cloudBackupEnabled,
        cloudBackupFolderPath: String? = Self.default.cloudBackupFolderPath,
        rooms: [String] = Self.default.rooms,
        didRunInitialVersionCheck: Bool = Self.default.didRunInitialVersionCheck,
        versionUpdate: AppVersionUpdate? = Self.default.versionUpdate
    ) {
        self.defaultScanRange = defaultScanRange
        self.scanIntervalMinutes = scanIntervalMinutes
        self.tcpPorts = tcpPorts
        self.scheduledScanningEnabled = scheduledScanningEnabled
        self.newDeviceNotificationsEnabled = newDeviceNotificationsEnabled
        self.riskyPortNotificationsEnabled = riskyPortNotificationsEnabled
        self.quietHoursEnabled = quietHoursEnabled
        self.quietHoursStart = quietHoursStart
        self.quietHoursEnd = quietHoursEnd
        self.quietHoursDays = quietHoursDays
        self.cloudBackupEnabled = cloudBackupEnabled
        self.cloudBackupFolderPath = cloudBackupFolderPath
        self.rooms = rooms
        self.didRunInitialVersionCheck = didRunInitialVersionCheck
        self.versionUpdate = versionUpdate
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        defaultScanRange = try container.decodeIfPresent(String.self, forKey: .defaultScanRange) ?? Self.default.defaultScanRange
        scanIntervalMinutes = try container.decodeIfPresent(Int.self, forKey: .scanIntervalMinutes) ?? Self.default.scanIntervalMinutes
        tcpPorts = try container.decodeIfPresent([Int].self, forKey: .tcpPorts) ?? Self.default.tcpPorts
        scheduledScanningEnabled = try container.decodeIfPresent(Bool.self, forKey: .scheduledScanningEnabled) ?? Self.default.scheduledScanningEnabled
        newDeviceNotificationsEnabled = try container.decodeIfPresent(Bool.self, forKey: .newDeviceNotificationsEnabled) ?? Self.default.newDeviceNotificationsEnabled
        riskyPortNotificationsEnabled = try container.decodeIfPresent(Bool.self, forKey: .riskyPortNotificationsEnabled) ?? Self.default.riskyPortNotificationsEnabled
        quietHoursEnabled = try container.decodeIfPresent(Bool.self, forKey: .quietHoursEnabled) ?? Self.default.quietHoursEnabled
        quietHoursStart = try container.decodeIfPresent(String.self, forKey: .quietHoursStart) ?? Self.default.quietHoursStart
        quietHoursEnd = try container.decodeIfPresent(String.self, forKey: .quietHoursEnd) ?? Self.default.quietHoursEnd
        quietHoursDays = try container.decodeIfPresent([QuietHoursWeekday].self, forKey: .quietHoursDays) ?? Self.default.quietHoursDays
        cloudBackupEnabled = try container.decodeIfPresent(Bool.self, forKey: .cloudBackupEnabled) ?? Self.default.cloudBackupEnabled
        cloudBackupFolderPath = try container.decodeIfPresent(String.self, forKey: .cloudBackupFolderPath) ?? Self.default.cloudBackupFolderPath
        rooms = try container.decodeIfPresent([String].self, forKey: .rooms) ?? Self.default.rooms
        didRunInitialVersionCheck = try container.decodeIfPresent(Bool.self, forKey: .didRunInitialVersionCheck) ?? Self.default.didRunInitialVersionCheck
        versionUpdate = try container.decodeIfPresent(AppVersionUpdate.self, forKey: .versionUpdate) ?? Self.default.versionUpdate
    }

    private static func normalizedPorts(_ ports: [Int]) -> [Int] {
        Array(Set(ports.filter { (1...65_535).contains($0) })).sorted()
    }

    private static func normalizedRooms(_ rooms: [String]) -> [String] {
        let trimmed = rooms.map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
        return Array(Set(trimmed.filter { !$0.isEmpty })).sorted {
            $0.localizedStandardCompare($1) == .orderedAscending
        }
    }

    func quietHoursActive(at date: Date = .now, calendar: Calendar = .current) -> Bool {
        guard quietHoursEnabled,
              !quietHoursDays.isEmpty,
              let startMinutes = Self.timeMinutes(quietHoursStart),
              let endMinutes = Self.timeMinutes(quietHoursEnd) else {
            return false
        }

        let components = calendar.dateComponents([.hour, .minute], from: date)
        guard let hour = components.hour, let minute = components.minute else { return false }
        let currentMinutes = hour * 60 + minute

        var weekdayDate = date
        if startMinutes > endMinutes, currentMinutes < endMinutes {
            weekdayDate = calendar.date(byAdding: .day, value: -1, to: date) ?? date
        }
        guard let weekday = QuietHoursWeekday.from(
            calendarWeekday: calendar.component(.weekday, from: weekdayDate)
        ), quietHoursDays.contains(weekday) else {
            return false
        }

        if startMinutes == endMinutes { return true }
        if startMinutes < endMinutes {
            return currentMinutes >= startMinutes && currentMinutes < endMinutes
        }
        return currentMinutes >= startMinutes || currentMinutes < endMinutes
    }

    private static func normalizedTime(_ value: String, fallback: String) -> String {
        guard let minutes = timeMinutes(value) else { return fallback }
        return String(format: "%02d:%02d", minutes / 60, minutes % 60)
    }

    private static func timeMinutes(_ value: String) -> Int? {
        let parts = value.split(separator: ":", omittingEmptySubsequences: false)
        guard parts.count == 2,
              let hour = Int(parts[0]),
              let minute = Int(parts[1]),
              (0...23).contains(hour),
              (0...59).contains(minute) else {
            return nil
        }
        return hour * 60 + minute
    }
}
