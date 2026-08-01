import Foundation

struct VersionUpdateStatus: Equatable {
    let latestVersion: String
    let releaseURL: URL
    let isUpdateAvailable: Bool
}

enum VersionUpdateChecker {
    private static let latestReleaseAPIURL = URL(string: "https://api.github.com/repos/hillaliy/LanGuard/releases/latest")!

    static func check(currentVersion: String) async throws -> VersionUpdateStatus {
        var request = URLRequest(url: latestReleaseAPIURL)
        request.setValue("application/vnd.github+json", forHTTPHeaderField: "Accept")
        request.setValue("LanGuardMac", forHTTPHeaderField: "User-Agent")

        let (data, response) = try await URLSession.shared.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse,
              200..<300 ~= httpResponse.statusCode else {
            throw VersionUpdateError.badResponse
        }

        let release = try JSONDecoder().decode(GitHubReleaseResponse.self, from: data)
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
}

private enum VersionUpdateError: Error {
    case badResponse
}

private struct GitHubReleaseResponse: Decodable {
    let tagName: String
    let htmlURL: URL

    private enum CodingKeys: String, CodingKey {
        case tagName = "tag_name"
        case htmlURL = "html_url"
    }
}
