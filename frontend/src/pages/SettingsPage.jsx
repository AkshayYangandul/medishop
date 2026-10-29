import React from 'react';
import { Settings } from 'lucide-react';
import { PlaceholderPage } from './PlaceholderPage';

export function SettingsPage() {
  return (
    <PlaceholderPage
      title="Store & System Settings"
      subtitle="Pharmacy license credentials, tax preferences, printer config, and staff roles"
      icon={Settings}
      moduleCode="SET-11"
      plannedFeatures={[
        'Pharmacy profile (Store name, Drug License 20B/21B, GSTIN, Address, Contact)',
        'Thermal receipt template customization & logo upload',
        'Staff user management & role-based permissions (Cashier, Pharmacist, Admin)',
        'Supabase project credentials & backup configurations',
      ]}
    />
  );
}
