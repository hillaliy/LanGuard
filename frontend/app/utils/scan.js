export function normalizedScanRanges(ranges, fallbackRange = '') {
  const values = Array.isArray(ranges) ? ranges.filter(Boolean) : [];
  return values.length ? values : fallbackRange ? [fallbackRange] : [];
}

export function formatScanRange(networkRange, labels = {}) {
  const label = String(labels?.[networkRange] || '').trim();
  return label ? `${label} · ${networkRange}` : networkRange;
}

export function compactScanRangesLabel(ranges, labels = {}) {
  if (!ranges.length) return '-';
  const firstRange = formatScanRange(ranges[0], labels);
  if (ranges.length === 1) return firstRange;
  return `${firstRange} +${ranges.length - 1} more`;
}
