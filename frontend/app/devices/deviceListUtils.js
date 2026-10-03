export function isPortGuidanceInteraction(event) {
  const pathIncludesGuidance = event.nativeEvent.composedPath().some(
    (node) => node?.classList?.contains('port-guidance-control')
  );
  if (pathIncludesGuidance) return true;

  const { clientX, clientY } = event.nativeEvent;
  return Array.from(event.currentTarget.querySelectorAll('.port-guidance-control')).some(
    (node) => {
      const bounds = node.getBoundingClientRect();
      return (
        clientX >= bounds.left
        && clientX <= bounds.right
        && clientY >= bounds.top
        && clientY <= bounds.bottom
      );
    }
  );
}

export function handleDeviceRowClick(event, device, bulkEditEnabled, onToggle, onSelect) {
  if (isPortGuidanceInteraction(event)) return;
  if (bulkEditEnabled) onToggle(device);
  else onSelect(device);
}

export function handleDeviceRowKeyDown(event, device, bulkEditEnabled, onToggle, onSelect) {
  if (isPortGuidanceInteraction(event) || !['Enter', ' '].includes(event.key)) return;
  event.preventDefault();
  if (bulkEditEnabled) onToggle(device);
  else onSelect(device);
}

export function sortableOrdering(field, currentOrdering) {
  if (currentOrdering === field) return `-${field}`;
  if (currentOrdering === `-${field}`) return '';
  return field;
}

export function sortableOrderingDescendingFirst(field, currentOrdering) {
  if (currentOrdering === `-${field}`) return field;
  if (currentOrdering === field) return '';
  return `-${field}`;
}
