import React from 'react';
import { Layers } from 'lucide-react';
import { PlaceholderPage } from './PlaceholderPage';

export function BatchesPage() {
  return (
    <PlaceholderPage
      title="Batches & Expiry Management"
      subtitle="Track manufacturing batch numbers, lot tracking, and expiry clearance dates"
      icon={Layers}
      moduleCode="BAT-04"
      plannedFeatures={[
        'Batch number assignment and barcode association',
        'Manufacturing date (MFG) and expiration date (EXP) tracking',
        'FIFO / FEFO (First-Expired, First-Out) dispensing logic',
        'Supplier return management for near-expiry or expired medicines',
        'Automated 30/60/90 days early warning alerts',
      ]}
    />
  );
}
