import { useEffect, useRef, useState } from 'react';
import { ActionIcon, Box, Group, Text, Tooltip } from '@mantine/core';
import {
  IconArrowUpRight,
  IconArrowsHorizontal,
  IconGripVertical,
} from '@tabler/icons-react';

import HomeMapDeviceButton from './HomeMapDeviceButton';
import { HomeMapRoomIcon, HomeMapRoomIconPicker } from './roomIcons';
import {
  buildHomeMapGridSlots,
  getHomeMapVisualDropIndex,
  homeMapRoomSpanOptions,
} from '../utils/homeMap';

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
  onDropOnSlot,
  onDragLeaveRoom,
  onMoveToRoot,
  onRoomIconChange,
  onRoomSizeChange,
  onSelectDevice,
  parentRoom = null,
  placementSlot = 0,
  placements = {},
  sizes = {},
}) {
  const roomRef = useRef(null);
  const [roomRowSpan, setRoomRowSpan] = useState(8);
  const [resizing, setResizing] = useState(false);
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
  const automaticSpan = roomSize === 'zone' || roomSize === 'large'
    ? 6
    : roomSize === 'wide'
      ? 4
      : 3;
  const minimumSpan = childSections.length ? 4 : 2;
  const roomSpan = Math.max(
    minimumSpan,
    sizes[section.room] || (isNested ? 4 : automaticSpan)
  );
  const childSlots = buildHomeMapGridSlots(childSections, placements, {
    columns: 3,
    includeDropRow: editMode,
  });

  useEffect(() => {
    if (!roomRef.current || typeof ResizeObserver === 'undefined') return undefined;
    const room = roomRef.current;
    const updateRowSpan = () => {
      const contentHeight = room.scrollHeight;
      const gridStyle = window.getComputedStyle(room.parentElement);
      const rowHeight = Number.parseFloat(gridStyle.gridAutoRows) || 8;
      const rowGap = Number.parseFloat(gridStyle.rowGap) || 0;
      const span = Math.ceil((contentHeight + rowGap) / (rowHeight + rowGap));
      setRoomRowSpan(Math.max(7, span));
    };
    const observer = new ResizeObserver(updateRowSpan);
    observer.observe(room);
    updateRowSpan();
    return () => observer.disconnect();
  }, [roomSpan]);

  function handleResizeStart(event) {
    event.preventDefault();
    event.stopPropagation();
    if (event.button !== 0) return;
    const grid = roomRef.current?.parentElement;
    if (!grid) return;

    const handle = event.currentTarget;
    const room = roomRef.current;
    const gridStyle = window.getComputedStyle(grid);
    const columnGap = Number.parseFloat(gridStyle.columnGap) || 0;
    const columnWidth = (grid.getBoundingClientRect().width - columnGap * 11) / 12;
    const stepWidth = Math.max(columnWidth + columnGap, 1);
    const startX = event.clientX;
    const startWidth = room.getBoundingClientRect().width;
    let lastSpan = roomSpan;
    let resizeFinished = false;
    const previousCursor = document.body.style.cursor;
    const previousUserSelect = document.body.style.userSelect;
    room.draggable = false;
    document.body.style.cursor = 'ew-resize';
    document.body.style.userSelect = 'none';
    try {
      handle.setPointerCapture(event.pointerId);
    } catch {
      // Window listeners below keep resizing available without pointer capture.
    }
    setResizing(true);

    function handlePointerMove(pointerEvent) {
      pointerEvent.preventDefault();
      const requestedWidth = Math.max(1, startWidth + pointerEvent.clientX - startX);
      const requestedSpan = Math.round((requestedWidth + columnGap) / stepWidth);
      const availableSpans = homeMapRoomSpanOptions.filter((option) => option >= minimumSpan);
      const nextSpan = availableSpans.reduce((closest, option) =>
        Math.abs(option - requestedSpan) < Math.abs(closest - requestedSpan) ? option : closest
      );
      if (nextSpan !== lastSpan) {
        lastSpan = nextSpan;
        room.style.setProperty('--home-map-room-span', nextSpan);
        onRoomSizeChange(section.room, nextSpan);
      }
    }

    function handlePointerEnd(pointerEvent) {
      if (resizeFinished) return;
      resizeFinished = true;
      if (
        Number.isInteger(pointerEvent?.pointerId)
        && handle.hasPointerCapture?.(pointerEvent.pointerId)
      ) {
        handle.releasePointerCapture(pointerEvent.pointerId);
      }
      room.draggable = editMode;
      document.body.style.cursor = previousCursor;
      document.body.style.userSelect = previousUserSelect;
      setResizing(false);
      window.removeEventListener('pointermove', handlePointerMove);
      window.removeEventListener('pointerup', handlePointerEnd);
      window.removeEventListener('pointercancel', handlePointerEnd);
      window.removeEventListener('blur', handlePointerEnd);
    }

    window.addEventListener('pointermove', handlePointerMove, { passive: false });
    window.addEventListener('pointerup', handlePointerEnd, { once: true });
    window.addEventListener('pointercancel', handlePointerEnd, { once: true });
    window.addEventListener('blur', handlePointerEnd, { once: true });
  }

  function handleRoomDrop(event) {
    const targetRect = event.currentTarget.getBoundingClientRect();
    const relativeY = (event.clientY - targetRect.top) / Math.max(targetRect.height, 1);
    if (relativeY < 0.25) {
      onDropOnSlot(event, parentRoom, placementSlot);
      return;
    }
    if (relativeY > 0.75) {
      onDropOnSlot(event, parentRoom, placementSlot + 1);
      return;
    }
    onDropOnRoom(event, section.room);
  }

  return (
    <article
      ref={roomRef}
      className={`home-map-room ${roomStatus} ${roomSize} span-${roomSpan} ${isNested ? 'nested' : ''} ${editMode ? 'editable' : ''} ${resizing ? 'resizing' : ''} ${draggedRoom === section.room ? 'dragging' : ''} ${editMode && dropTarget?.room === section.room ? `drop-${dropTarget.position}` : ''}`}
      style={{
        '--home-map-room-span': roomSpan,
        '--home-map-room-row-span': roomRowSpan,
      }}
      draggable={editMode && !resizing}
      onDragStart={editMode ? (event) => onDragStart(event, section.room) : undefined}
      onDragEnd={editMode ? onDragEnd : undefined}
      onDragOver={editMode ? (event) => onDragOverRoom(event, section.room) : undefined}
      onDragLeave={editMode ? onDragLeaveRoom : undefined}
      onDrop={editMode ? handleRoomDrop : undefined}
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
          <Group gap={6} align="flex-start" wrap="nowrap">
            {editMode && (
              <span className="home-map-room-grip" aria-hidden="true">
                <IconGripVertical size={16} />
              </span>
            )}
            {editMode ? (
              <HomeMapRoomIconPicker
                room={section.room}
                value={section.roomIcon}
                onChange={(icon) => onRoomIconChange(section.room, icon)}
              />
            ) : (
              <span className="home-map-room-icon">
                <HomeMapRoomIcon icon={section.roomIcon} size={19} />
              </span>
            )}
            <Box className="home-map-room-heading-copy">
              <Text fw={800} className="home-map-room-name">{section.room}</Text>
              <div
                className="home-map-room-summary"
                aria-label={`${deviceCount} ${deviceCount === 1 ? 'device' : 'devices'}, ${section.onlineCount} online, ${section.attentionCount} attention`}
              >
                <span className="home-map-room-summary-item">
                  <span className="home-map-room-summary-dot devices" aria-hidden="true" />
                  {deviceCount} {deviceCount === 1 ? 'device' : 'devices'}
                </span>
                <span className="home-map-room-summary-item">
                  <span className="home-map-room-summary-dot online" aria-hidden="true" />
                  {section.onlineCount} online
                </span>
                <span className={`home-map-room-summary-item ${section.attentionCount > 0 ? 'attention' : ''}`}>
                  <span className="home-map-room-summary-dot attention" aria-hidden="true" />
                  {section.attentionCount} attention
                </span>
              </div>
            </Box>
          </Group>
        </Box>
        {editMode && (
          <Group className="home-map-room-actions" gap={2} wrap="nowrap">
            {isNested && (
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
        <div className={`home-map-child-rooms ${editMode ? 'editing' : ''}`}>
          {childSlots.map(({ section: childSection, slot }) => childSection ? (
            <HomeMapRoom
              key={childSection.room}
              section={childSection}
              childSections={childSection.children}
              draggedRoom={draggedRoom}
              editMode={editMode}
              isNested
              parentRoom={section.room}
              placementSlot={slot}
              placements={placements}
              sizes={sizes}
              dropTarget={dropTarget}
              onDragStart={onDragStart}
              onDragEnd={onDragEnd}
              onDragOverRoom={onDragOverRoom}
              onDropOnRoom={onDropOnRoom}
              onDropOnSlot={onDropOnSlot}
              onDragLeaveRoom={onDragLeaveRoom}
              onMoveToRoot={onMoveToRoot}
              onRoomIconChange={onRoomIconChange}
              onRoomSizeChange={onRoomSizeChange}
              onSelectDevice={onSelectDevice}
            />
          ) : (
            <button
              key={`empty-${section.room}-${slot}`}
              type="button"
              className={`home-map-empty-slot ${editMode ? 'editing' : ''}`}
              aria-label={`Place a room in position ${slot + 1} inside ${section.room}`}
              onDragOver={editMode ? (event) => event.preventDefault() : undefined}
              onDrop={editMode
                ? (event) => onDropOnSlot(
                  event,
                  section.room,
                  getHomeMapVisualDropIndex(event.currentTarget) ?? slot,
                  4
                )
                : undefined}
              tabIndex={editMode ? 0 : -1}
            >
              {editMode ? <span>Drop here</span> : null}
            </button>
          ))}
        </div>
      )}
      {editMode && (
        <button
          type="button"
          className="home-map-room-resize-handle"
          aria-label={`Resize ${section.room}`}
          onPointerDown={handleResizeStart}
          onClick={(event) => event.stopPropagation()}
        >
          <IconArrowsHorizontal size={14} />
        </button>
      )}
    </article>
  );
}
