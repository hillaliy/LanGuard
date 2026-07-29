import Foundation

enum RouteParser {
    static func defaultGateway(from output: String) -> String? {
        output
            .split(whereSeparator: \.isNewline)
            .compactMap { line -> String? in
                let trimmed = line.trimmingCharacters(in: .whitespaces)
                guard trimmed.hasPrefix("gateway:") else { return nil }
                return trimmed.replacingOccurrences(of: "gateway:", with: "")
                    .trimmingCharacters(in: .whitespaces)
            }
            .first
    }
}
