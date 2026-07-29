import Foundation
import UserNotifications

@MainActor
protocol NotificationServicing: AnyObject {
    func requestAuthorization() async
    func notifyNewDevice(_ device: NetworkDevice) async
    func notifyRiskyDevice(_ device: NetworkDevice) async
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

final class NotificationService: NotificationServicing {
    private let center: UNUserNotificationCenter

    init(center: UNUserNotificationCenter) {
        self.center = center
    }

    convenience init() {
        self.init(center: .current())
    }

    func requestAuthorization() async {
        do {
            _ = try await center.requestAuthorization(options: [.alert, .sound])
        } catch {
            // Permission failures are non-fatal; the app can continue without notifications.
        }
    }

    func notifyNewDevice(_ device: NetworkDevice) async {
        await addNotification(
            identifier: "new-device-\(device.id)-\(device.lastSeen.timeIntervalSince1970)",
            title: "New device found",
            body: "\(device.name) joined at \(device.ipAddress)"
        )
    }

    func notifyRiskyDevice(_ device: NetworkDevice) async {
        let ports = device.openPorts.map(String.init).joined(separator: ", ")
        await addNotification(
            identifier: "risky-device-\(device.id)-\(device.lastSeen.timeIntervalSince1970)",
            title: "Risky ports found",
            body: "\(device.name) has high-risk ports open: \(ports)"
        )
    }

    private func addNotification(identifier: String, title: String, body: String) async {
        let content = UNMutableNotificationContent()
        content.title = title
        content.body = body
        content.sound = .default

        let request = UNNotificationRequest(
            identifier: identifier,
            content: content,
            trigger: nil
        )

        do {
            try await center.add(request)
        } catch {
            // Notification delivery failures should not block scan results.
        }
    }
}

final class DisabledNotificationService: NotificationServicing {
    func requestAuthorization() async {}
    func notifyNewDevice(_ device: NetworkDevice) async {}
    func notifyRiskyDevice(_ device: NetworkDevice) async {}
}
