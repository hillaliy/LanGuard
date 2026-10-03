import { Tooltip, UnstyledButton } from '@mantine/core';

import DeviceIconStack from '../components/DeviceIconStack';
import { deviceStatus, displayDeviceName } from '../utils/device';
import { homeMapDeviceStatusClass } from '../utils/homeMap';

export default function HomeMapDeviceButton({ device, onSelectDevice }) {
  const status = deviceStatus(device);
  const risk = String(device.risk || '').toLowerCase();
  const vendor = String(device.vendor || '').trim();
  const hostname = String(device.hostname || '').trim();
  const tooltip = [
    displayDeviceName(device),
    device.ip,
    status.label,
    vendor,
    hostname,
  ].filter(Boolean).join(' · ');

  return (
    <Tooltip label={tooltip} withArrow>
      <UnstyledButton
        className={`home-map-device ${homeMapDeviceStatusClass(device)}`}
        onClick={() => onSelectDevice(device)}
        aria-label={tooltip}
      >
        <DeviceIconStack device={device} size={20} />
        {(risk === 'medium' || risk === 'high') && (
          <span className={`home-map-device-risk ${risk}`} aria-hidden="true" />
        )}
      </UnstyledButton>
    </Tooltip>
  );
}
