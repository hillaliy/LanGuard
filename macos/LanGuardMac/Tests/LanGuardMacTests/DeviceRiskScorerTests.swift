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
func riskScorerKeepsKnownCameraWithExpectedPortsLow() {
    #expect(DeviceRiskScorer.risk(for: [80, 443, 554, 8443], isKnown: true, role: .camera) == .low)
}

@Test
func riskScorerKeepsKnownServerWithExpectedPortsLow() {
    #expect(DeviceRiskScorer.risk(for: [22, 80, 443, 8080, 8443], isKnown: true, role: .server) == .low)
}

@Test
func riskScorerStillMarksKnownServerWithDangerousRemotePortHigh() {
    #expect(DeviceRiskScorer.risk(for: [80, 3389], isKnown: true, role: .server) == .high)
}

@Test
func riskScorerMarksQuietDevicesAsLow() {
    #expect(DeviceRiskScorer.risk(for: [], isKnown: false) == .low)
}
