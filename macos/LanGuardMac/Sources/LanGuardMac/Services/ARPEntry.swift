import Foundation

struct ARPEntry: Equatable, Sendable {
    var hostname: String?
    var ipAddress: String
    var macAddress: String
}
