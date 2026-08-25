import Foundation

enum ExternalLinkValidator {
    static func normalizedString(_ value: String?) -> String? {
        let trimmed = value?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        guard !trimmed.isEmpty,
              let components = URLComponents(string: trimmed),
              let scheme = components.scheme?.lowercased(),
              scheme == "http" || scheme == "https",
              components.host != nil else {
            return nil
        }
        return trimmed
    }

    static func url(_ value: String?) -> URL? {
        guard let normalized = normalizedString(value) else { return nil }
        return URL(string: normalized)
    }
}

enum WebInterfaceDetector {
    private static let portSchemes: [(port: Int, scheme: String)] = [
        (443, "https"),
        (80, "http"),
        (8443, "https"),
        (8080, "http"),
        (8000, "http"),
        (8888, "http"),
    ]

    static func candidateURLs(ipAddress: String, openPorts: [Int]) -> [URL] {
        let host = ipAddress.contains(":") ? "[\(ipAddress)]" : ipAddress
        let ports = Set(openPorts)
        return portSchemes.compactMap { entry in
            guard ports.contains(entry.port) else { return nil }
            let isDefault = (entry.scheme == "http" && entry.port == 80)
                || (entry.scheme == "https" && entry.port == 443)
            let portSuffix = isDefault ? "" : ":\(entry.port)"
            return URL(string: "\(entry.scheme)://\(host)\(portSuffix)")
        }
    }

    static func detect(ipAddress: String, openPorts: [Int]) async -> URL? {
        let delegate = LocalWebInterfaceSessionDelegate()
        let configuration = URLSessionConfiguration.ephemeral
        configuration.timeoutIntervalForRequest = 1.2
        configuration.timeoutIntervalForResource = 1.5
        let session = URLSession(configuration: configuration, delegate: delegate, delegateQueue: nil)
        defer { session.invalidateAndCancel() }

        for url in candidateURLs(ipAddress: ipAddress, openPorts: openPorts) {
            var request = URLRequest(url: url)
            request.httpMethod = "HEAD"
            request.timeoutInterval = 1.2
            request.setValue("LanGuard/1.0", forHTTPHeaderField: "User-Agent")
            do {
                let (_, response) = try await session.data(for: request)
                if response is HTTPURLResponse {
                    return url
                }
            } catch {
                continue
            }
        }
        return nil
    }
}

private final class LocalWebInterfaceSessionDelegate: NSObject, URLSessionDelegate, @unchecked Sendable {
    func urlSession(
        _ session: URLSession,
        didReceive challenge: URLAuthenticationChallenge,
        completionHandler: @escaping (URLSession.AuthChallengeDisposition, URLCredential?) -> Void
    ) {
        guard challenge.protectionSpace.authenticationMethod == NSURLAuthenticationMethodServerTrust,
              let trust = challenge.protectionSpace.serverTrust else {
            completionHandler(.performDefaultHandling, nil)
            return
        }
        completionHandler(.useCredential, URLCredential(trust: trust))
    }
}
