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

@Test
func versionUpdateCheckerAcceptsMacReleaseWithDMGAsset() {
    #expect(VersionUpdateChecker.isMacRelease(
        body: "## macOS\n- New native app build.",
        assetNames: ["LanGuard-1.3.1.dmg"]
    ))
}

@Test
func versionUpdateCheckerIgnoresDockerOnlyRelease() {
    #expect(!VersionUpdateChecker.isMacRelease(
        body: "## Docker/web\n- Fix Docker images.\n\n## macOS\n- No new macOS app build in this release.",
        assetNames: []
    ))
}

@Test
func versionUpdateCheckerAcceptsUnmarkedReleaseWithoutDMGAsset() {
    #expect(VersionUpdateChecker.isMacRelease(
        body: "## macOS\n- Notes only.",
        assetNames: []
    ))
}

@Test
func versionUpdateCheckerIgnoresDraftAndPrereleaseBuilds() {
    #expect(!VersionUpdateChecker.isMacRelease(
        body: "## macOS\n- Draft build.",
        assetNames: ["LanGuard-1.3.2.dmg"],
        isDraft: true
    ))
    #expect(!VersionUpdateChecker.isMacRelease(
        body: "## macOS\n- Prerelease build.",
        assetNames: ["LanGuard-1.3.2.dmg"],
        isPrerelease: true
    ))
}
