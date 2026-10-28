import { NavLink } from 'react-router-dom';
import { PageHeader } from '../components/common/PageHeader';
import { Badge } from '../components/common/Badge';
import { Button } from '../components/common/Button';
import { MetricsOverview } from '../components/dashboard/MetricsOverview';
import { SalesRevenueChart } from '../components/dashboard/SalesRevenueChart';
import { CategoryDistributionChart } from '../components/dashboard/CategoryDistributionChart';
import { RecentSalesTable } from '../components/dashboard/RecentSalesTable';
import { ExpiringAlertsList } from '../components/dashboard/ExpiringAlertsList';
import { QuickActions } from '../components/dashboard/QuickActions';
import { ShoppingCart, Download } from 'lucide-react';

export function DashboardPage() {
  return (
    <div className="space-y-6">
      {/* Page Header */}
      <PageHeader
        title="Pharmacy Dashboard"
        subtitle="Real-time overview of pharmacy inventory, counter sales, and batch expiry tracking."
        badge={
          <Badge variant="brand" size="md" dot>
            Phase 1 • Mock Data Active
          </Badge>
        }
        actions={
          <>
            <Button
              variant="outline"
              size="sm"
              icon={Download}
              onClick={() => alert('Exporting dashboard report (mock feature for Phase 1)')}
            >
              Export Summary
            </Button>
            <NavLink to="/sales">
              <Button variant="primary" size="sm" icon={ShoppingCart}>
                New Sale (POS)
              </Button>
            </NavLink>
          </>
        }
      />

      {/* Summary Stat Cards (4 required metrics) */}
      <MetricsOverview />

      {/* Quick Action Shortcuts */}
      <QuickActions />

      {/* Charts Section: Weekly Sales Area Chart + Category Donut Chart */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <SalesRevenueChart />
        </div>
        <div className="lg:col-span-1">
          <CategoryDistributionChart />
        </div>
      </div>

      {/* Tables and Alerts: Recent Sales + Expiry Watchlist */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <RecentSalesTable />
        </div>
        <div className="lg:col-span-1">
          <ExpiringAlertsList />
        </div>
      </div>
    </div>
  );
}
