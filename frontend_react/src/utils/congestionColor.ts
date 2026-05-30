export function getCongestionHex(level: number | null | undefined): string {
  if (level === 0) return '#22c55e';
  if (level === 1) return '#f59e0b';
  if (level === 2) return '#ef4444';
  return '#94a3b8';
}

export function getCongestionLabel(level: number | null | undefined): string {
  if (level === 0) return 'Thông thoáng';
  if (level === 1) return 'Chậm';
  if (level === 2) return 'Kẹt xe';
  return 'Chưa rõ';
}

export function getCongestionTextClass(level: number | null | undefined): string {
  if (level === 0) return 'text-traffic-clear';
  if (level === 1) return 'text-traffic-slow';
  if (level === 2) return 'text-traffic-congested';
  return 'text-traffic-unknown';
}

export function getCongestionBgClass(level: number | null | undefined): string {
  if (level === 0) return 'bg-traffic-clear';
  if (level === 1) return 'bg-traffic-slow';
  if (level === 2) return 'bg-traffic-congested';
  return 'bg-traffic-unknown';
}
