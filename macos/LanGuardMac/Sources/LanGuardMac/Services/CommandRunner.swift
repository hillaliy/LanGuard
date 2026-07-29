import Foundation

protocol CommandRunning: Sendable {
    func run(_ launchPath: String, arguments: [String]) async throws -> String
}

struct CommandRunner: CommandRunning {
    func run(_ launchPath: String, arguments: [String]) async throws -> String {
        try await Task.detached(priority: .utility) {
            let process = Process()
            let pipe = Pipe()

            process.executableURL = URL(fileURLWithPath: launchPath)
            process.arguments = arguments
            process.standardOutput = pipe
            process.standardError = pipe

            try process.run()
            process.waitUntilExit()

            let data = pipe.fileHandleForReading.readDataToEndOfFile()
            let output = String(data: data, encoding: .utf8) ?? ""

            guard process.terminationStatus == 0 else {
                throw ScannerError.commandFailed(launchPath, output)
            }

            return output
        }.value
    }
}
