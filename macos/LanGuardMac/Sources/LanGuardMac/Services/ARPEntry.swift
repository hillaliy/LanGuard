import Foundation

struct ARPEntry: Equatable, Sendable {
    var hostname: String?
    var hostnameSource: DeviceIdentitySource?
    var ipAddress: String
    var macAddress: String

    init(
        hostname: String?,
        hostnameSource: DeviceIdentitySource? = nil,
        ipAddress: String,
        macAddress: String
    ) {
        self.hostname = hostname
        self.hostnameSource = hostname == nil ? nil : hostnameSource
        self.ipAddress = ipAddress
        self.macAddress = macAddress
    }
}
