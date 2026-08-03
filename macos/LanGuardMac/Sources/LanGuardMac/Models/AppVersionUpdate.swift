import Foundation

struct AppVersionUpdate: Codable, Equatable, Sendable {
    var latestVersion: String
    var releaseURL: URL
    var isUpdateAvailable: Bool
    var checkedAt: Date

    init(
        latestVersion: String,
        releaseURL: URL,
        isUpdateAvailable: Bool,
        checkedAt: Date = .now
    ) {
        self.latestVersion = latestVersion
        self.releaseURL = releaseURL
        self.isUpdateAvailable = isUpdateAvailable
        self.checkedAt = checkedAt
    }

    init(status: VersionUpdateStatus, checkedAt: Date = .now) {
        self.init(
            latestVersion: status.latestVersion,
            releaseURL: status.releaseURL,
            isUpdateAvailable: status.isUpdateAvailable,
            checkedAt: checkedAt
        )
    }
}
