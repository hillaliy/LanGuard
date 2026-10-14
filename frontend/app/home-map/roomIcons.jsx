import { ActionIcon, Popover, SimpleGrid, Text, UnstyledButton } from '@mantine/core';
import {
  IconBath,
  IconBed,
  IconBox,
  IconBriefcase,
  IconCarGarage,
  IconDoorEnter,
  IconHome,
  IconPlant2,
  IconServer,
  IconSofa,
  IconStairsDown,
  IconTable,
  IconToolsKitchen2,
  IconTrees,
  IconWash,
} from '@tabler/icons-react';

import { homeMapRoomIconOptions } from '../utils/homeMap';

export const defaultHomeMapRoomIcon = 'home';

const roomIconComponents = {
  home: IconHome,
  'living-room': IconSofa,
  bedroom: IconBed,
  kitchen: IconToolsKitchen2,
  'dining-room': IconTable,
  office: IconBriefcase,
  bathroom: IconBath,
  entrance: IconDoorEnter,
  garage: IconCarGarage,
  basement: IconStairsDown,
  garden: IconPlant2,
  outside: IconTrees,
  laundry: IconWash,
  storage: IconBox,
  'server-room': IconServer,
};

const roomIconsByValue = new Map(
  homeMapRoomIconOptions.map((option) => [option.value, option])
);

export function HomeMapRoomIcon({ icon = defaultHomeMapRoomIcon, size = 18 }) {
  const Icon = roomIconComponents[icon] || IconHome;
  return <Icon size={size} stroke={1.8} aria-hidden="true" />;
}

export function HomeMapRoomIconPicker({ room, value, onChange }) {
  const selected = roomIconsByValue.get(value) || roomIconsByValue.get(defaultHomeMapRoomIcon);

  return (
    <Popover position="bottom-start" shadow="md" width={300} withinPortal>
      <Popover.Target>
        <ActionIcon
          aria-label={`Choose an icon for ${room}. Current icon: ${selected.label}`}
          className="home-map-room-icon-button"
          size="md"
          variant="subtle"
          onClick={(event) => event.stopPropagation()}
          onMouseDown={(event) => event.stopPropagation()}
        >
          <HomeMapRoomIcon icon={selected.value} size={19} />
        </ActionIcon>
      </Popover.Target>
      <Popover.Dropdown className="home-map-room-icon-menu">
        <Text fw={700} size="sm" mb="xs">Room icon</Text>
        <SimpleGrid cols={4} spacing={6}>
          {homeMapRoomIconOptions.map((option) => (
            <UnstyledButton
              key={option.value}
              aria-label={`Use ${option.label} icon for ${room}`}
              aria-pressed={selected.value === option.value}
              className={`home-map-room-icon-option ${selected.value === option.value ? 'selected' : ''}`}
              title={option.label}
              onClick={(event) => {
                event.stopPropagation();
                onChange(option.value);
              }}
              onMouseDown={(event) => event.stopPropagation()}
            >
              <HomeMapRoomIcon icon={option.value} size={21} />
              <span>{option.label}</span>
            </UnstyledButton>
          ))}
        </SimpleGrid>
      </Popover.Dropdown>
    </Popover>
  );
}
