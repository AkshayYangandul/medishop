import React from 'react';
import { Pill } from 'lucide-react';
import { PlaceholderPage } from './PlaceholderPage';

export function MedicinesPage() {
  return (
    <PlaceholderPage
      title="Medicines Catalog"
      subtitle="Master directory of pharmaceutical drugs, dosage formulations, and pricing"
      icon={Pill}
      moduleCode="MED-01"
      plannedFeatures={[
        'Full drug catalog with generic name, strength, dosage form (tablet, syrup, etc.)',
        'Barcode / QR code scanning & SKU generation',
        'Prescription drug flagging (Schedule H / X compliance)',
        'Minimum reorder point thresholds & low stock automated alerts',
        'Supabase CRUD integration with search & filters by category/brand',
      ]}
    />
  );
}
