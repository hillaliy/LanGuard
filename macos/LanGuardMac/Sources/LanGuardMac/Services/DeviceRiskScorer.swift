import Foundation

enum DeviceRiskScorer {
    static func risk(for ports: [Int], isKnown: Bool) -> DeviceRisk {
        if ports.contains(where: highRiskPorts.contains) {
            return .high
        }

        if !isKnown, !ports.isEmpty {
            return .medium
        }

        if ports.count >= 4 {
            return .medium
        }

        return .low
    }

    private static let highRiskPorts: Set<Int> = [
        21,
        23,
        3389,
        5900,
    ]
}
