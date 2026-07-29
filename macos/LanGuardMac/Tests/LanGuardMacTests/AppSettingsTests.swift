import Testing
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
