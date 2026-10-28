import React from 'react';
import { PackagePlus } from 'lucide-react';
import { PlaceholderPage } from './PlaceholderPage';

export function PurchasesPage() {
  return (
    <PlaceholderPage
      title="Purchases & Inward Stock"
      subtitle="Stock entry, supplier invoice processing, and purchase returns"
      icon={PackagePlus}
      moduleCode="PUR-06"
      plannedFeatures={[
        'Inward stock entry with batch, MRP, purchase cost, and trade schemes',
        'Automatic calculation of input GST (CGST/SGST/IGST)',
        'Purchase invoice reconciliation with supplier ledger',
        'Damaged goods / defective stock return processing',
      ]}
    />
  );
}
