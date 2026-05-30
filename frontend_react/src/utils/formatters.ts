export function fmtTimestampVN(iso: string | null | undefined): string {
  if (!iso) return 'N/A';
  try {
    const d = new Date(iso);
    // Convert to Vietnam timezone UTC+7
    const vnTime = new Date(d.getTime() + 7 * 60 * 60 * 1000);
    const yyyy = vnTime.getUTCFullYear();
    const mm = String(vnTime.getUTCMonth() + 1).padStart(2, '0');
    const dd = String(vnTime.getUTCDate()).padStart(2, '0');
    const hh = String(vnTime.getUTCHours()).padStart(2, '0');
    const min = String(vnTime.getUTCMinutes()).padStart(2, '0');
    const ss = String(vnTime.getUTCSeconds()).padStart(2, '0');
    return `${yyyy}-${mm}-${dd} ${hh}:${min}:${ss} +07`;
  } catch (e) {
    return 'N/A';
  }
}

export function normalizeVN(text: string | null | undefined): string {
  if (!text) return '';
  return text
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/đ/g, 'd')
    .replace(/Đ/g, 'D');
}
