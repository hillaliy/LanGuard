import Testing
import Foundation
@testable import LanGuardMac

@Test
func appSettingsParsesAndNormalizesPorts() {
    #expect(AppSettings.parsePorts("443, 80 22\n80") == [22, 80, 443])
}

@Test
func appSettingsRejectsInvalidPorts() {
    #expect(AppSettings.parsePorts("80, 70000") == nil)
}

@Test
func cidrRangeMatchesOnlyAddressesInsideRange() {
    let range = IPv4CIDRRange("192.168.0.0/24")

    #expect(range?.contains("192.168.0.1") == true)
    #expect(range?.contains("192.168.1.1") == false)
}

@Test
func cidrRangeBuildsUsableHostsWithoutNetworkAndBroadcast() {
    let range = IPv4CIDRRange("192.168.0.0/30")

    #expect(range?.usableHosts() == ["192.168.0.1", "192.168.0.2"])
}

@Test
func cidrRangeRejectsNetworkAndBroadcastAsUsableHosts() {
    let range = IPv4CIDRRange("192.168.0.0/24")

    #expect(range?.isUsableHost("192.168.0.1") == true)
    #expect(range?.isUsableHost("192.168.0.0") == false)
    #expect(range?.isUsableHost("192.168.0.255") == false)
}

@Test
func appSettingsQuietHoursApplyOnlyOnSelectedDay() {
    var calendar = Calendar(identifier: .gregorian)
    calendar.timeZone = TimeZone(secondsFromGMT: 0)!
    let monday = calendar.date(from: DateComponents(year: 2026, month: 8, day: 24, hour: 12))!
    let tuesday = calendar.date(from: DateComponents(year: 2026, month: 8, day: 25, hour: 12))!
    let settings = AppSettings(
        defaultScanRange: "192.168.0.0/24",
        scanIntervalMinutes: 5,
        tcpPorts: AppSettings.defaultPorts,
        scheduledScanningEnabled: false,
        quietHoursEnabled: true,
        quietHoursStart: "09:00",
        quietHoursEnd: "17:00",
        quietHoursDays: [.monday]
    )

    #expect(settings.quietHoursActive(at: monday, calendar: calendar))
    #expect(!settings.quietHoursActive(at: tuesday, calendar: calendar))
}

@Test
func appSettingsOvernightQuietHoursUseStartingDay() {
    var calendar = Calendar(identifier: .gregorian)
    calendar.timeZone = TimeZone(secondsFromGMT: 0)!
    let mondayNight = calendar.date(from: DateComponents(year: 2026, month: 8, day: 24, hour: 23))!
    let tuesdayMorning = calendar.date(from: DateComponents(year: 2026, month: 8, day: 25, hour: 2))!
    let tuesdayNight = calendar.date(from: DateComponents(year: 2026, month: 8, day: 25, hour: 23))!
    let settings = AppSettings(
        defaultScanRange: "192.168.0.0/24",
        scanIntervalMinutes: 5,
        tcpPorts: AppSettings.defaultPorts,
        scheduledScanningEnabled: false,
        quietHoursEnabled: true,
        quietHoursStart: "22:00",
        quietHoursEnd: "07:00",
        quietHoursDays: [.monday]
    )

    #expect(settings.quietHoursActive(at: mondayNight, calendar: calendar))
    #expect(settings.quietHoursActive(at: tuesdayMorning, calendar: calendar))
    #expect(!settings.quietHoursActive(at: tuesdayNight, calendar: calendar))
}

@Test
func appSettingsDecodesLegacyDataWithQuietHoursDefaults() throws {
    let settings = try JSONDecoder().decode(AppSettings.self, from: Data("{}".utf8))

    #expect(!settings.quietHoursEnabled)
    #expect(settings.quietHoursStart == "22:00")
    #expect(settings.quietHoursEnd == "07:00")
    #expect(settings.quietHoursDays == QuietHoursWeekday.allCases)
}
