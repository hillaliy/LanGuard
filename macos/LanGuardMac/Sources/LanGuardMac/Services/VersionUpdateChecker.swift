import Foundation

struct VersionUpdateStatus: Equatable {
    let latestVersion: String
    let releaseURL: URL
    let isUpdateAvailable: Bool
}

enum VersionUpdateChecker {
    private static let releasesAPIURL = URL(string: "https://api.github.com/repos/hillaliy/LanGuard/releases?per_page=20")!
    private static let releasesPageURL = URL(string: "https://github.com/hillaliy/LanGuard/releases")!

    static func check(currentVersion: String) async throws -> VersionUpdateStatus {
        var request = URLRequest(url: releasesAPIURL)
        request.setValue("application/vnd.github+json", forHTTPHeaderField: "Accept")
        request.setValue("LanGuardMac", forHTTPHeaderField: "User-Agent")

        let (data, response) = try await URLSession.shared.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse,
              200..<300 ~= httpResponse.statusCode else {
            throw VersionUpdateError.badResponse
        }

        let releases = try JSONDecoder().decode([GitHubReleaseResponse].self, from: data)
        guard let release = releases.first(where: isMacRelease) else {
            return VersionUpdateStatus(
                latestVersion: normalizedVersionString(currentVersion),
                releaseURL: releasesPageURL,
                isUpdateAvailable: false
            )
        }

        let latestVersion = normalizedVersionString(release.tagName)

        return VersionUpdateStatus(
            latestVersion: latestVersion,
            releaseURL: release.htmlURL,
            isUpdateAvailable: isVersion(latestVersion, newerThan: currentVersion)
        )
    }

    static func isVersion(_ latestVersion: String, newerThan currentVersion: String) -> Bool {
        let latest = versionComponents(latestVersion)
        let current = versionComponents(currentVersion)
        let maxCount = max(latest.count, current.count)

        for index in 0..<maxCount {
            let latestPart = index < latest.count ? latest[index] : 0
            let currentPart = index < current.count ? current[index] : 0

            if latestPart != currentPart {
                return latestPart > currentPart
            }
        }

        return false
    }

    static func normalizedVersionString(_ rawVersion: String) -> String {
        var version = rawVersion
            .trimmingCharacters(in: .whitespacesAndNewlines)

        if version.lowercased().hasPrefix("v") {
            version.removeFirst()
        }

        return version
    }

    static func versionComponents(_ rawVersion: String) -> [Int] {
        let normalizedVersion = normalizedVersionString(rawVersion)
        let components = normalizedVersion
            .split { !$0.isNumber }
            .compactMap { Int($0) }

        return components.isEmpty ? [0] : components
    }

    static func isMacRelease(
        body: String?,
        assetNames: [String],
        isDraft: Bool = false,
        isPrerelease: Bool = false
    ) -> Bool {
        if isDraft || isPrerelease {
            return false
        }

        let hasMacDownload = assetNames.contains { assetName in
            assetName.lowercased().hasSuffix(".dmg")
        }
        if hasMacDownload {
            return true
        }

        let bodyText = (body ?? "").lowercased()
        return !bodyText.contains("no new macos app build")
            && !bodyText.contains("same macos app as")
            && !bodyText.contains("docker/web only")
            && !bodyText.contains("docker only")
    }

    private static func isMacRelease(_ release: GitHubReleaseResponse) -> Bool {
        isMacRelease(
            body: release.body,
            assetNames: release.assets.map(\.name),
            isDraft: release.isDraft,
            isPrerelease: release.isPrerelease
        )
    }
}

private enum VersionUpdateError: Error {
    case badResponse
}

private struct GitHubReleaseResponse: Decodable {
    let tagName: String
    let htmlURL: URL
    let body: String?
    let isDraft: Bool
    let isPrerelease: Bool
    let assets: [GitHubReleaseAsset]

    private enum CodingKeys: String, CodingKey {
        case tagName = "tag_name"
        case htmlURL = "html_url"
        case body
        case isDraft = "draft"
        case isPrerelease = "prerelease"
        case assets
    }
}

private struct GitHubReleaseAsset: Decodable {
    let name: String
}
