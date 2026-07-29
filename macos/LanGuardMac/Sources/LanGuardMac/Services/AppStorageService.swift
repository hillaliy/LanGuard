import Foundation

protocol AppStorageServicing: Sendable {
    func load() async throws -> AppStorageSnapshot
    func save(_ snapshot: AppStorageSnapshot) async throws
}

struct AppStorageService: AppStorageServicing {
    private let fileURL: URL
    private let encoder: JSONEncoder
    private let decoder: JSONDecoder

    init(fileURL: URL? = nil) {
        self.fileURL = fileURL ?? Self.defaultFileURL()

        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        encoder.dateEncodingStrategy = .iso8601
        self.encoder = encoder

        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        self.decoder = decoder
    }

    func load() async throws -> AppStorageSnapshot {
        try await Task.detached(priority: .utility) {
            guard FileManager.default.fileExists(atPath: fileURL.path) else {
                return .empty
            }

            let data = try Data(contentsOf: fileURL)
            return try decoder.decode(AppStorageSnapshot.self, from: data)
        }.value
    }

    func save(_ snapshot: AppStorageSnapshot) async throws {
        try await Task.detached(priority: .utility) {
            let directoryURL = fileURL.deletingLastPathComponent()
            try FileManager.default.createDirectory(
                at: directoryURL,
                withIntermediateDirectories: true
            )

            let data = try encoder.encode(snapshot)
            try data.write(to: fileURL, options: [.atomic])
        }.value
    }

    private static func defaultFileURL() -> URL {
        let baseURL = FileManager.default.urls(
            for: .applicationSupportDirectory,
            in: .userDomainMask
        ).first ?? FileManager.default.temporaryDirectory

        return baseURL
            .appending(path: "LanGuard", directoryHint: .isDirectory)
            .appending(path: "LanGuardMac.json")
    }
}
