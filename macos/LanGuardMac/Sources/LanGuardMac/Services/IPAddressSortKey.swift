import Foundation

struct IPAddressSortKey: Comparable, Sendable {
    private let value: UInt32

    init(_ address: String) {
        let parts = address.split(separator: ".").compactMap { UInt32($0) }

        guard parts.count == 4 else {
            value = UInt32.max
            return
        }

        value = parts.reduce(UInt32(0)) { result, part in
            (result << 8) + min(part, 255)
        }
    }

    static func < (left: IPAddressSortKey, right: IPAddressSortKey) -> Bool {
        left.value < right.value
    }
}
