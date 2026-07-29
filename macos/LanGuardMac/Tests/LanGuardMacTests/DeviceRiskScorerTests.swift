import Testing
@testable import LanGuardMac

@Test
func riskScorerMarksDangerousRemoteAccessPortsAsHigh() {
    #expect(DeviceRiskScorer.risk(for: [80, 5900], isKnown: true) == .high)
}

@Test
func riskScorerMarksUnknownDevicesWithOpenPortsAsMedium() {
    #expect(DeviceRiskScorer.risk(for: [443], isKnown: false) == .medium)
}

@Test
func riskScorerMarksManyOpenPortsAsMedium() {
    #expect(DeviceRiskScorer.risk(for: [22, 80, 443, 8080], isKnown: true) == .medium)
}

@Test
func riskScorerMarksQuietDevicesAsLow() {
    #expect(DeviceRiskScorer.risk(for: [], isKnown: false) == .low)
}
