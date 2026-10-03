import { useEffect, useMemo, useState } from 'react';
import { useDisclosure } from '@mantine/hooks';

import { apiRequest } from '../api';
import {
  homeMapLayoutStorageKey,
  isHomeMapDescendant,
  normalizeHomeMapLayout,
  orderHomeMapRooms,
} from '../utils/homeMap';

function hasLayout(layout) {
  return Boolean(
    layout
    && (
      (Array.isArray(layout.order) && layout.order.length > 0)
      || (layout.parents && Object.keys(layout.parents).length > 0)
    )
  );
}

function getRoomDropPosition(event) {
  const targetRect = event.currentTarget.getBoundingClientRect();
  const relativeY = (event.clientY - targetRect.top) / Math.max(targetRect.height, 1);
  if (relativeY < 0.25) return 'before';
  if (relativeY > 0.75) return 'after';
  return 'inside';
}

export default function useHomeMapLayout({ assignedRooms, canEditLayout, onError, onSuccess }) {
  const [layout, setLayout] = useState({ order: [], parents: {} });
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
        let nextLayout = serverLayout;

        if (!hasLayout(serverLayout)) {
          try {
            const storedLayout = JSON.parse(
              localStorage.getItem(homeMapLayoutStorageKey) || '{}'
            );
            if (hasLayout(storedLayout)) nextLayout = storedLayout;
          } catch {
            nextLayout = serverLayout;
          }
        }

        if (!cancelled) {
          setLayout(
            nextLayout && typeof nextLayout === 'object'
              ? nextLayout
              : { order: [], parents: {} }
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
    if (!layoutLoaded) return;
    const nextLayout = normalizeHomeMapLayout(layout, assignedRooms);
    if (
      JSON.stringify(nextLayout.order) !== JSON.stringify(layout.order)
      || JSON.stringify(nextLayout.parents) !== JSON.stringify(layout.parents)
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
    if (!canEditLayout && layoutEditMode) setLayoutEditMode(false);
  }, [canEditLayout, layoutEditMode]);

  function updateLayout(updater) {
    setLayout((currentLayout) => {
      const normalizedCurrent = normalizeHomeMapLayout(currentLayout, assignedRooms);
      return normalizeHomeMapLayout(updater(normalizedCurrent), assignedRooms);
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
    setDraggedRoom(room);
    event.dataTransfer.effectAllowed = 'move';
    event.dataTransfer.setData('text/plain', room);
  }

  function handleRoomDragEnd() {
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
        return { order, parents };
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
      return { order, parents };
    });
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
      const order = currentLayout.order.filter((room) => room !== sourceRoom);
      order.push(sourceRoom);
      return { order, parents };
    });
  }

  function moveRoomToRoot(room) {
    updateLayout((currentLayout) => {
      const parents = { ...currentLayout.parents };
      delete parents[room];
      const order = currentLayout.order.filter((item) => item !== room);
      order.push(room);
      return { order, parents };
    });
  }

  function resetLayout() {
    setDraggedRoom(null);
    setDropTarget(null);
    setLayout({ order: [], parents: {} });
    resetModal.close();
  }

  return {
    draggedRoom,
    dropTarget,
    handleDragLeaveRoom,
    handleDragOverRoom,
    handleDropOnBuilding,
    handleDropOnRoom,
    handleRoomDragEnd,
    handleRoomDragStart,
    layoutEditMode,
    layoutSaving,
    moveRoomToRoot,
    resetLayout,
    resetModal,
    resetModalOpened,
    roomTree,
    toggleEditMode,
  };
}
