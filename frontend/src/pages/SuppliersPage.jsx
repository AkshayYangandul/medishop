import React from 'react';
import { Truck } from 'lucide-react';
import { PlaceholderPage } from './PlaceholderPage';

export function SuppliersPage() {
  return (
    <PlaceholderPage
      title="Suppliers & Wholesalers"
      subtitle="Manage medicine vendors, wholesale distributors, and credit terms"
      icon={Truck}
      moduleCode="SUP-05"
      plannedFeatures={[
        'Wholesaler master ledger with GSTIN and Drug License details',
        'Credit terms, payment schedules, and outstanding balances',
        'Purchase order history and delivery timelines',
        'Direct email/WhatsApp purchase order generation',
      ]}
    />
  );
}
