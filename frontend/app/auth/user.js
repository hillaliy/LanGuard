export function userDisplayName(user) {
  const fullName = [user?.first_name, user?.last_name].filter(Boolean).join(' ').trim();
  return fullName || user?.username || 'User';
}

export function userInitials(user) {
  const displayName = userDisplayName(user);
  const parts = displayName.split(/\s+/).filter(Boolean);
  const nameInitials =
    parts.length > 1
      ? `${parts[0][0]}${parts[parts.length - 1][0]}`
      : '';

  if (nameInitials) {
    return nameInitials.toUpperCase();
  }

  return (user?.username || 'U').trim().slice(0, 2).toUpperCase();
}

export function capitalizeName(value) {
  return (value || '')
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .map((word) => word
      .split('-')
      .map((part) => part ? `${part[0].toUpperCase()}${part.slice(1).toLowerCase()}` : part)
      .join('-'))
    .join(' ');
}
