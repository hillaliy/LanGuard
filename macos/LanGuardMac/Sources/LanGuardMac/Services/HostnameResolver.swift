import Foundation
import Darwin

enum HostnameResolver {
    static func resolve(ipAddress: String) -> String? {
        var address = sockaddr_in()
        address.sin_len = UInt8(MemoryLayout<sockaddr_in>.size)
        address.sin_family = sa_family_t(AF_INET)

        guard ipAddress.withCString({ inet_pton(AF_INET, $0, &address.sin_addr) }) == 1 else {
            return nil
        }

        var host = [CChar](repeating: 0, count: Int(NI_MAXHOST))
        let status: Int32 = host.withUnsafeMutableBufferPointer { hostBuffer in
            withUnsafePointer(to: &address) { pointer in
                pointer.withMemoryRebound(to: sockaddr.self, capacity: 1) {
                    getnameinfo($0, socklen_t(MemoryLayout<sockaddr_in>.size), hostBuffer.baseAddress, socklen_t(hostBuffer.count), nil, 0, NI_NAMEREQD)
                }
            }
        }

        guard status == 0 else { return nil }
        let hostname = String(decoding: host.prefix { $0 != 0 }.map { UInt8(bitPattern: $0) }, as: UTF8.self)
            .trimmingCharacters(in: .whitespacesAndNewlines)
            .trimmingCharacters(in: CharacterSet(charactersIn: "."))
        guard !hostname.isEmpty, hostname != ipAddress, !hostname.contains("in-addr.arpa") else { return nil }
        return hostname.split(separator: ".").first?.replacingOccurrences(of: "-", with: " ")
    }
}
