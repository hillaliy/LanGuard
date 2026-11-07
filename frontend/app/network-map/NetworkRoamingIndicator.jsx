import { Tooltip } from '@mantine/core';
import { IconArrowsShuffle } from '@tabler/icons-react';

export default function NetworkRoamingIndicator() {
  return <Tooltip multiline w={260} events={{ hover: true, focus: true, touch: true }}
    label="Mobile devices without a fixed router assignment. Roaming between access points has not been automatically detected.">
    <span className="network-roaming-indicator" tabIndex={0} role="img" aria-label="Roaming devices - no fixed access point">
      <IconArrowsShuffle size={19} aria-hidden="true" />
    </span>
  </Tooltip>;
}
