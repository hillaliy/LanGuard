'use client';

import { useMemo, useState } from 'react';
import {
  Badge,
  Box,
  Button,
  Group,
  Modal,
  Paper,
  SegmentedControl,
  Select,
  Text,
  TextInput,
  Title,
} from '@mantine/core';
import { IconGripVertical, IconNetwork, IconPlus, IconRestore, IconSmartHome } from '@tabler/icons-react';

import {
  buildHomeMapGridSlots,
  buildHomeMapRooms,
  filterHomeMapRoomTree,
  getHomeMapVisualDropIndex,
  homeMapFilterOptions,
  unassignedRoomLabel,
} from '../utils/homeMap';
import HomeMapDeviceButton from './HomeMapDeviceButton';
import HomeMapRoom from './HomeMapRoom';
import useHomeMapLayout from './useHomeMapLayout';

export default function HomeMapView({
  devices = [],
  devicesLoaded = true,
  onSelectDevice,
  canEditLayout,
  onError,
  onSuccess,
}) {
  const [deviceFilter, setDeviceFilter] = useState('all');
  const [addRoomOpened, setAddRoomOpened] = useState(false);
  const [roomName, setRoomName] = useState('');
  const [parentRoom, setParentRoom] = useState(null);
  const [roomError, setRoomError] = useState(null);
  const [roomToRemove, setRoomToRemove] = useState(null);
  const rooms = useMemo(
    () => buildHomeMapRooms(devices, deviceFilter),
    [deviceFilter, devices]
  );
  const assignedRooms = useMemo(
    () => rooms.filter((section) => section.room !== unassignedRoomLabel),
    [rooms]
  );
  const unassignedSection = useMemo(
    () => rooms.find((section) => section.room === unassignedRoomLabel),
    [rooms]
  );
  const deviceCount = rooms.reduce((total, section) => total + section.devices.length, 0);
  const layout = useHomeMapLayout({
    assignedRooms,
    canEditLayout,
    devicesLoaded,
    onError,
    onSuccess,
  });
  const visibleRoomTree = useMemo(
    () => filterHomeMapRoomTree(layout.roomTree, deviceFilter, layout.layoutEditMode),
    [deviceFilter, layout.layoutEditMode, layout.roomTree]
  );
  const showUnassigned = Boolean(
    unassignedSection
    && (
      deviceFilter === 'all'
      || layout.layoutEditMode
      || unassignedSection.visibleDevices.length > 0
    )
  );
  const rootSlots = useMemo(
    () => buildHomeMapGridSlots(
      visibleRoomTree,
      deviceFilter === 'all' || layout.layoutEditMode ? layout.placements : {},
      {
      columns: 4,
      includeDropRow: layout.layoutEditMode,
      }
    ),
    [deviceFilter, layout.layoutEditMode, layout.placements, visibleRoomTree]
  );

  function createRoom(event) {
    event.preventDefault();
    const name = roomName.trim();
    if (!name || name.length > 100 || name === unassignedRoomLabel) {
      setRoomError('Enter a room name of 1 to 100 characters. Unassigned is reserved.');
      return;
    }
    if (layout.rooms.some((section) => section.room === name)) {
      setRoomError('A room with this name already exists.');
      return;
    }
    if (layout.customRooms.length >= 100) {
      setRoomError('A maximum of 100 custom rooms is supported.');
      return;
    }
    layout.addRoom(name, parentRoom);
    setAddRoomOpened(false);
  }

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
              <Text size="sm" c="dimmed">Rooms and device icons</Text>
            </Box>
          </Group>
          <Group gap="xs">
            <Badge variant="light" color="indigo">{layout.rooms.length} rooms</Badge>
            <Badge variant="light" color="blue">{deviceCount} devices</Badge>
          </Group>
        </Group>

        {(deviceCount > 0 || layout.rooms.length > 0 || canEditLayout) ? (
          <div className="home-map-house">
            <Group justify="space-between" className="home-map-controls" wrap="wrap">
              <SegmentedControl
                className="home-map-filter"
                data={homeMapFilterOptions}
                value={deviceFilter}
                onChange={setDeviceFilter}
                size="xs"
              />
              {canEditLayout && (
                <Group gap="xs">
                  {layout.layoutEditMode && (
                    <Button
                      variant="light"
                      size="xs"
                      leftSection={<IconPlus size={16} />}
                      disabled={!layout.layoutLoaded || !devicesLoaded || layout.layoutSaving}
                      onClick={() => {
                        setRoomName('');
                        setParentRoom(null);
                        setRoomError(null);
                        setAddRoomOpened(true);
                      }}
                    >
                      Add room
                    </Button>
                  )}
                  {layout.layoutEditMode && (
                    <Button
                      variant="subtle"
                      color="gray"
                      size="xs"
                      leftSection={<IconRestore size={16} />}
                      onClick={layout.resetModal.open}
                    >
                      Reset layout
                    </Button>
                  )}
                  <Button
                    variant={layout.layoutEditMode ? 'filled' : 'light'}
                    size="xs"
                    leftSection={<IconGripVertical size={16} />}
                    loading={layout.layoutSaving}
                    disabled={!layout.layoutLoaded || !devicesLoaded}
                    onClick={layout.toggleEditMode}
                  >
                    {layout.layoutEditMode ? 'Done' : 'Edit layout'}
                  </Button>
                </Group>
              )}
            </Group>
            {(visibleRoomTree.length > 0 || !showUnassigned) && (
              <section className="home-map-building">
                <div
                  className={`home-map-room-grid ${layout.layoutEditMode ? 'editing' : ''}`}
                  onDragOver={layout.layoutEditMode
                    ? (event) => event.preventDefault()
                    : undefined}
                  onDrop={layout.layoutEditMode ? layout.handleDropOnBuilding : undefined}
                >
                  {rootSlots.map(({ section, slot }) => section ? (
                    <HomeMapRoom
                      key={section.room}
                      section={section}
                      childSections={section.children}
                      draggedRoom={layout.draggedRoom}
                      editMode={layout.layoutEditMode}
                      placementSlot={slot}
                      placements={
                        deviceFilter === 'all' || layout.layoutEditMode
                          ? layout.placements
                          : {}
                      }
                      sizes={layout.sizes}
                      dropTarget={layout.dropTarget}
                      onDragStart={layout.handleRoomDragStart}
                      onDragEnd={layout.handleRoomDragEnd}
                      onDragOverRoom={layout.handleDragOverRoom}
                      onDropOnRoom={layout.handleDropOnRoom}
                      onDropOnSlot={layout.handleDropOnSlot}
                      onDragLeaveRoom={layout.handleDragLeaveRoom}
                      onMoveToRoot={layout.moveRoomToRoot}
                      onRoomIconChange={layout.setRoomIcon}
                      onRoomSizeChange={layout.setRoomSize}
                      customRooms={layout.customRooms}
                      onRemoveRoom={setRoomToRemove}
                      onSelectDevice={onSelectDevice}
                    />
                  ) : (
                    <button
                      key={`empty-root-${slot}`}
                      type="button"
                      className={`home-map-empty-slot root ${layout.layoutEditMode ? 'editing' : ''}`}
                      aria-label={`Place a room in top-level position ${slot + 1}`}
                      onDragOver={layout.layoutEditMode
                        ? (event) => event.preventDefault()
                        : undefined}
                      onDrop={layout.layoutEditMode
                        ? (event) => layout.handleDropOnSlot(
                          event,
                          null,
                          getHomeMapVisualDropIndex(event.currentTarget) ?? slot,
                          3
                        )
                        : undefined}
                      tabIndex={layout.layoutEditMode ? 0 : -1}
                    >
                      {layout.layoutEditMode ? <span>Drop here</span> : null}
                    </button>
                  ))}
                  {visibleRoomTree.length === 0 && (
                    <Text className="home-map-empty-filter" c="dimmed" ta="center">
                      {deviceFilter === 'all' ? 'No rooms to show.' : 'No devices match this filter.'}
                    </Text>
                  )}
                </div>
              </section>
            )}
            {showUnassigned && (
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
          <Text c="dimmed" ta="center" py="xl">No devices to show.</Text>
        )}
      </Paper>
      <Modal opened={addRoomOpened} onClose={() => setAddRoomOpened(false)} title="Add room" centered size="sm">
        <form onSubmit={createRoom}>
          <TextInput
            label="Room name"
            value={roomName}
            onChange={(event) => { setRoomName(event.currentTarget.value); setRoomError(null); }}
            error={roomError}
            maxLength={100}
            required
            data-autofocus
          />
          <Select
            label="Parent room"
            placeholder="Top level"
            data={layout.rooms.map((section) => section.room)}
            value={parentRoom}
            onChange={setParentRoom}
            searchable
            clearable
            mt="md"
          />
          <Group justify="flex-end" mt="lg">
            <Button variant="default" onClick={() => setAddRoomOpened(false)}>Cancel</Button>
            <Button type="submit">Add room</Button>
          </Group>
        </form>
      </Modal>
      <Modal opened={roomToRemove !== null} onClose={() => setRoomToRemove(null)} title="Delete room?" centered size="sm">
        <Text mb="lg">Delete {roomToRemove}? Nested rooms will be moved up one level. Devices will not be changed.</Text>
        <Group justify="flex-end">
          <Button variant="default" onClick={() => setRoomToRemove(null)}>Cancel</Button>
          <Button color="red" onClick={() => {
            layout.removeRoom(roomToRemove);
            setRoomToRemove(null);
          }}>Delete room</Button>
        </Group>
      </Modal>
      <Modal
        opened={layout.resetModalOpened}
        onClose={layout.resetModal.close}
        title="Reset layout?"
        centered
        size="sm"
      >
        <Text c="dimmed" mb="lg">
          This will reset the room order, positions, sizes, nesting, and icons to the automatic arrangement. Custom rooms will be kept.
        </Text>
        <Group justify="flex-end">
          <Button variant="default" onClick={layout.resetModal.close}>Cancel</Button>
          <Button color="red" onClick={layout.resetLayout}>Reset layout</Button>
        </Group>
      </Modal>
    </>
  );
}
