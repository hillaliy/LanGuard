import Foundation

struct ScanRecord: Codable, Identifiable, Hashable, Sendable {
    enum Status: String, Codable, Sendable {
        case running
        case completed
        case failed
    }

    let id: UUID
    var startedAt: Date
    var finishedAt: Date?
    var status: Status
    var discoveredCount: Int
    var errorMessage: String?

    var duration: TimeInterval? {
        guard let finishedAt else { return nil }
        return finishedAt.timeIntervalSince(startedAt)
    }

    init(
        id: UUID = UUID(),
        startedAt: Date = .now,
        finishedAt: Date? = nil,
        status: Status = .running,
        discoveredCount: Int = 0,
        errorMessage: String? = nil
    ) {
        self.id = id
        self.startedAt = startedAt
        self.finishedAt = finishedAt
        self.status = status
        self.discoveredCount = discoveredCount
        self.errorMessage = errorMessage
    }
}
