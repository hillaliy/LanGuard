import { useState } from 'react';

const fallbackTimeZoneOptions = [
  'UTC',
  'Asia/Jerusalem',
  'Europe/London',
  'Europe/Paris',
  'Europe/Berlin',
  'America/New_York',
  'America/Chicago',
  'America/Denver',
  'America/Los_Angeles',
  'Asia/Dubai',
  'Asia/Tokyo',
  'Australia/Sydney',
];

const timeZoneOptions =
  typeof Intl !== 'undefined' && typeof Intl.supportedValuesOf === 'function'
    ? Intl.supportedValuesOf('timeZone')
    : fallbackTimeZoneOptions;

export default function useScanningSettings() {
  const [scanNetworks, setScanNetworks] = useState([
    { name: 'Primary network', cidr: '' },
  ]);
  const [scanMaxHosts, setScanMaxHosts] = useState(1024);
  const [scanInterval, setScanInterval] = useState(10);
  const [timeZone, setTimeZone] = useState('UTC');
  const [snmpEnabled, setSnmpEnabled] = useState(false);
  const [snmpConfigured, setSnmpConfigured] = useState(false);
  const [snmpCommunity, setSnmpCommunity] = useState('');
  const [snmpMaxDevices, setSnmpMaxDevices] = useState(64);

  function hydrate(data) {
    const loadedRanges =
      Array.isArray(data.scan_ranges) && data.scan_ranges.length
        ? data.scan_ranges
        : data.ip_range
          ? [data.ip_range]
          : [];
    const loadedLabels = data.scan_range_labels || {};
    setScanNetworks(
      loadedRanges.map((cidr, index) => ({
        cidr,
        name:
          loadedLabels[cidr]
          || (index === 0 ? 'Primary network' : `Network ${index + 1}`),
      }))
    );
    setScanMaxHosts(Number(data.scan_max_hosts || 1024));
    setScanInterval(data.scan_interval || 10);
    setTimeZone(data.time_zone || 'UTC');
    setSnmpEnabled(Boolean(data.snmp_enabled));
    setSnmpConfigured(Boolean(data.snmp_configured));
    setSnmpCommunity('');
    setSnmpMaxDevices(Number(data.snmp_max_devices || 64));
  }

  function buildPayload() {
    const normalizedScanNetworks = scanNetworks.map(({ name, cidr }) => ({
      name: name.trim(),
      cidr: cidr.trim(),
    }));
    const payload = {
      scan_ranges: normalizedScanNetworks.map(({ cidr }) => cidr),
      scan_range_labels: Object.fromEntries(
        normalizedScanNetworks.map(({ cidr, name }) => [cidr, name])
      ),
      scan_interval: scanInterval,
      time_zone: timeZone,
      snmp_enabled: snmpEnabled,
    };
    if (snmpCommunity) payload.snmp_community = snmpCommunity;
    return payload;
  }

  function updateScanNetwork(index, field, value) {
    setScanNetworks((current) =>
      current.map((network, networkIndex) =>
        networkIndex === index ? { ...network, [field]: value } : network
      )
    );
  }

  function addScanNetwork() {
    setScanNetworks((current) => {
      if (current.length >= 16) return current;
      return [...current, { name: `Network ${current.length + 1}`, cidr: '' }];
    });
  }

  function removeScanNetwork(index) {
    setScanNetworks((current) =>
      current.length > 1
        ? current.filter((_, networkIndex) => networkIndex !== index)
        : current
    );
  }

  return {
    hydrate,
    buildPayload,
    controller: {
      addScanNetwork,
      removeScanNetwork,
      scanInterval,
      scanMaxHosts,
      scanNetworks,
      setSnmpCommunity,
      setSnmpEnabled,
      setScanInterval,
      setTimeZone,
      timeZone,
      timeZoneOptions,
      updateScanNetwork,
      snmpCommunity,
      snmpConfigured,
      snmpEnabled,
      snmpMaxDevices,
    },
    timeZone,
  };
}
