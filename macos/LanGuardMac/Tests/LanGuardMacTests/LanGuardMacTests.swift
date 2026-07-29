import Testing
@testable import LanGuardMac

@Test
func arpParserParsesKnownHostLine() {
    let line = "router.local (192.168.0.1) at 1:2:3:a:b:c on en0 ifscope [ethernet]"

    let entry = ARPTableParser.parseLine(line)

    #expect(entry == ARPEntry(
        hostname: "router.local",
        ipAddress: "192.168.0.1",
        macAddress: "01:02:03:0a:0b:0c"
    ))
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
func vendorResolverFindsKnownOUI() {
    #expect(MACVendorResolver.vendor(for: "90:dd:5d:b7:bd:01") == "Apple")
}

@Test
func bundledVendorDatabaseParsesManufLines() {
    let contents = """
    # comment
    90:DD:5D Apple Apple, Inc.
    24-A1-60 Espressif Espressif Inc.
    """

    let vendors = BundledVendorDatabase.parse(contents)

    #expect(vendors["90:dd:5d"] == "Apple")
    #expect(vendors["24:a1:60"] == "Espressif")
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

    #expect(enriched.vendor == "Apple")
    #expect(enriched.name == "Apple Camera")
    #expect(enriched.iconName == "camera")
}
