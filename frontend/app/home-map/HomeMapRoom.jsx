import { ActionIcon, Box, Group, Text, Tooltip } from '@mantine/core';
import { IconArrowUpRight, IconGripVertical } from '@tabler/icons-react';

import HomeMapDeviceButton from './HomeMapDeviceButton';

export default function HomeMapRoom({
  section,
  childSections = [],
  draggedRoom,
  editMode = false,
  isNested = false,
  dropTarget,
  onDragStart,
  onDragEnd,
  onDragOverRoom,
  onDropOnRoom,
  onDragLeaveRoom,
  onMoveToRoot,
  onSelectDevice,
}) {
  const roomStatus = section.attentionCount > 0 ? 'attention' : 'healthy';
  const deviceCount = section.devices.length;
  const visibleDevices = section.visibleDevices || section.devices;
  const roomSize = childSections.length
    ? 'zone'
    : deviceCount >= 10
      ? 'large'
      : deviceCount >= 7
        ? 'wide'
        : deviceCount >= 4
          ? 'medium'
          : 'small';

  return (
    <article
      className={`home-map-room ${roomStatus} ${roomSize} ${isNested ? 'nested' : ''} ${editMode ? 'editable' : ''} ${draggedRoom === section.room ? 'dragging' : ''} ${editMode && dropTarget?.room === section.room ? `drop-${dropTarget.position}` : ''}`}
      draggable={editMode}
      onDragStart={editMode ? (event) => onDragStart(event, section.room) : undefined}
      onDragEnd={editMode ? onDragEnd : undefined}
      onDragOver={editMode ? (event) => onDragOverRoom(event, section.room) : undefined}
      onDragLeave={editMode ? onDragLeaveRoom : undefined}
      onDrop={editMode ? (event) => onDropOnRoom(event, section.room) : undefined}
    >
      {editMode && dropTarget?.room === section.room && (
        <span className="home-map-drop-label">
          {dropTarget.position === 'inside'
            ? 'Inside'
            : dropTarget.position === 'before'
              ? 'Before'
              : 'After'}
        </span>
      )}
      <Group justify="space-between" align="flex-start" gap="xs" wrap="nowrap">
        <Box className="home-map-room-title">
          <Group gap={6} wrap="nowrap">
            {editMode && (
              <span className="home-map-room-grip" aria-hidden="true">
                <IconGripVertical size={16} />
              </span>
            )}
            <Text fw={800} className="home-map-room-name">{section.room}</Text>
          </Group>
        </Box>
        {editMode && isNested && (
          <Tooltip label="Move to top level" withArrow>
            <ActionIcon
              aria-label={`Move ${section.room} to top level`}
              className="home-map-room-action"
              color="gray"
              size="sm"
              variant="subtle"
              onClick={(event) => {
                event.stopPropagation();
                onMoveToRoot(section.room);
              }}
              onMouseDown={(event) => event.stopPropagation()}
            >
              <IconArrowUpRight size={16} />
            </ActionIcon>
          </Tooltip>
        )}
      </Group>
      <div className="home-map-device-cloud">
        {visibleDevices.map((device) => (
          <HomeMapDeviceButton
            key={device.id}
            device={device}
            onSelectDevice={onSelectDevice}
          />
        ))}
      </div>
      {childSections.length > 0 && (
        <div className="home-map-child-rooms">
          {childSections.map((childSection) => (
            <HomeMapRoom
              key={childSection.room}
              section={childSection}
              childSections={childSection.children}
              draggedRoom={draggedRoom}
              editMode={editMode}
              isNested
              dropTarget={dropTarget}
              onDragStart={onDragStart}
              onDragEnd={onDragEnd}
              onDragOverRoom={onDragOverRoom}
              onDropOnRoom={onDropOnRoom}
              onDragLeaveRoom={onDragLeaveRoom}
              onMoveToRoot={onMoveToRoot}
              onSelectDevice={onSelectDevice}
            />
          ))}
        </div>
      )}
    </article>
  );
}
