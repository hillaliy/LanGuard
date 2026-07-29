import SwiftUI

struct ContentView: View {
    var body: some View {
        NavigationSplitView {
            List {
                NavigationLink {
                    DashboardView()
                } label: {
                    Label("Dashboard", systemImage: "gauge.with.dots.needle.67percent")
                }

                NavigationLink {
                    DevicesView()
                } label: {
                    Label("Devices", systemImage: "network")
                }

                NavigationLink {
                    ScanHistoryView()
                } label: {
                    Label("Scan History", systemImage: "clock.arrow.circlepath")
                }

                NavigationLink {
                    SettingsView()
                } label: {
                    Label("Settings", systemImage: "gearshape")
                }
            }
            .navigationSplitViewColumnWidth(min: 190, ideal: 220)
        } detail: {
            DashboardView()
        }
        .frame(minWidth: 980, minHeight: 640)
    }
}

#Preview {
    ContentView()
}
