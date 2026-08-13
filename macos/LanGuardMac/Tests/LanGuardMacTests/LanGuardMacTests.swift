import Foundation
import Testing
@testable import LanGuardMac

@Test
func arpParserParsesKnownHostLine() {
    let line = "router.local (192.168.0.1) at 1:2:3:a:b:c on en0 ifscope [ethernet]"

    let entry = ARPTableParser.parseLine(line)

    #expect(entry == ARPEntry(
        hostname: "router",
        ipAddress: "192.168.0.1",
        macAddress: "01:02:03:0a:0b:0c"
    ))
}

@Test
func arpParserCleansHostnamesForDeviceIdentity() {
    let line = "samsung-tablet.local. (192.168.0.58) at f4:34:f0:00:c6:8c on en0 ifscope [ethernet]"

    let entry = ARPTableParser.parseLine(line)

    #expect(entry?.hostname == "samsung tablet")
}

@Test
func arpParserIgnoresInvalidLines() {
    let output = """
    not a valid arp line
    ? (192.168.0.20) at 90:dd:5d:b7:bd:01 on en0 ifscope [ethernet]
    """

    let entries = ARPTableParser.parse(output)

    #expect(entries.count == 1)
    #expect(entries.first?.hostname == nil)
    #expect(entries.first?.ipAddress == "192.168.0.20")
}

@Test
func hostnameResolverRejectsInvalidAddress() {
    #expect(HostnameResolver.resolve(ipAddress: "not-an-ip") == nil)
}

@Test
func routeParserFindsDefaultGateway() {
    let output = """
       route to: default
    destination: default
           mask: default
        gateway: 192.168.0.1
      interface: en0
    """

    #expect(RouteParser.defaultGateway(from: output) == "192.168.0.1")
}

@Test
func ipSortKeySortsNumerically() {
    let addresses = ["192.168.0.100", "192.168.0.2", "192.168.0.10"]
    let sorted = addresses.sorted { IPAddressSortKey($0) < IPAddressSortKey($1) }

    #expect(sorted == ["192.168.0.2", "192.168.0.10", "192.168.0.100"])
}

@Test
func deviceNameGuesserUsesHostnameWhenAvailable() {
    #expect(DeviceNameGuesser.displayName(hostname: "Living Room TV", macAddress: "90:dd:5d:b7:bd:01") == "Living Room TV")
}

@Test
func deviceNameGuesserFallsBackToMacSuffix() {
    #expect(DeviceNameGuesser.displayName(hostname: nil, macAddress: "90:dd:5d:b7:bd:01") == "Unknown Device BD01")
}

@Test
func deviceInventoryExportUsesEffectiveRole() throws {
    let device = NetworkDevice(
        id: "aa:bb:cc:dd:ee:ff",
        name: "Gateway",
        ipAddress: "192.168.1.1",
        macAddress: "aa:bb:cc:dd:ee:ff",
        isGateway: true
    )
    let document = DeviceInventoryDocument(devices: [device])
    let data = try JSONEncoder().encode(document)
    let payload = try JSONSerialization.jsonObject(with: data) as? [String: Any]
    let devices = payload?["devices"] as? [[String: Any]]

    #expect(devices?.first?["role"] as? String == "gateway")
}

@Test
func vendorResolverFindsKnownOUI() {
    #expect(MACVendorResolver.vendor(for: "90:dd:5d:b7:bd:01") == "Apple, Inc.")
    #expect(MACVendorResolver.vendor(for: "90:ee:c7:f8:d4:e1") == "Samsung Electronics Co., Ltd.")
    #expect(MACVendorResolver.vendor(for: "bc:5e:33:b0:02:04") == "Hangzhou Hikvision Digital Technology Co., Ltd.")
}

@Test
func vendorResolverIgnoresLocallyAdministeredMacAddresses() {
    #expect(MACVendorResolver.isLocallyAdministered("ba:e6:e0:17:66:94"))
    #expect(MACVendorResolver.vendor(for: "ba:e6:e0:17:66:94") == nil)
}

@Test
func vendorResolverPreservesObservedVendorNames() {
    #expect(
        MACVendorResolver.preferredVendor(
            macAddress: "00:11:22:33:44:55",
            observedVendor: "TP-Link Technologies Co., Ltd."
        ) == "TP-Link Technologies Co., Ltd."
    )
    #expect(
        MACVendorResolver.preferredVendor(
            macAddress: "00:11:22:33:44:55",
            observedVendor: "Hon Hai Precision Industry Co.,Ltd."
        ) == "Hon Hai Precision Industry Co.,Ltd."
    )
}

@Test
func httpMetadataProbeInfersVendorFromHTTPContent() {
    let reolink = HTTPDeviceMetadataProbe.metadata(
        headers: ["X-Manufacturer": "Reolink"],
        body: "<html><head><title>IP Camera</title></head></html>"
    )
    let hikvision = HTTPDeviceMetadataProbe.metadata(
        headers: [:],
        body: #"<html><head><meta name="manufacturer" content="Hikvision"></head></html>"#
    )
    let genericCamera = HTTPDeviceMetadataProbe.metadata(
        headers: ["Server": "Boa/0.94"],
        body: "<html><head><title>IP Camera</title></head></html>"
    )

    #expect(reolink.vendor == "Reolink")
    #expect(hikvision.vendor == "Hikvision")
    #expect(genericCamera.vendor == nil)
}

@Test
func httpMetadataProbeInfersHostnameFromHTTPContent() {
    let headerName = HTTPDeviceMetadataProbe.metadata(
        headers: ["X-Hostname": "living-room-switch"],
        body: "<html><head><title>Login</title></head></html>"
    )
    let jsonName = HTTPDeviceMetadataProbe.metadata(
        headers: [:],
        body: #"{"deviceName":"esp32-climate"}"#
    )
    let genericTitle = HTTPDeviceMetadataProbe.metadata(
        headers: [:],
        body: "<html><head><title>Login</title></head></html>"
    )

    #expect(headerName.hostname == "living room switch")
    #expect(jsonName.hostname == "esp32 climate")
    #expect(genericTitle.hostname == nil)
}

@Test
func ssdpResponseParsesHeadersAndDeviceDescriptionMetadata() {
    let response = """
    HTTP/1.1 200 OK\r
    LOCATION: http://192.168.0.31:80/device.xml\r
    SERVER: Linux/5.4 UPnP/1.0\r
    \r
    """
    let parsed = SSDPResponse.parse(response, ipAddress: "192.168.0.31")
    let description = """
    <root>
      <device>
        <friendlyName>Front Door Camera</friendlyName>
        <manufacturer>Hangzhou Hikvision Digital Technology Co., Ltd.</manufacturer>
        <modelName>IP Camera</modelName>
      </device>
    </root>
    """
    let metadata = SSDPMetadataDiscovery.metadata(fromDeviceDescription: description)

    #expect(parsed.ipAddress == "192.168.0.31")
    #expect(parsed.headers["location"] == "http://192.168.0.31:80/device.xml")
    #expect(metadata.hostname == "Front Door Camera")
    #expect(metadata.vendor == "Hangzhou Hikvision Digital Technology Co., Ltd.")
}

@Test
func snmpMetadataUsesSysNameAndSysDescr() {
    let metadata = SNMPMetadataDiscovery.metadata(
        sysName: #""Archer-BE550""#,
        sysDescr: #""TP-Link Router Archer BE550""#,
        ipAddress: "192.168.0.1"
    )

    #expect(metadata.hostname == "Archer BE550")
    #expect(metadata.vendor == "TP-Link Router Archer BE550")
}

@Test
func dnsPTRMetadataParsesDigOutput() {
    let output = """
    Apple-Watch.local.

    """

    #expect(DNSPTRMetadataDiscovery.hostname(fromDigOutput: output, ipAddress: "192.168.0.79") == "Apple Watch")
}

@Test
func mdnsReverseMetadataParsesDNSServiceOutput() {
    let output = """
    DATE: ---Wed 05 Aug 2026---
    22:15:01.000  Add     2   4 79.0.168.192.in-addr.arpa. PTR IN 0 Apple-Watch.local.
    """

    #expect(MDNSReverseMetadataDiscovery.hostname(from: output, ipAddress: "192.168.0.79") == "Apple Watch")
}

@Test
func mdnsReverseMetadataIgnoresUnrelatedDNSServiceOutput() {
    let output = """
    DATE: ---Wed 05 Aug 2026---
    22:15:01.000  Add     2   4 21.0.168.192.in-addr.arpa. PTR IN 0 Aqara-Hub.local.
    """

    #expect(MDNSReverseMetadataDiscovery.hostname(from: output, ipAddress: "192.168.0.79") == nil)
}

@Test
func multicastPTRMetadataParsesCompressedDNSResponse() {
    var response = Data()

    func appendUInt16(_ value: UInt16) {
        response.append(UInt8((value >> 8) & 0xff))
        response.append(UInt8(value & 0xff))
    }

    func appendUInt32(_ value: UInt32) {
        response.append(UInt8((value >> 24) & 0xff))
        response.append(UInt8((value >> 16) & 0xff))
        response.append(UInt8((value >> 8) & 0xff))
        response.append(UInt8(value & 0xff))
    }

    func appendName(_ name: String) {
        for label in name.split(separator: ".") {
            let bytes = Array(label.utf8)
            response.append(UInt8(bytes.count))
            response.append(contentsOf: bytes)
        }
        response.append(0x00)
    }

    appendUInt16(0x4c47)
    appendUInt16(0x8000)
    appendUInt16(0x0001)
    appendUInt16(0x0001)
    appendUInt16(0x0000)
    appendUInt16(0x0000)
    appendName("79.0.168.192.in-addr.arpa")
    appendUInt16(0x000c)
    appendUInt16(0x0001)
    response.append(contentsOf: [0xc0, 0x0c])
    appendUInt16(0x000c)
    appendUInt16(0x0001)
    appendUInt32(120)

    let hostnameStart = response.count
    appendUInt16(0)
    appendName("Apple-Watch.local")
    let hostnameLength = response.count - hostnameStart - 2
    response[hostnameStart] = UInt8((hostnameLength >> 8) & 0xff)
    response[hostnameStart + 1] = UInt8(hostnameLength & 0xff)

    #expect(LLMNRReverseMetadataDiscovery.hostname(from: response, ipAddress: "192.168.0.79") == "Apple Watch")
    #expect(MDNSPTRSocketDiscovery.hostname(from: response, ipAddress: "192.168.0.79") == "Apple Watch")
}

@Test
func multicastPTRMetadataIgnoresUnrelatedCompressedDNSResponse() {
    var response = Data()

    func appendUInt16(_ value: UInt16) {
        response.append(UInt8((value >> 8) & 0xff))
        response.append(UInt8(value & 0xff))
    }

    func appendUInt32(_ value: UInt32) {
        response.append(UInt8((value >> 24) & 0xff))
        response.append(UInt8((value >> 16) & 0xff))
        response.append(UInt8((value >> 8) & 0xff))
        response.append(UInt8(value & 0xff))
    }

    func appendName(_ name: String) {
        for label in name.split(separator: ".") {
            let bytes = Array(label.utf8)
            response.append(UInt8(bytes.count))
            response.append(contentsOf: bytes)
        }
        response.append(0x00)
    }

    appendUInt16(0x4c47)
    appendUInt16(0x8000)
    appendUInt16(0x0001)
    appendUInt16(0x0001)
    appendUInt16(0x0000)
    appendUInt16(0x0000)
    appendName("79.0.168.192.in-addr.arpa")
    appendUInt16(0x000c)
    appendUInt16(0x0001)
    appendName("21.0.168.192.in-addr.arpa")
    appendUInt16(0x000c)
    appendUInt16(0x0001)
    appendUInt32(120)

    let hostnameStart = response.count
    appendUInt16(0)
    appendName("Aqara-Hub.local")
    let hostnameLength = response.count - hostnameStart - 2
    response[hostnameStart] = UInt8((hostnameLength >> 8) & 0xff)
    response[hostnameStart + 1] = UInt8(hostnameLength & 0xff)

    #expect(LLMNRReverseMetadataDiscovery.hostname(from: response, ipAddress: "192.168.0.79") == nil)
    #expect(MDNSPTRSocketDiscovery.hostname(from: response, ipAddress: "192.168.0.79") == nil)
}

@Test
func mdnsServiceMetadataMapsARecordHostnamesToIPAddresses() {
    var response = Data()

    func appendUInt16(_ value: UInt16) {
        response.append(UInt8((value >> 8) & 0xff))
        response.append(UInt8(value & 0xff))
    }

    func appendUInt32(_ value: UInt32) {
        response.append(UInt8((value >> 24) & 0xff))
        response.append(UInt8((value >> 16) & 0xff))
        response.append(UInt8((value >> 8) & 0xff))
        response.append(UInt8(value & 0xff))
    }

    func appendName(_ name: String) {
        for label in name.split(separator: ".") {
            let bytes = Array(label.utf8)
            response.append(UInt8(bytes.count))
            response.append(contentsOf: bytes)
        }
        response.append(0x00)
    }

    appendUInt16(0)
    appendUInt16(0x8400)
    appendUInt16(0)
    appendUInt16(0)
    appendUInt16(0)
    appendUInt16(2)
    appendName("HAA-123456._hap._tcp.local")
    appendUInt16(0x0021)
    appendUInt16(0x0001)
    appendUInt32(120)
    let srvLengthStart = response.count
    appendUInt16(0)
    appendUInt16(0)
    appendUInt16(0)
    appendUInt16(5556)
    appendName("esp32-climate.local")
    let srvLength = response.count - srvLengthStart - 2
    response[srvLengthStart] = UInt8((srvLength >> 8) & 0xff)
    response[srvLengthStart + 1] = UInt8(srvLength & 0xff)

    appendName("esp32-climate.local")
    appendUInt16(0x0001)
    appendUInt16(0x0001)
    appendUInt32(120)
    appendUInt16(4)
    response.append(contentsOf: [192, 168, 0, 42])

    #expect(MDNSServiceMetadataDiscovery.hostnamesByIP(from: response)["192.168.0.42"] == "HAA 123456")
}

@Test
func mdnsServiceMetadataExtractsHomeKitInstanceFromPTROnlyResponse() {
    var response = Data()

    func appendUInt16(_ value: UInt16) {
        response.append(UInt8((value >> 8) & 0xff))
        response.append(UInt8(value & 0xff))
    }

    func appendUInt32(_ value: UInt32) {
        response.append(UInt8((value >> 24) & 0xff))
        response.append(UInt8((value >> 16) & 0xff))
        response.append(UInt8((value >> 8) & 0xff))
        response.append(UInt8(value & 0xff))
    }

    func appendName(_ name: String) {
        for label in name.split(separator: ".") {
            let bytes = Array(label.utf8)
            response.append(UInt8(bytes.count))
            response.append(contentsOf: bytes)
        }
        response.append(0x00)
    }

    appendUInt16(0)
    appendUInt16(0x8400)
    appendUInt16(0)
    appendUInt16(1)
    appendUInt16(0)
    appendUInt16(0)
    appendName("_hap._tcp.local")
    appendUInt16(0x000c)
    appendUInt16(0x0001)
    appendUInt32(120)
    let ptrLengthStart = response.count
    appendUInt16(0)
    appendName("HAA-123456._hap._tcp.local")
    let ptrLength = response.count - ptrLengthStart - 2
    response[ptrLengthStart] = UInt8((ptrLength >> 8) & 0xff)
    response[ptrLengthStart + 1] = UInt8(ptrLength & 0xff)

    #expect(MDNSServiceMetadataDiscovery.serviceHostname(from: response) == "HAA 123456")
}

@Test
func netBIOSNameDiscoveryParsesNodeStatusResponse() {
    var data = Data(repeating: 0, count: 57)
    data.append(2)
    data.append(contentsOf: Array("APPLE-WATCH    ".utf8))
    data.append(0x00)
    data.append(contentsOf: [0x00, 0x00])
    data.append(contentsOf: Array("WORKGROUP      ".utf8))
    data.append(0x00)
    data.append(contentsOf: [0x80, 0x00])

    #expect(NetBIOSNameDiscovery.hostname(fromNodeStatusResponse: data, ipAddress: "192.168.0.79") == "APPLE WATCH")
}

@Test
func hostnameResolverRejectsDNSClassAndNumericFieldsAsHostname() {
    #expect(HostnameResolver.clean("IN", ipAddress: "192.168.0.79") == nil)
    #expect(HostnameResolver.clean("0", ipAddress: "192.168.0.79") == nil)
    #expect(HostnameResolver.clean(";; connection timed out; no servers could be reached", ipAddress: "192.168.0.21") == nil)
}

@Test
func networkDeviceRejectsInvalidHostnamesAtInitialization() {
    let device = NetworkDevice(
        id: "00:11:22:33:44:55",
        name: "Device",
        ipAddress: "192.168.0.79",
        macAddress: "00:11:22:33:44:55",
        hostname: "0"
    )

    #expect(device.hostname == nil)
}

@Test
func bundledVendorDatabaseParsesManufLines() {
    let contents = """
    # comment
    90:DD:5D Apple Apple, Inc.
    24-A1-60 Espressif Espressif Inc.
    00-11-22-33-40/36 PreciseVendor Precise Vendor Ltd.
    """

    let vendors = BundledVendorDatabase.parse(contents)

    #expect(vendors["90dd5d"] == "Apple, Inc.")
    #expect(vendors["24a160"] == "Espressif Inc.")
    #expect(vendors["001122334"] == "Precise Vendor Ltd.")
}

@Test
func bundledVendorDatabaseMatchesMoreSpecificManufPrefix() {
    let contents = """
    00:11:22 Generic Generic Vendor
    00-11-22-33-40/36 PreciseVendor Precise Vendor Ltd.
    """

    let vendors = BundledVendorDatabase.parse(contents)
    let database = BundledVendorDatabase(vendors: vendors)

    #expect(database.vendor(forMACHex: "001122334abc") == "Precise Vendor Ltd.")
    #expect(database.vendor(forMACHex: "00112222abcd") == "Generic Vendor")
}

@Test
func deviceProfilerUsesVendorAndPortsForUnknownDevice() {
    let device = NetworkDevice(
        id: "90:dd:5d:b7:bd:01",
        name: "Unknown Device BD01",
        ipAddress: "192.168.0.51",
        macAddress: "90:dd:5d:b7:bd:01",
        openPorts: [554]
    )

    let enriched = DeviceProfiler.enrich(device)

    #expect(enriched.vendor == "Apple, Inc.")
    #expect(enriched.name == "Apple, Inc. Camera")
    #expect(enriched.iconName == "camera")
}

@Test
func deviceProfilerUsesUpdatedOUIForHikvisionCameraPrefix() {
    let device = NetworkDevice(
        id: "bc:5e:33:b0:02:04",
        name: "מצלמה 1",
        ipAddress: "192.168.0.31",
        macAddress: "bc:5e:33:b0:02:04",
        openPorts: [80, 443, 554, 8443]
    )

    let enriched = DeviceProfiler.enrich(device)

    #expect(enriched.vendor == "Hangzhou Hikvision Digital Technology Co., Ltd.")
    #expect(enriched.iconName == "camera")
    #expect(enriched.detectedRole == .camera)
}

@Test
func deviceProfilerClearsStaleVendorForRandomizedMacAddress() {
    let device = NetworkDevice(
        id: "ba:e6:e0:17:66:94",
        name: "Apple Device",
        ipAddress: "192.168.0.54",
        macAddress: "ba:e6:e0:17:66:94",
        vendor: "Apple"
    )

    let enriched = DeviceProfiler.enrich(device)

    #expect(enriched.vendor == nil)
    #expect(enriched.name == "Unknown Device 6694")
}

@Test
func deviceProfilerInfersAppleVendorFromHostnameForPrivateMacAddress() {
    let device = NetworkDevice(
        id: "f6:34:f0:00:c6:8d",
        name: "Unknown Device C68D",
        ipAddress: "192.168.0.79",
        macAddress: "f6:34:f0:00:c6:8d",
        hostname: "HomePod Mini"
    )

    let enriched = DeviceProfiler.enrich(device)

    #expect(enriched.vendor == "Apple, Inc.")
    #expect(enriched.iconName == "homepod")
    #expect(enriched.detectedRole == .speaker)
}

@Test
func deviceProfilerDetectsSmartHomeDeviceIcons() {
    #expect(DeviceProfiler.iconName(
        name: "Kitchen Smart Speaker",
        hostname: nil,
        vendor: nil,
        openPorts: [],
        isGateway: false
    ) == "homepod")
    #expect(DeviceProfiler.iconName(
        name: "Living Room Power Strip",
        hostname: nil,
        vendor: nil,
        openPorts: [],
        isGateway: false
    ) == "poweroutlet.strip")
    #expect(DeviceProfiler.iconName(
        name: "Living Room Hub",
        hostname: nil,
        vendor: nil,
        openPorts: [],
        isGateway: false
    ) == "point.3.connected.trianglepath.dotted")
    #expect(DeviceProfiler.iconName(
        name: "Relay Controller",
        hostname: nil,
        vendor: nil,
        openPorts: [],
        isGateway: false
    ) == "switch.2")
    #expect(DeviceProfiler.iconName(
        name: "Robot Vacuum",
        hostname: nil,
        vendor: nil,
        openPorts: [],
        isGateway: false
    ) == "robotic.vacuum")
    #expect(DeviceProfiler.iconName(
        name: "Kitchen LED Strip",
        hostname: nil,
        vendor: nil,
        openPorts: [],
        isGateway: false
    ) == "light.strip.2")
}

@Test
func deviceProfilerDetectsDeviceRoles() {
    #expect(DeviceProfiler.role(
        name: "Mesh Router",
        hostname: nil,
        vendor: nil,
        openPorts: [],
        isGateway: false
    ) == .meshRouter)
    #expect(DeviceProfiler.role(
        name: "Router",
        hostname: nil,
        vendor: nil,
        openPorts: [80, 443],
        isGateway: true
    ) == .gateway)
    #expect(DeviceProfiler.role(
        name: "Front Door",
        hostname: nil,
        vendor: nil,
        openPorts: [554],
        isGateway: false
    ) == .camera)
    #expect(DeviceProfiler.role(
        name: "Home Hub",
        hostname: nil,
        vendor: nil,
        openPorts: [],
        isGateway: false
    ) == .hub)
}
