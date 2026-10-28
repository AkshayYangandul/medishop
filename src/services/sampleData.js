/**
 * Sample / Mock data for Phase 1 UI Demonstration
 * Realistic pharmacy & medical store records
 */

export const mockDashboardMetrics = {
  totalMedicines: {
    value: 1482,
    trend: '+12.5%',
    isPositive: true,
    comparison: 'vs last month',
  },
  lowStockCount: {
    value: 23,
    trend: '4 critical',
    isPositive: false,
    comparison: 'below reorder point',
  },
  expiringBatchesCount: {
    value: 9,
    trend: 'Within 30 days',
    isPositive: false,
    comparison: 'needs clearance',
  },
  todaySales: {
    value: 48250,
    trend: '+18.4%',
    isPositive: true,
    comparison: 'vs yesterday',
  },
};

export const mockSalesRevenueTrends = [
  { day: 'Mon', sales: 32400, purchases: 18000, profit: 14400 },
  { day: 'Tue', sales: 41200, purchases: 22000, profit: 19200 },
  { day: 'Wed', sales: 38900, purchases: 15500, profit: 23400 },
  { day: 'Thu', sales: 45600, purchases: 31000, profit: 14600 },
  { day: 'Fri', sales: 52300, purchases: 24000, profit: 28300 },
  { day: 'Sat', sales: 61000, purchases: 29500, profit: 31500 },
  { day: 'Sun', sales: 48250, purchases: 16000, profit: 32250 },
];

export const mockCategoryDistribution = [
  { name: 'Antibiotics', value: 410, color: '#0d9488' },
  { name: 'Analgesics / Pain', value: 320, color: '#0284c7' },
  { name: 'Cardiovascular', value: 240, color: '#6366f1' },
  { name: 'Vitamins & Supps', value: 210, color: '#f59e0b' },
  { name: 'Dermatological', value: 165, color: '#ec4899' },
  { name: 'Gastrointestinal', value: 137, color: '#10b981' },
];

export const mockExpiringBatches = [
  {
    id: 'b-101',
    medicineName: 'Amoxicillin 500mg',
    batchNo: 'BAT-2024-089',
    category: 'Antibiotics',
    expiryDate: '2026-11-15',
    daysRemaining: 19,
    quantity: 45,
    unit: 'Strips',
    supplier: 'Sun Pharma Ltd',
  },
  {
    id: 'b-102',
    medicineName: 'Azithromycin 250mg',
    batchNo: 'AZI-992-12',
    category: 'Antibiotics',
    expiryDate: '2026-11-20',
    daysRemaining: 24,
    quantity: 30,
    unit: 'Strips',
    supplier: 'Cipla Healthcare',
  },
  {
    id: 'b-103',
    medicineName: 'Cetirizine 10mg Syrup',
    batchNo: 'CET-SYR-041',
    category: 'Antihistamines',
    expiryDate: '2026-11-28',
    daysRemaining: 32,
    quantity: 18,
    unit: 'Bottles',
    supplier: 'Dr. Reddy’s Lab',
  },
  {
    id: 'b-104',
    medicineName: 'Omeprazole 20mg',
    batchNo: 'OMP-441-90',
    category: 'Gastrointestinal',
    expiryDate: '2026-12-05',
    daysRemaining: 39,
    quantity: 60,
    unit: 'Strips',
    supplier: 'Lupin Pharmaceuticals',
  },
];

export const mockLowStockMedicines = [
  {
    id: 'm-01',
    name: 'Paracetamol 650mg (Dolo)',
    category: 'Analgesics',
    currentStock: 14,
    minThreshold: 50,
    unit: 'Strips',
    status: 'Critical',
  },
  {
    id: 'm-02',
    name: 'Metformin 500mg',
    category: 'Antidiabetic',
    currentStock: 22,
    minThreshold: 60,
    unit: 'Strips',
    status: 'Low',
  },
  {
    id: 'm-03',
    name: 'Pantoprazole 40mg',
    category: 'Gastrointestinal',
    currentStock: 18,
    minThreshold: 40,
    unit: 'Strips',
    status: 'Critical',
  },
  {
    id: 'm-04',
    name: 'Atorvastatin 10mg',
    category: 'Cardiovascular',
    currentStock: 25,
    minThreshold: 50,
    unit: 'Strips',
    status: 'Low',
  },
];

export const mockRecentSales = [
  {
    id: 'INV-2026-0914',
    customerName: 'Rajesh Kumar',
    customerPhone: '+91 98765 43210',
    itemsCount: 4,
    totalAmount: 1240.00,
    paymentMethod: 'UPI',
    status: 'Completed',
    time: '10 mins ago',
  },
  {
    id: 'INV-2026-0913',
    customerName: 'Priya Sharma',
    customerPhone: '+91 98111 22334',
    itemsCount: 2,
    totalAmount: 480.50,
    paymentMethod: 'Cash',
    status: 'Completed',
    time: '28 mins ago',
  },
  {
    id: 'INV-2026-0912',
    customerName: 'Amit Patel',
    customerPhone: '+91 97234 56789',
    itemsCount: 6,
    totalAmount: 3150.00,
    paymentMethod: 'Card',
    status: 'Completed',
    time: '1 hour ago',
  },
  {
    id: 'INV-2026-0911',
    customerName: 'Walk-in Patient',
    customerPhone: 'N/A',
    itemsCount: 1,
    totalAmount: 95.00,
    paymentMethod: 'Cash',
    status: 'Completed',
    time: '2 hours ago',
  },
  {
    id: 'INV-2026-0910',
    customerName: 'Sunita Rao',
    customerPhone: '+91 94455 66778',
    itemsCount: 3,
    totalAmount: 890.00,
    paymentMethod: 'UPI',
    status: 'Completed',
    time: '3 hours ago',
  },
];
