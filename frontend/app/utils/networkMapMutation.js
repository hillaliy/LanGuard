function matchingConnection(link, body) {
  const port = (value) => (value || '').trim();
  const forward = link.source === body.source && link.target === body.target
    && port(link.source_port) === port(body.source_port) && port(link.target_port) === port(body.target_port);
  const reverse = link.source === body.target && link.target === body.source
    && port(link.source_port) === port(body.target_port) && port(link.target_port) === port(body.source_port);
  return (forward || reverse) && link.kind === (body.kind || 'unknown') && port(link.label) === port(body.label);
}

export function networkMapMutationMatches(snapshot, path, method, body, previous) {
  if (path === 'links/' && method === 'POST') return snapshot.links.some((link) => matchingConnection(link, body));
  if (path === 'links/bulk/' && method === 'POST') {
    return body.connections.length > 0 && body.connections.every((item) => snapshot.links.some((link) => matchingConnection(link, item)));
  }
  const linkId = path.match(/^links\/(\d+)\/$/);
  if (linkId) {
    const link = snapshot.links.find((item) => item.id === Number(linkId[1]));
    if (method === 'DELETE') return !link;
    return Boolean(link && link.revision > body.revision && matchingConnection(link, body));
  }
  if (path === 'layout/' && method === 'PUT') {
    return snapshot.layout.revision > body.revision && Object.entries(body.positions).every(([id, point]) =>
      snapshot.layout.positions[id]?.x === point.x && snapshot.layout.positions[id]?.y === point.y);
  }
  if (path === 'suggestions/restored/' && method === 'DELETE') return snapshot.dismissed_count === 0;
  const suggestion = path.match(/^suggestions\/([^/]+)\/(accept|dismiss)\/$/);
  if (suggestion) {
    const original = previous.suggestions.find((item) => item.key === suggestion[1]);
    if (!original) return false;
    if (suggestion[2] === 'dismiss') return !snapshot.suggestions.some((item) => item.key === original.key);
    return snapshot.links.some((link) => link.origin === 'lldp' && matchingConnection(link, original));
  }
  return false;
}
