import Testing
@testable import LanGuardMac

@Test
func versionUpdateCheckerDetectsNewerVersion() {
    #expect(VersionUpdateChecker.isVersion("1.0.17", newerThan: "1.0.16"))
    #expect(VersionUpdateChecker.isVersion("v1.1.0", newerThan: "1.0.16"))
}

@Test
func versionUpdateCheckerDoesNotFlagSameOrOlderVersion() {
    #expect(!VersionUpdateChecker.isVersion("v1.0.16", newerThan: "1.0.16"))
    #expect(!VersionUpdateChecker.isVersion("1.0.15", newerThan: "1.0.16"))
}

@Test
func versionUpdateCheckerComparesMissingPatchAsZero() {
    #expect(!VersionUpdateChecker.isVersion("1.0", newerThan: "1.0.0"))
    #expect(VersionUpdateChecker.isVersion("1.0.1", newerThan: "1.0"))
}

@Test
func versionUpdateCheckerNormalizesReleaseTags() {
    #expect(VersionUpdateChecker.normalizedVersionString("v1.0.16") == "1.0.16")
    #expect(VersionUpdateChecker.normalizedVersionString(" V1.0.16 ") == "1.0.16")
}
