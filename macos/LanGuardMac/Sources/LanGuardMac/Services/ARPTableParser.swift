import Foundation

enum ARPTableParser {
    static func parse(_ output: String) -> [ARPEntry] {
        output
            .split(whereSeparator: \.isNewline)
            .compactMap { parseLine(String($0)) }
    }

    static func parseLine(_ line: String) -> ARPEntry? {
        guard let openParen = line.firstIndex(of: "("),
              let closeParen = line[openParen...].firstIndex(of: ")") else {
            return nil
        }

        let rawHostname = line[..<openParen].trimmingCharacters(in: .whitespaces)
        let hostname = rawHostname == "?" ? nil : rawHostname
        let ipAddress = String(line[line.index(after: openParen)..<closeParen])
        let remainder = line[line.index(after: closeParen)...]
        let marker = " at "

        guard let markerRange = remainder.range(of: marker) else {
            return nil
        }

        let afterMarker = remainder[markerRange.upperBound...]
        guard let rawMAC = afterMarker.split(separator: " ").first else {
            return nil
        }

        let macAddress = normalizeMAC(String(rawMAC))

        guard isValidIPv4(ipAddress), isValidMAC(macAddress) else {
            return nil
        }

        return ARPEntry(
            hostname: hostname,
            ipAddress: ipAddress,
            macAddress: macAddress
        )
    }

    private static func normalizeMAC(_ value: String) -> String {
        value
            .split(separator: ":")
            .map { part in
                part.count == 1 ? "0\(part)" : String(part)
            }
            .joined(separator: ":")
            .lowercased()
    }

    private static func isValidIPv4(_ value: String) -> Bool {
        let octets = value.split(separator: ".")
        guard octets.count == 4 else { return false }
        return octets.allSatisfy { octet in
            guard let number = Int(octet) else { return false }
            return (0...255).contains(number)
        }
    }

    private static func isValidMAC(_ value: String) -> Bool {
        value.split(separator: ":").count == 6
    }
}
