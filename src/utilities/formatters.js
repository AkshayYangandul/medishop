/**
 * Currency formatter for Indian Rupees (or USD / local currency)
 */
export function formatCurrency(amount, currency = 'INR') {
  if (typeof amount !== 'number') {
    const parsed = parseFloat(amount);
    if (isNaN(parsed)) return '₹0.00';
    amount = parsed;
  }
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: currency,
    maximumFractionDigits: 2,
  }).format(amount);
}

/**
 * Format a date string or timestamp into human-readable format
 */
export function formatDate(dateInput) {
  if (!dateInput) return '-';
  const date = new Date(dateInput);
  if (isNaN(date.getTime())) return '-';
  return new Intl.DateTimeFormat('en-IN', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  }).format(date);
}

/**
 * Format number with comma separators
 */
export function formatNumber(num) {
  if (num === null || num === undefined) return '0';
  return new Intl.NumberFormat('en-IN').format(num);
}
