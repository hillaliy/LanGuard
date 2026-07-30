import Foundation
import ServiceManagement

enum LaunchAtLoginService {
    static var isEnabled: Bool {
        SMAppService.mainApp.status == .enabled
    }

    static var statusText: String {
        switch SMAppService.mainApp.status {
        case .enabled:
            "Enabled"
        case .requiresApproval:
            "Requires approval in macOS System Settings"
        case .notRegistered:
            "Disabled"
        case .notFound:
            "Available after installing LanGuard as an app"
        @unknown default:
            "Unknown"
        }
    }

    static func setEnabled(_ enabled: Bool) throws {
        let appService = SMAppService.mainApp

        if enabled {
            guard appService.status != .enabled else { return }
            try appService.register()
        } else {
            guard appService.status == .enabled else { return }
            try appService.unregister()
        }
    }
}
