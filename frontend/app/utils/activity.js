export function activityRecordLabel(pagination, loadedCount) {
  const total = pagination?.count ?? loadedCount;
  if (total > loadedCount) {
    return `Latest ${loadedCount} of ${total} records`;
  }
  return `${loadedCount} records`;
}

export function hasNextActivityPage(pagination) {
  return pagination?.next_offset !== null && pagination?.next_offset !== undefined;
}

export function eventDeviceId(event) {
  const eventDevice = event?.device;
  if (eventDevice && typeof eventDevice === 'object') {
    return eventDevice.id;
  }
  return eventDevice;
}

export function appendUniqueById(current, incoming) {
  const seen = new Set(current.map((item) => item.id));
  return [
    ...current,
    ...incoming.filter((item) => {
      if (seen.has(item.id)) {
        return false;
      }
      seen.add(item.id);
      return true;
    }),
  ];
}
