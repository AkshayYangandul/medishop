import { useState } from 'react';
import {
  mockDashboardMetrics,
  mockSalesRevenueTrends,
  mockCategoryDistribution,
  mockExpiringBatches,
  mockRecentSales,
  mockLowStockMedicines,
} from '../services/sampleData';

/**
 * Custom hook providing dashboard data
 * Pre-wired with sample data for Phase 1.
 * Ready for Supabase real-time subscription / query hook in Phase 2.
 */
export function useDashboardData() {
  const [loading] = useState(false);
  const [data] = useState({
    metrics: mockDashboardMetrics,
    revenueTrends: mockSalesRevenueTrends,
    categoryDistribution: mockCategoryDistribution,
    expiringBatches: mockExpiringBatches,
    recentSales: mockRecentSales,
    lowStockMedicines: mockLowStockMedicines,
  });

  return {
    ...data,
    loading,
    isMock: true,
  };
}
