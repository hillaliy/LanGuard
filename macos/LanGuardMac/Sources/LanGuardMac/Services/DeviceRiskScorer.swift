import Foundation

enum DeviceRiskScorer {
    static func risk(for ports: [Int], isKnown: Bool, role: DeviceRole = .device) -> DeviceRisk {
        let expectedPorts = isKnown ? expectedPortsByRole[role, default: []] : []
        let unexpectedPorts = ports.filter { !expectedPorts.contains($0) }

        if unexpectedPorts.contains(where: highRiskPorts.contains) {
            return .high
        }

        if !isKnown, !unexpectedPorts.isEmpty {
            return .medium
        }

        if ports.count >= 4, !(isKnown && portDenseRoles.contains(role)) {
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

    private static let expectedPortsByRole: [DeviceRole: Set<Int>] = [
        .camera: [80, 443, 554, 8000, 8080, 8443, 8554],
        .intercom: [80, 443, 554, 8000, 8080, 8443, 8554],
        .server: [22, 80, 443, 445, 3000, 5000, 8080, 8443],
    ]

    private static let portDenseRoles: Set<DeviceRole> = [
        .camera,
        .intercom,
        .server,
    ]
}
