import NepaliDate from 'nepali-date-converter';

const now = new NepaliDate();
console.log('Now BS:', now.format('YYYY-MM-DD'));
console.log('Now AD:', now.toJsDate().toISOString());

const startOfPastMonthBS = new NepaliDate(now.getYear(), now.getMonth() - 1, 1);
console.log('Past Month Start BS:', startOfPastMonthBS.format('YYYY-MM-DD'));
console.log('Past Month Start AD:', startOfPastMonthBS.toJsDate().toISOString());

const daysInPastMonth = new NepaliDate(now.getYear(), now.getMonth() - 1, 1).getDaysInMonth();
const endOfPastMonthBS = new NepaliDate(now.getYear(), now.getMonth() - 1, daysInPastMonth);
console.log('Past Month End BS:', endOfPastMonthBS.format('YYYY-MM-DD'));
console.log('Past Month End AD:', endOfPastMonthBS.toJsDate().toISOString());

// convert from AD to BS
const date = new NepaliDate(new Date('2024-01-01'));
console.log('2024-01-01 in BS:', date.format('YYYY-MM-DD'));

// convert from BS to AD
const adDate = new NepaliDate('2080-09-17').toJsDate();
console.log('2080-09-17 in AD:', adDate.toISOString());
