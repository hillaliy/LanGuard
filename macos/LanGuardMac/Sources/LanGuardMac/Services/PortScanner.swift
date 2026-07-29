import Foundation
import Network

protocol PortScanning: Sendable {
    func scanOpenPorts(host: String, ports: [Int]) async -> [Int]
}

struct TCPPortScanner: PortScanning {
    var timeoutNanoseconds: UInt64 = 600_000_000

    func scanOpenPorts(host: String, ports: [Int]) async -> [Int] {
        await withTaskGroup(of: Int?.self) { group in
            for port in ports {
                group.addTask {
                    await isOpen(host: host, port: port) ? port : nil
                }
            }

            var openPorts: [Int] = []
            for await port in group {
                if let port {
                    openPorts.append(port)
                }
            }

            return openPorts.sorted()
        }
    }

    private func isOpen(host: String, port: Int) async -> Bool {
        guard let nwPort = NWEndpoint.Port(rawValue: UInt16(port)) else {
            return false
        }

        return await withCheckedContinuation { continuation in
            let connection = NWConnection(
                host: NWEndpoint.Host(host),
                port: nwPort,
                using: .tcp
            )
            let gate = PortScanContinuationGate()

            connection.stateUpdateHandler = { state in
                switch state {
                case .ready:
                    gate.resumeOnce(continuation, connection: connection, result: true)
                case .failed, .cancelled:
                    gate.resumeOnce(continuation, connection: connection, result: false)
                default:
                    break
                }
            }

            connection.start(queue: .global(qos: .utility))

            Task {
                try? await Task.sleep(nanoseconds: timeoutNanoseconds)
                gate.resumeOnce(continuation, connection: connection, result: false)
            }
        }
    }
}

struct DisabledPortScanner: PortScanning {
    func scanOpenPorts(host: String, ports: [Int]) async -> [Int] {
        []
    }
}

private final class PortScanContinuationGate: @unchecked Sendable {
    private let lock = NSLock()
    private var didResume = false

    func resumeOnce(
        _ continuation: CheckedContinuation<Bool, Never>,
        connection: NWConnection,
        result: Bool
    ) {
        lock.lock()
        defer { lock.unlock() }

        guard !didResume else { return }
        didResume = true
        connection.cancel()
        continuation.resume(returning: result)
    }
}
