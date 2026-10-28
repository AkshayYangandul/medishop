import React from 'react';
import { Bookmark } from 'lucide-react';
import { PlaceholderPage } from './PlaceholderPage';

export function BrandsPage() {
  return (
    <PlaceholderPage
      title="Pharmaceutical Brands & Manufacturers"
      subtitle="Manage pharmaceutical companies, distributors, and licensed brand lines"
      icon={Bookmark}
      moduleCode="BRD-03"
      plannedFeatures={[
        'Manufacturer directory (e.g. Cipla, Sun Pharma, Dr. Reddy’s, Abbott)',
        'Company drug license credentials and GSTIN records',
        'Direct contact persons and representative details',
        'Brand-wise sales performance analytics',
      ]}
    />
  );
}
