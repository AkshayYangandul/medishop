import { useState, useEffect } from 'react';
import { getMedicinesInventory, getDashboardStats } from '../services/api';

const EXPIRY_WINDOW_DAYS = 60;

function daysUntil(dateInput) {
  if (!dateInput) return null;
  const expiry = new Date(dateInput);
  if (isNaN(expiry.getTime())) return null;
  const diff = expiry.getTime() - Date.now();
  return Math.ceil(diff / (1000 * 60 * 60 * 24));
}

export function useDashboardData() {
  const [medicines, setMedicines] = useState([]);
  const [totalMedicines, setTotalMedicines] = useState(0);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const [inventoryRes, statsRes] = await Promise.allSettled([
          getMedicinesInventory({ isActive: true, page: 1, limit: 100 }),
          getDashboardStats(),
        ]);

        if (cancelled) return;

        if (inventoryRes.status === 'fulfilled') {
          const inventory = inventoryRes.value;
          const entries = inventory?.medicines || [];
          setMedicines(entries);
          setTotalMedicines(inventory?.total ?? entries.length);
        }

        if (statsRes.status === 'fulfilled') {
          setStats(statsRes.value);
        }
      } catch (err) {
        if (cancelled) return;
        setError(err?.message || 'Failed to load dashboard data.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    load();
    return () => {
      cancelled = true;
    };
  }, []);

  const computedLowStock = medicines.filter((entry) => entry.is_low_stock).length;
  const lowStockCount = stats?.low_stock_count ?? computedLowStock;

  const expiringBatches = medicines.reduce((acc, entry) => {
    (entry.batches || []).forEach((batch) => {
      const daysRemaining = daysUntil(batch.expiry_date);
      if (daysRemaining === null) return;
      if (daysRemaining < 0 || daysRemaining > EXPIRY_WINDOW_DAYS) return;
      if ((batch.current_quantity ?? 0) <= 0) return;
      acc.push({
        id: batch.id || `${entry.medicine_id}-${batch.batch_no}`,
        medicineId: entry.medicine_id,
        medicineName: entry.medicine_name,
        batchNo: batch.batch_no,
        expiryDate: batch.expiry_date,
        daysRemaining,
        quantity: batch.current_quantity,
        supplier: batch.supplier_name,
      });
    });
    return acc;
  }, []);

  const metrics = {
    totalMedicines: stats?.total_medicines ?? totalMedicines,
    lowStockCount,
    expiringBatchesCount: stats?.expiring_batches_count ?? expiringBatches.length,
    todaySales: stats?.today_revenue ?? 0,
    todayOrders: stats?.today_orders ?? 0,
  };

  return {
    medicines,
    totalMedicines: metrics.totalMedicines,
    lowStockCount,
    expiringBatches,
    metrics,
    stats,
    loading,
    error,
  };
}
