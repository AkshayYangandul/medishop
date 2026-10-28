import React from 'react';
import { Users } from 'lucide-react';
import { PlaceholderPage } from './PlaceholderPage';

export function CustomersPage() {
  return (
    <PlaceholderPage
      title="Customers & Patients Directory"
      subtitle="Patient profiles, prescription histories, and loyalty accounts"
      icon={Users}
      moduleCode="CUST-07"
      plannedFeatures={[
        'Customer profiles with phone, address, and allergies/notes',
        'Prescription image attachments and doctor reference tracking',
        'Chronic illness refill reminders (e.g., monthly diabetes or cardiac meds)',
        'Customer ledger for credit sales & payment tracking',
      ]}
    />
  );
}
