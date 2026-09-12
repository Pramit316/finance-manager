import NepaliDate from 'nepali-date-converter';

export interface BsDate {
  year: number;
  month: number;
  date: number;
}

const BS_MONTHS = [
  'Baisakh', 'Jestha', 'Asar', 'Shrawan', 'Bhadra', 'Aswin',
  'Kartik', 'Mangsir', 'Poush', 'Magh', 'Falgun', 'Chaitra',
];

export function parseIsoDate(value: string): Date {
  const [year, month, day] = value.split('-').map(Number);
  return new Date(year, month - 1, day);
}

export function formatIsoDate(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

export function adToBs(value: string | Date): BsDate {
  const nepaliDate = new NepaliDate(typeof value === 'string' ? parseIsoDate(value) : value);
  const bs = nepaliDate.getBS();
  return { year: bs.year, month: bs.month, date: bs.date };
}

export function bsToAd(value: string): string {
  const normalized = value.trim().replace(/\//g, '-');
  const match = /^(\d{4})-(\d{1,2})-(\d{1,2})$/.exec(normalized);
  if (!match) throw new Error('Use BS format YYYY-MM-DD');
  const nepaliDate = new NepaliDate(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
  return formatIsoDate(nepaliDate.toJsDate());
}

export function formatBsDate(value: string | Date): string {
  const bs = adToBs(value);
  return `${bs.year} ${BS_MONTHS[bs.month]} ${bs.date}`;
}

export function formatAdDate(value: string): string {
  return parseIsoDate(value).toLocaleDateString('en-US', {
    year: 'numeric', month: 'short', day: 'numeric',
  });
}

export function formatDualDate(value: string): string {
  return `${formatAdDate(value)} · ${formatBsDate(value)}`;
}

export function bsInputValue(value: string): string {
  const bs = adToBs(value);
  return `${bs.year}-${String(bs.month + 1).padStart(2, '0')}-${String(bs.date).padStart(2, '0')}`;
}

export function currentBsMonthRange(today = new Date()): { from: string; to: string } {
  const current = new NepaliDate(today).getBS();
  const first = new NepaliDate(current.year, current.month, 1).toJsDate();
  const nextMonth = current.month === 11
    ? new NepaliDate(current.year + 1, 0, 1).toJsDate()
    : new NepaliDate(current.year, current.month + 1, 1).toJsDate();
  const last = new Date(nextMonth);
  last.setDate(last.getDate() - 1);
  return { from: formatIsoDate(first), to: formatIsoDate(last) };
}
