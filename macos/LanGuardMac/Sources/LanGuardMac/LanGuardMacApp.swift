import SwiftUI

@main
struct LanGuardMacApp: App {
    @State private var appModel = AppModel()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environment(appModel)
                .task {
                    await appModel.prepareNotifications()
                }
        }
        .windowStyle(.hiddenTitleBar)

        Settings {
            SettingsView()
        }
    }
}
