// swift-tools-version: 6.3

import PackageDescription

let package = Package(
    name: "LanGuardMac",
    platforms: [
        .macOS("26.0"),
    ],
    products: [
        .executable(
            name: "LanGuardMac",
            targets: ["LanGuardMac"]
        ),
    ],
    targets: [
        .executableTarget(
            name: "LanGuardMac"
        ),
        .testTarget(
            name: "LanGuardMacTests",
            dependencies: ["LanGuardMac"]
        ),
    ]
)
