import { useEffect, useState } from 'react';
import { Box, Group, SegmentedControl, useMantineColorScheme } from '@mantine/core';
import { IconDeviceDesktop, IconMoon, IconSun } from '@tabler/icons-react';

function useHydrated() {
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    setHydrated(true);
  }, []);

  return hydrated;
}

export function ColorSchemeControl() {
  const hydrated = useHydrated();
  const { colorScheme, setColorScheme } = useMantineColorScheme();

  return (
    <SegmentedControl
      className="color-scheme-control"
      size="xs"
      value={hydrated ? colorScheme : 'auto'}
      onChange={setColorScheme}
      data={[
        {
          value: 'light',
          label: (
            <Group component="span" gap={4} wrap="nowrap">
              <IconSun size={14} />
              <Box component="span" visibleFrom="lg">Light</Box>
            </Group>
          ),
        },
        {
          value: 'dark',
          label: (
            <Group component="span" gap={4} wrap="nowrap">
              <IconMoon size={14} />
              <Box component="span" visibleFrom="lg">Dark</Box>
            </Group>
          ),
        },
        {
          value: 'auto',
          label: (
            <Group component="span" gap={4} wrap="nowrap">
              <IconDeviceDesktop size={14} />
              <Box component="span" visibleFrom="lg">Auto</Box>
            </Group>
          ),
        },
      ]}
    />
  );
}

export function formatTopbarDate(value, timeZone) {
  return new Intl.DateTimeFormat(undefined, {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    ...(timeZone ? { timeZone } : {}),
  }).format(value);
}

export function formatTopbarTime(value, timeZone) {
  return new Intl.DateTimeFormat(undefined, {
    hour: '2-digit',
    minute: '2-digit',
    ...(timeZone ? { timeZone } : {}),
  }).format(value);
}
