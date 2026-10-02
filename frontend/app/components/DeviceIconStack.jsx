import {
  IconAirConditioning,
  IconBlind,
  IconBulb,
  IconBulbFilled,
  IconCast,
  IconCircuitSwitchClosed,
  IconDeviceCctv,
  IconDeviceDesktop,
  IconDeviceGamepad2,
  IconDeviceLaptop,
  IconDeviceMobile,
  IconDeviceSpeaker,
  IconDeviceTablet,
  IconDeviceTv,
  IconDeviceWatch,
  IconLamp,
  IconLine,
  IconLock,
  IconMeterCube,
  IconOutlet,
  IconPlugConnected,
  IconPrinter,
  IconPropeller,
  IconQuestionMark,
  IconRouter,
  IconServer,
  IconServer2,
  IconSmartHome,
  IconTemperature,
  IconVacuumCleaner,
  IconWindmill,
  IconWindow,
} from '@tabler/icons-react';

export const deviceIconOptions = [
  { value: 'unknown', label: 'Unknown', icon: IconQuestionMark },
  { value: 'desktop', label: 'Desktop', icon: IconDeviceDesktop },
  { value: 'game-console', label: 'Game console', icon: IconDeviceGamepad2 },
  { value: 'router', label: 'Router', icon: IconRouter },
  { value: 'smart-hub', label: 'Smart hub', icon: IconSmartHome },
  { value: 'phone', label: 'Phone', icon: IconDeviceMobile },
  { value: 'tablet', label: 'Tablet', icon: IconDeviceTablet },
  { value: 'smart-watch', label: 'Smart watch', icon: IconDeviceWatch },
  { value: 'laptop', label: 'Laptop', icon: IconDeviceLaptop },
  { value: 'nas', label: 'NAS', icon: IconServer2 },
  { value: 'tv', label: 'TV', icon: IconDeviceTv },
  { value: 'streamer', label: 'Streamer', icon: IconCast },
  { value: 'security-camera', label: 'Security camera', icon: IconDeviceCctv },
  { value: 'shutter', label: 'Shutter', icon: IconWindow },
  { value: 'blinds', label: 'Blinds', icon: IconBlind },
  { value: 'light', label: 'Light', icon: IconBulb },
  { value: 'led-strip', label: 'LED strip', icon: IconLine },
  { value: 'desk-lamp', label: 'Desk lamp', icon: IconLamp },
  { value: 'ceiling-light', label: 'Ceiling light', icon: IconBulbFilled },
  { value: 'air-conditioner', label: 'Air conditioner', icon: IconAirConditioning },
  { value: 'fan', label: 'Fan', icon: IconPropeller },
  { value: 'ceiling-fan', label: 'Ceiling fan', icon: IconWindmill },
  { value: 'thermostat', label: 'Thermostat', icon: IconTemperature },
  { value: 'speaker', label: 'Speaker', icon: IconDeviceSpeaker },
  { value: 'printer', label: 'Printer', icon: IconPrinter },
  { value: 'lock', label: 'Lock', icon: IconLock },
  { value: 'robot-vacuum', label: 'Robot vacuum', icon: IconVacuumCleaner },
  { value: 'power-strip', label: 'Power strip', icon: IconOutlet },
  { value: 'smart-relay', label: 'Smart relay', icon: IconCircuitSwitchClosed },
  { value: 'smart-power-strip', label: 'Smart power strip', icon: IconPlugConnected },
  { value: 'power-meter', label: 'Power meter', icon: IconMeterCube },
  { value: 'server', label: 'Server', icon: IconServer },
];

export function normalizeDeviceIcon(value) {
  const aliases = {
    plus: 'unknown',
    device: 'desktop',
    computer: 'desktop',
    desktopcomputer: 'desktop',
    hub: 'smart-hub',
    'smart-hub': 'smart-hub',
    smarthub: 'smart-hub',
    'smart-home': 'smart-hub',
    smarthome: 'smart-hub',
    aqara: 'smart-hub',
    aqura: 'smart-hub',
    cpu: 'smart-hub',
    'point.3.connected.trianglepath.dotted': 'smart-hub',
    'sensor.tag.radiowaves.forward': 'smart-hub',
    'switch.2': 'smart-hub',
    mobile: 'phone',
    iphone: 'phone',
    ipad: 'tablet',
    pad: 'tablet',
    applewatch: 'smart-watch',
    watch: 'smart-watch',
    smartwatch: 'smart-watch',
    'smart-watch': 'smart-watch',
    wearable: 'smart-watch',
    macbook: 'laptop',
    console: 'game-console',
    gameconsole: 'game-console',
    'game-console': 'game-console',
    gamepad: 'game-console',
    playstation: 'game-console',
    xbox: 'game-console',
    television: 'tv',
    airplayvideo: 'streamer',
    cast: 'streamer',
    streaming: 'streamer',
    camera: 'security-camera',
    cctv: 'security-camera',
    'video.doorbell': 'security-camera',
    blind: 'blinds',
    'blinds.horizontal.closed': 'shutter',
    shade: 'blinds',
    curtain: 'blinds',
    window: 'shutter',
    'window.shade.closed': 'blinds',
    'roller-shutter': 'shutter',
    rollershutter: 'shutter',
    bulb: 'light',
    lightbulb: 'light',
    'lightbulb.max': 'light',
    'light.panel': 'light',
    'lightswitch.on': 'light',
    led: 'led-strip',
    'led-strip': 'led-strip',
    ledstrip: 'led-strip',
    'light-strip': 'led-strip',
    lightstrip: 'led-strip',
    'strip-light': 'led-strip',
    striplight: 'led-strip',
    'light.strip.2': 'led-strip',
    lamp: 'desk-lamp',
    'lamp.desk': 'desk-lamp',
    'desk-lamp': 'desk-lamp',
    desklamp: 'desk-lamp',
    'table-lamp': 'desk-lamp',
    tablelamp: 'desk-lamp',
    'lamp.ceiling': 'ceiling-light',
    'light.recessed': 'ceiling-light',
    'ceiling-light': 'ceiling-light',
    ceilinglight: 'ceiling-light',
    downlight: 'ceiling-light',
    'air.conditioner.horizontal': 'air-conditioner',
    aircon: 'air-conditioner',
    ac: 'air-conditioner',
    hvac: 'air-conditioner',
    propeller: 'fan',
    'standing-fan': 'fan',
    'floor-fan': 'fan',
    ceilingfan: 'ceiling-fan',
    'cilling-fan': 'ceiling-fan',
    cillingfan: 'ceiling-fan',
    'fan.ceiling': 'ceiling-fan',
    'thermometer.medium': 'thermostat',
    'thermometer-snow': 'thermostat',
    temperature: 'thermostat',
    audio: 'speaker',
    hifispeaker: 'speaker',
    homepod: 'speaker',
    security: 'lock',
    smartlock: 'lock',
    'smart-lock': 'lock',
    lock: 'lock',
    printer: 'printer',
    vacuum: 'robot-vacuum',
    roomba: 'robot-vacuum',
    robot: 'robot-vacuum',
    'robotic.vacuum': 'robot-vacuum',
    'vacuum-cleaner': 'robot-vacuum',
    outlet: 'power-strip',
    socket: 'power-strip',
    plug: 'power-strip',
    powerplug: 'power-strip',
    'poweroutlet.strip': 'power-strip',
    'poweroutlet.type.h': 'power-strip',
    'smart-plug': 'power-strip',
    'plug-strip': 'power-strip',
    'power-outlet': 'power-strip',
    nas: 'nas',
    'network-attached-storage': 'nas',
    relay: 'smart-relay',
    smartrelay: 'smart-relay',
    'smart-relay': 'smart-relay',
    smartpowerstrip: 'smart-power-strip',
    'smart-power-strip': 'smart-power-strip',
    'multi-plug': 'smart-power-strip',
    powermeter: 'power-meter',
    'power-meter': 'power-meter',
    'energy-meter': 'power-meter',
    'server.rack': 'server',
    'wifi.router': 'router',
  };
  const normalized = aliases[value] || value || 'unknown';
  return deviceIconOptions.some((option) => option.value === normalized)
    ? normalized
    : 'unknown';
}

export function DeviceIcon({ value, size = 18 }) {
  const normalized = normalizeDeviceIcon(value);
  const option =
    deviceIconOptions.find((item) => item.value === normalized) ||
    deviceIconOptions[0];
  const Icon = option.icon;
  return <Icon size={size} stroke={1.8} />;
}

function deviceDisplayIcons(device) {
  const primaryIcon = normalizeDeviceIcon(device?.icon);
  const secondaryIcon = normalizeDeviceIcon(device?.secondary_icon);

  if (!secondaryIcon || secondaryIcon === 'unknown' || secondaryIcon === primaryIcon) {
    return [primaryIcon];
  }

  return [primaryIcon, secondaryIcon];
}

export default function DeviceIconStack({ device, size = 18, className = '' }) {
  const icons = deviceDisplayIcons(device);

  return (
    <span className={`device-icon-stack ${icons.length > 1 ? 'has-secondary' : ''} ${className}`.trim()}>
      {icons.map((icon) => (
        <DeviceIcon key={icon} value={icon} size={size} />
      ))}
    </span>
  );
}
