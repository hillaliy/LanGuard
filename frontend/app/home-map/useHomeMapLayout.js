import { useEffect, useMemo, useState } from 'react';
import { useDisclosure } from '@mantine/hooks';

import { apiRequest } from '../api';
import {
  homeMapLayoutStorageKey,
  isHomeMapDescendant,
  moveHomeMapRoomToSlot,
  normalizeHomeMapLayout,
  orderHomeMapRooms,
} from '../utils/homeMap';

function getRoomDropPosition(event) {
  const targetRect = event.currentTarget.getBoundingClientRect();
  const relativeY = (event.clientY - targetRect.top) / Math.max(targetRect.height, 1);
  if (relativeY < 0.25) return 'before';
  if (relativeY > 0.75) return 'after';
  return 'inside';
}

export default function useHomeMapLayout({
  assignedRooms,
  canEditLayout,
  devicesLoaded,
  onError,
  onSuccess,
}) {
  const [layout, setLayout] = useState({
    order: [], parents: {}, icons: {}, placements: {}, sizes: {},
  });
  const [layoutEditMode, setLayoutEditMode] = useState(false);
  const [draggedRoom, setDraggedRoom] = useState(null);
  const [dropTarget, setDropTarget] = useState(null);
  const [resetModalOpened, resetModal] = useDisclosure(false);
  const [layoutLoaded, setLayoutLoaded] = useState(false);
  const [layoutSaving, setLayoutSaving] = useState(false);
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
      {
        ...section,
        children: [],
        roomIcon: normalizedLayout.icons[section.room] || 'home',
      },
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
  }, [normalizedLayout.icons, normalizedLayout.parents, orderedRooms]);

  useEffect(() => {
    let cancelled = false;

    async function loadLayout() {
      try {
        const payload = await apiRequest('home-map-layout/');
        const serverLayout = payload.data?.layout || {};
        let nextLayout = serverLayout;

        try {
          const storedValue = localStorage.getItem(homeMapLayoutStorageKey);
          const storedLayout = storedValue === null ? null : JSON.parse(storedValue);
          if (storedLayout && typeof storedLayout === 'object') nextLayout = storedLayout;
        } catch {
          nextLayout = serverLayout;
        }

        if (!cancelled) {
          setLayout(
            nextLayout && typeof nextLayout === 'object'
              ? nextLayout
              : { order: [], parents: {}, icons: {}, placements: {}, sizes: {} }
          );
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
    if (!layoutLoaded || !devicesLoaded) return;
    const nextLayout = normalizeHomeMapLayout(layout, assignedRooms);
    if (
      JSON.stringify(nextLayout.order) !== JSON.stringify(layout.order)
      || JSON.stringify(nextLayout.parents) !== JSON.stringify(layout.parents)
      || JSON.stringify(nextLayout.icons) !== JSON.stringify(layout.icons)
      || JSON.stringify(nextLayout.placements) !== JSON.stringify(layout.placements)
      || JSON.stringify(nextLayout.sizes) !== JSON.stringify(layout.sizes)
    ) {
      setLayout(nextLayout);
    }
  }, [assignedRooms, devicesLoaded, layout, layoutLoaded]);

  useEffect(() => {
    if (!layoutEditMode) {
      setDraggedRoom(null);
      setDropTarget(null);
    }
  }, [layoutEditMode]);

  useEffect(() => {
    if (!canEditLayout && layoutEditMode) setLayoutEditMode(false);
  }, [canEditLayout, layoutEditMode]);

  function updateLayout(updater) {
    setLayout((currentLayout) => {
      const normalizedCurrent = normalizeHomeMapLayout(currentLayout, assignedRooms);
      const nextLayout = normalizeHomeMapLayout(updater(normalizedCurrent), assignedRooms);
      try {
        localStorage.setItem(homeMapLayoutStorageKey, JSON.stringify(nextLayout));
      } catch {
        // The server save on Done remains available when local storage is unavailable.
      }
      return nextLayout;
    });
  }

  async function saveLayout() {
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
        // Database storage remains authoritative if local cleanup is unavailable.
      }
      onSuccess(payload);
    } catch (err) {
      onError(err);
    } finally {
      setLayoutSaving(false);
    }
  }

  function toggleEditMode() {
    if (!layoutEditMode) {
      setLayoutEditMode(true);
      return;
    }
    saveLayout();
  }

  function handleRoomDragStart(event, room) {
    event.stopPropagation();
    setDraggedRoom(room);
    event.dataTransfer.effectAllowed = 'move';
    event.dataTransfer.setData('text/plain', room);
  }

  function handleRoomDragEnd(event) {
    event?.stopPropagation();
    setDraggedRoom(null);
    setDropTarget(null);
  }

  function handleDragOverRoom(event, targetRoom) {
    event.preventDefault();
    event.stopPropagation();
    const sourceRoom = event.dataTransfer.getData('text/plain') || draggedRoom;
    if (!sourceRoom || sourceRoom === targetRoom) {
      setDropTarget(null);
      return;
    }
    setDropTarget({ room: targetRoom, position: getRoomDropPosition(event) });
  }

  function handleDragLeaveRoom(event) {
    if (!event.currentTarget.contains(event.relatedTarget)) setDropTarget(null);
  }

  function handleDropOnRoom(event, targetRoom) {
    event.preventDefault();
    event.stopPropagation();
    const sourceRoom = event.dataTransfer.getData('text/plain') || draggedRoom;
    if (!sourceRoom || sourceRoom === targetRoom) {
      handleRoomDragEnd();
      return;
    }

    const dropPosition = getRoomDropPosition(event);
    handleRoomDragEnd();
    updateLayout((currentLayout) => {
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
        const placements = { ...currentLayout.placements };
        delete placements[sourceRoom];
        return { ...currentLayout, order, parents, placements };
      }

      order.splice(
        targetIndex >= 0 && dropPosition === 'after'
          ? targetIndex + 1
          : Math.max(targetIndex, 0),
        0,
        sourceRoom
      );
      if (targetParent) {
        parents[sourceRoom] = targetParent;
      } else {
        delete parents[sourceRoom];
      }
      return { ...currentLayout, order, parents };
    });
  }

  function moveRoomToSlot(sourceRoom, targetParent, targetSlot, targetSpan = null) {
    updateLayout((currentLayout) => moveHomeMapRoomToSlot(
      currentLayout,
      assignedRooms,
      sourceRoom,
      targetParent,
      targetSlot,
      targetSpan
    ));
  }

  function handleDropOnSlot(event, targetParent, targetSlot, targetSpan = null) {
    event.preventDefault();
    event.stopPropagation();
    const sourceRoom = event.dataTransfer.getData('text/plain') || draggedRoom;
    handleRoomDragEnd();
    if (sourceRoom) moveRoomToSlot(sourceRoom, targetParent, targetSlot, targetSpan);
  }

  function handleDropOnBuilding(event) {
    event.preventDefault();
    setDropTarget(null);
    const sourceRoom = event.dataTransfer.getData('text/plain') || draggedRoom;
    if (!sourceRoom) {
      setDraggedRoom(null);
      return;
    }
    setDraggedRoom(null);
    updateLayout((currentLayout) => {
      const parents = { ...currentLayout.parents };
      delete parents[sourceRoom];
      const placements = { ...currentLayout.placements };
      delete placements[sourceRoom];
      const order = currentLayout.order.filter((room) => room !== sourceRoom);
      order.push(sourceRoom);
      return { ...currentLayout, order, parents, placements };
    });
  }

  function moveRoomToRoot(room) {
    updateLayout((currentLayout) => {
      const parents = { ...currentLayout.parents };
      delete parents[room];
      const placements = { ...currentLayout.placements };
      delete placements[room];
      const order = currentLayout.order.filter((item) => item !== room);
      order.push(room);
      return { ...currentLayout, order, parents, placements };
    });
  }

  function setRoomIcon(room, icon) {
    updateLayout((currentLayout) => ({
      ...currentLayout,
      icons: {
        ...currentLayout.icons,
        [room]: icon,
      },
    }));
  }

  function setRoomSize(room, span) {
    updateLayout((currentLayout) => ({
      ...currentLayout,
      sizes: {
        ...currentLayout.sizes,
        [room]: span,
      },
    }));
  }

  function resetLayout() {
    setDraggedRoom(null);
    setDropTarget(null);
    setLayout({ order: [], parents: {}, icons: {}, placements: {}, sizes: {} });
    try {
      localStorage.setItem(homeMapLayoutStorageKey, JSON.stringify({
        order: [], parents: {}, icons: {}, placements: {}, sizes: {},
      }));
    } catch {
      // The reset will still be persisted when the user selects Done.
    }
    resetModal.close();
  }

  return {
    draggedRoom,
    dropTarget,
    handleDragLeaveRoom,
    handleDragOverRoom,
    handleDropOnBuilding,
    handleDropOnRoom,
    handleDropOnSlot,
    handleRoomDragEnd,
    handleRoomDragStart,
    layoutEditMode,
    placements: normalizedLayout.placements,
    layoutSaving,
    moveRoomToRoot,
    resetLayout,
    resetModal,
    resetModalOpened,
    roomTree,
    setRoomIcon,
    setRoomSize,
    sizes: normalizedLayout.sizes,
    toggleEditMode,
  };
}
