import Foundation
import UserNotifications

@MainActor
protocol NotificationServicing: AnyObject {
    func authorizationStatus() async -> AppNotificationAuthorizationStatus
    func requestAuthorization() async -> Bool
    func notifyNewDevice(_ device: NetworkDevice) async
    func notifyRiskyDevice(_ device: NetworkDevice) async
    func notifyTest() async throws
}

enum AppNotificationAuthorizationStatus: Sendable {
    case disabledInDevelopment
    case notDetermined
    case denied
    case authorized
}

enum NotificationServiceError: LocalizedError {
    case disabledInDevelopment
    case notAuthorized

    var errorDescription: String? {
        switch self {
        case .disabledInDevelopment:
            "Notifications require the packaged LanGuard.app. They are disabled when running with swift run."
        case .notAuthorized:
            "Notifications are not allowed for LanGuard in macOS System Settings."
        }
    }
}

enum NotificationServiceFactory {
    @MainActor
    static func makeDefault() -> NotificationServicing {
        guard Bundle.main.bundleIdentifier != nil,
              Bundle.main.bundleURL.pathExtension == "app" else {
            return DisabledNotificationService()
        }

        return NotificationService()
    }
}

final class NotificationService: NSObject, NotificationServicing, UNUserNotificationCenterDelegate {
    private let center: UNUserNotificationCenter

    override init() {
        self.center = .current()
        super.init()
        center.delegate = self
    }

    init(center: UNUserNotificationCenter) {
        self.center = center
        super.init()
        center.delegate = self
    }

    func authorizationStatus() async -> AppNotificationAuthorizationStatus {
        let settings = await center.notificationSettings()
        switch settings.authorizationStatus {
        case .notDetermined:
            return .notDetermined
        case .denied:
            return .denied
        case .authorized, .provisional, .ephemeral:
            return .authorized
        @unknown default:
            return .denied
        }
    }

    func requestAuthorization() async -> Bool {
        do {
            return try await center.requestAuthorization(options: [.alert, .sound])
        } catch {
            // Permission failures are non-fatal; the app can continue without notifications.
            return false
        }
    }

    func notifyNewDevice(_ device: NetworkDevice) async {
        try? await addNotification(
            identifier: "new-device-\(device.id)-\(device.lastSeen.timeIntervalSince1970)",
            title: "New device found",
            body: "\(device.name) joined at \(device.ipAddress)"
        )
    }

    func notifyRiskyDevice(_ device: NetworkDevice) async {
        let ports = device.openPorts.map(String.init).joined(separator: ", ")
        try? await addNotification(
            identifier: "risky-device-\(device.id)-\(device.lastSeen.timeIntervalSince1970)",
            title: "Risky ports found",
            body: "\(device.name) has high-risk ports open: \(ports)"
        )
    }

    func notifyTest() async throws {
        guard await isAuthorized else {
            throw NotificationServiceError.notAuthorized
        }

        try await addNotification(
            identifier: "test-notification-\(Date().timeIntervalSince1970)",
            title: "LanGuard notifications are working",
            body: "You will receive alerts for new unknown devices and unknown devices with risky ports."
        )
    }

    private func addNotification(identifier: String, title: String, body: String) async throws {
        let content = UNMutableNotificationContent()
        content.title = title
        content.body = body
        content.sound = .default

        let request = UNNotificationRequest(
            identifier: identifier,
            content: content,
            trigger: nil
        )

        try await center.add(request)
    }

    private var isAuthorized: Bool {
        get async {
            let settings = await center.notificationSettings()
            switch settings.authorizationStatus {
            case .authorized, .provisional, .ephemeral:
                return true
            case .denied, .notDetermined:
                return false
            @unknown default:
                return false
            }
        }
    }

    nonisolated func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        willPresent notification: UNNotification,
        withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void
    ) {
        completionHandler([.banner, .list, .sound])
    }
}

final class DisabledNotificationService: NotificationServicing {
    func authorizationStatus() async -> AppNotificationAuthorizationStatus { .disabledInDevelopment }
    func requestAuthorization() async -> Bool { false }
    func notifyNewDevice(_ device: NetworkDevice) async {}
    func notifyRiskyDevice(_ device: NetworkDevice) async {}
    func notifyTest() async throws {
        throw NotificationServiceError.disabledInDevelopment
    }
}
