'use client';

import { useEffect, useMemo, useState } from 'react';
import {
  ActionIcon,
  Badge,
  Box,
  Button,
  Group,
  Modal,
  Paper,
  SegmentedControl,
  Text,
  Title,
  Tooltip,
  UnstyledButton,
} from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import {
  IconArrowUpRight,
  IconGripVertical,
  IconNetwork,
  IconRestore,
  IconSmartHome,
} from '@tabler/icons-react';

import { apiRequest } from '../api';
import DeviceIconStack from '../components/DeviceIconStack';
import { deviceStatus, displayDeviceName } from '../utils/device';
import {
  buildHomeMapRooms,
  homeMapDeviceStatusClass,
  homeMapFilterOptions,
  homeMapLayoutStorageKey,
  isHomeMapDescendant,
  normalizeHomeMapLayout,
  orderHomeMapRooms,
  unassignedRoomLabel,
} from '../utils/homeMap';

function HomeMapDeviceButton({ device, onSelectDevice }) {
  const status = deviceStatus(device);
  const risk = String(device.risk || '').toLowerCase();
  const vendor = String(device.vendor || '').trim();
  const hostname = String(device.hostname || '').trim();
  const tooltipParts = [
    displayDeviceName(device),
    device.ip,
    status.label,
    vendor,
    hostname,
  ].filter(Boolean);
  const tooltip = tooltipParts.join(' · ');

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
function HomeMapRoom({
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

export default function HomeMapView({
  devices = [],
  onSelectDevice,
  canEditLayout,
  onError,
  onSuccess,
}) {
  const [deviceFilter, setDeviceFilter] = useState('all');
  const rooms = useMemo(() => buildHomeMapRooms(devices, deviceFilter), [deviceFilter, devices]);
  const assignedRooms = useMemo(
    () => rooms.filter((section) => section.room !== unassignedRoomLabel),
    [rooms]
  );
  const unassignedSection = useMemo(
    () => rooms.find((section) => section.room === unassignedRoomLabel),
    [rooms]
  );
  const [layout, setLayout] = useState({ order: [], parents: {} });
  const [layoutEditMode, setLayoutEditMode] = useState(false);
  const [draggedRoom, setDraggedRoom] = useState(null);
  const [dropTarget, setDropTarget] = useState(null);
  const [resetModalOpened, resetModal] = useDisclosure(false);
  const [layoutLoaded, setLayoutLoaded] = useState(false);
  const [layoutSaving, setLayoutSaving] = useState(false);
  const deviceCount = rooms.reduce((total, section) => total + section.devices.length, 0);
  const roomCount = assignedRooms.length;
  const normalizedLayout = useMemo(
    () => normalizeHomeMapLayout(layout, assignedRooms),
    [assignedRooms, layout]
  );
  const orderedRooms = useMemo(
    () => orderHomeMapRooms(assignedRooms, normalizedLayout.order),
    [assignedRooms, normalizedLayout.order]
  );
  const roomTree = useMemo(() => {
    const sectionsByRoom = new Map(orderedRooms.map((section) => [
      section.room,
      { ...section, children: [] },
    ]));
    const roots = [];

    orderedRooms.forEach((section) => {
      const node = sectionsByRoom.get(section.room);
      const parentRoom = normalizedLayout.parents[section.room];
      const parentNode = sectionsByRoom.get(parentRoom);
      if (parentNode) {
        parentNode.children.push(node);
      } else {
        roots.push(node);
      }
    });

    return roots;
  }, [normalizedLayout.parents, orderedRooms]);

  useEffect(() => {
    let cancelled = false;

    async function loadLayout() {
      try {
        const payload = await apiRequest('home-map-layout/');
        const serverLayout = payload.data?.layout || {};
        const serverHasLayout = Boolean(
          serverLayout &&
          (
            (Array.isArray(serverLayout.order) && serverLayout.order.length > 0) ||
            (serverLayout.parents && Object.keys(serverLayout.parents).length > 0)
          )
        );
        let nextLayout = serverLayout;

        if (!serverHasLayout) {
          try {
            const storedLayout = JSON.parse(localStorage.getItem(homeMapLayoutStorageKey) || '{}');
            const storedHasLayout = Boolean(
              storedLayout &&
              (
                (Array.isArray(storedLayout.order) && storedLayout.order.length > 0) ||
                (storedLayout.parents && Object.keys(storedLayout.parents).length > 0)
              )
            );
            if (storedHasLayout) {
              nextLayout = storedLayout;
            }
          } catch {
            nextLayout = serverLayout;
          }
        }

        if (!cancelled) {
          setLayout(nextLayout && typeof nextLayout === 'object' ? nextLayout : { order: [], parents: {} });
          setLayoutLoaded(true);
        }
      } catch (err) {
        if (!cancelled) {
          setLayoutLoaded(true);
          onError(err);
        }
      }
    }

    loadLayout();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!layoutLoaded) {
      return;
    }

    const nextLayout = normalizeHomeMapLayout(layout, assignedRooms);
    if (
      JSON.stringify(nextLayout.order) !== JSON.stringify(layout.order) ||
      JSON.stringify(nextLayout.parents) !== JSON.stringify(layout.parents)
    ) {
      setLayout(nextLayout);
    }
  }, [assignedRooms, layout, layoutLoaded]);

  useEffect(() => {
    if (!layoutEditMode) {
      setDraggedRoom(null);
      setDropTarget(null);
    }
  }, [layoutEditMode]);

  useEffect(() => {
    if (!canEditLayout && layoutEditMode) {
      setLayoutEditMode(false);
    }
  }, [canEditLayout, layoutEditMode]);

  const updateHomeMapLayout = (updater) => {
    setLayout((currentLayout) => {
      const normalizedCurrent = normalizeHomeMapLayout(currentLayout, assignedRooms);
      return normalizeHomeMapLayout(updater(normalizedCurrent), assignedRooms);
    });
  };

  const saveHomeMapLayout = async () => {
    const nextLayout = normalizeHomeMapLayout(layout, assignedRooms);
    setLayoutSaving(true);
    try {
      const payload = await apiRequest('home-map-layout/', {
        method: 'PUT',
        body: { layout: nextLayout },
      });
      setLayout(nextLayout);
      setLayoutEditMode(false);
      try {
        localStorage.removeItem(homeMapLayoutStorageKey);
      } catch {
        // Ignore cleanup failures; DB storage is authoritative.
      }
      onSuccess(payload);
    } catch (err) {
      onError(err);
    } finally {
      setLayoutSaving(false);
    }
  };

  const toggleHomeMapEditMode = () => {
    if (!layoutEditMode) {
      setLayoutEditMode(true);
      return;
    }
    saveHomeMapLayout();
  };

  const handleRoomDragStart = (event, room) => {
    setDraggedRoom(room);
    event.dataTransfer.effectAllowed = 'move';
    event.dataTransfer.setData('text/plain', room);
  };

  const handleRoomDragEnd = () => {
    setDraggedRoom(null);
    setDropTarget(null);
  };

  const getRoomDropPosition = (event) => {
    const targetRect = event.currentTarget.getBoundingClientRect();
    const relativeY = (event.clientY - targetRect.top) / Math.max(targetRect.height, 1);
    if (relativeY < 0.25) {
      return 'before';
    }
    if (relativeY > 0.75) {
      return 'after';
    }
    return 'inside';
  };

  const handleDragOverRoom = (event, targetRoom) => {
    event.preventDefault();
    event.stopPropagation();
    const sourceRoom = event.dataTransfer.getData('text/plain') || draggedRoom;
    if (!sourceRoom || sourceRoom === targetRoom) {
      setDropTarget(null);
      return;
    }
    setDropTarget({ room: targetRoom, position: getRoomDropPosition(event) });
  };

  const handleDragLeaveRoom = (event) => {
    if (!event.currentTarget.contains(event.relatedTarget)) {
      setDropTarget(null);
    }
  };

  const handleDropOnRoom = (event, targetRoom) => {
    event.preventDefault();
    event.stopPropagation();
    const sourceRoom = event.dataTransfer.getData('text/plain') || draggedRoom;
    if (!sourceRoom || sourceRoom === targetRoom) {
      setDraggedRoom(null);
      setDropTarget(null);
      return;
    }

    const dropPosition = getRoomDropPosition(event);
    setDraggedRoom(null);
    setDropTarget(null);

    updateHomeMapLayout((currentLayout) => {
      if (isHomeMapDescendant(sourceRoom, targetRoom, currentLayout.parents)) {
        return currentLayout;
      }

      const targetParent = currentLayout.parents[targetRoom] || null;
      const order = currentLayout.order.filter((room) => room !== sourceRoom);
      const targetIndex = order.indexOf(targetRoom);
      const parents = { ...currentLayout.parents };

      if (dropPosition === 'inside') {
        order.splice(targetIndex >= 0 ? targetIndex + 1 : order.length, 0, sourceRoom);
        parents[sourceRoom] = targetRoom;
        return { order, parents };
      }

      order.splice(
        targetIndex >= 0 && dropPosition === 'after' ? targetIndex + 1 : Math.max(targetIndex, 0),
        0,
        sourceRoom
      );
      if (targetParent) {
        parents[sourceRoom] = targetParent;
      } else {
        delete parents[sourceRoom];
      }
      return { order, parents };
    });
  };

  const handleDropOnBuilding = (event) => {
    event.preventDefault();
    setDropTarget(null);
    const sourceRoom = event.dataTransfer.getData('text/plain') || draggedRoom;
    if (!sourceRoom) {
      setDraggedRoom(null);
      return;
    }
    setDraggedRoom(null);

    updateHomeMapLayout((currentLayout) => {
      const parents = { ...currentLayout.parents };
      delete parents[sourceRoom];
      const order = currentLayout.order.filter((room) => room !== sourceRoom);
      order.push(sourceRoom);
      return { order, parents };
    });
  };

  const moveRoomToRoot = (room) => {
    updateHomeMapLayout((currentLayout) => {
      const parents = { ...currentLayout.parents };
      delete parents[room];
      const order = currentLayout.order.filter((item) => item !== room);
      order.push(room);
      return { order, parents };
    });
  };

  const resetHomeMapLayout = () => {
    setDraggedRoom(null);
    setDropTarget(null);
    setLayout({ order: [], parents: {} });
    resetModal.close();
  };

  return (
    <>
      <Paper className="home-map-panel" radius="md">
        <Group justify="space-between" align="center" className="home-map-header" wrap="wrap">
          <Group gap="sm" wrap="nowrap">
            <span className="home-map-header-icon">
              <IconSmartHome size={24} />
            </span>
            <Box>
              <Title order={4}>Home Map</Title>
              <Text size="sm" c="dimmed">
                Rooms and device icons
              </Text>
            </Box>
          </Group>
          <Group gap="xs">
            <Badge variant="light" color="indigo">{roomCount} rooms</Badge>
            <Badge variant="light" color="blue">{deviceCount} devices</Badge>
          </Group>
        </Group>

        {deviceCount ? (
          <div className="home-map-house">
            <Group justify="space-between" className="home-map-controls" wrap="wrap">
              <SegmentedControl
                className="home-map-filter"
                data={homeMapFilterOptions}
                value={deviceFilter}
                onChange={setDeviceFilter}
                size="xs"
              />
              {canEditLayout && <Group gap="xs">
                {layoutEditMode && (
                  <Button
                    variant="subtle"
                    color="gray"
                    size="xs"
                    leftSection={<IconRestore size={16} />}
                    onClick={resetModal.open}
                  >
                    Reset layout
                  </Button>
                )}
              <Button
                variant={layoutEditMode ? 'filled' : 'light'}
                size="xs"
                leftSection={<IconGripVertical size={16} />}
                loading={layoutSaving}
                onClick={toggleHomeMapEditMode}
              >
                {layoutEditMode ? 'Done' : 'Edit layout'}
              </Button>
              </Group>}
            </Group>
            <section className="home-map-building">
              <div
                className={`home-map-room-grid ${layoutEditMode ? 'editing' : ''}`}
                onDragOver={layoutEditMode ? (event) => event.preventDefault() : undefined}
                onDrop={layoutEditMode ? handleDropOnBuilding : undefined}
              >
                {roomTree.map((section) => (
                  <HomeMapRoom
                    key={section.room}
                    section={section}
                    childSections={section.children}
                    draggedRoom={draggedRoom}
                    editMode={layoutEditMode}
                    dropTarget={dropTarget}
                    onDragStart={handleRoomDragStart}
                    onDragEnd={handleRoomDragEnd}
                    onDragOverRoom={handleDragOverRoom}
                    onDropOnRoom={handleDropOnRoom}
                    onDragLeaveRoom={handleDragLeaveRoom}
                    onMoveToRoot={moveRoomToRoot}
                    onSelectDevice={onSelectDevice}
                  />
                ))}
              </div>
            </section>
            {unassignedSection && (
              <section className="home-map-utility">
                <Group justify="space-between" align="center" mb="sm" wrap="nowrap">
                  <Group gap="xs" wrap="nowrap">
                    <IconNetwork size={20} />
                    <Text fw={900}>No room</Text>
                  </Group>
                </Group>
                <div className="home-map-device-cloud">
                  {(unassignedSection.visibleDevices || unassignedSection.devices).map((device) => (
                    <HomeMapDeviceButton
                      key={device.id}
                      device={device}
                      onSelectDevice={onSelectDevice}
                    />
                  ))}
                </div>
              </section>
            )}
          </div>
        ) : (
          <Text c="dimmed" ta="center" py="xl">
          No devices to show.
        </Text>
      )}
      </Paper>
      <Modal
        opened={resetModalOpened}
        onClose={resetModal.close}
        title="Reset layout?"
        centered
        size="sm"
      >
        <Text c="dimmed" mb="lg">
          This will reset the Home Map layout to the automatic arrangement.
        </Text>
        <Group justify="flex-end">
          <Button variant="default" onClick={resetModal.close}>
            Cancel
          </Button>
          <Button color="red" onClick={resetHomeMapLayout}>
            Reset layout
          </Button>
        </Group>
      </Modal>
    </>
  );
}
