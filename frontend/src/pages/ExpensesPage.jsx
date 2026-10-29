import React from 'react';
import { Receipt } from 'lucide-react';
import { PlaceholderPage } from './PlaceholderPage';

export function ExpensesPage() {
  return (
    <PlaceholderPage
      title="Store Expenses & Petty Cash"
      subtitle="Track operating expenditures, rent, utilities, staff wages, and logistics"
      icon={Receipt}
      moduleCode="EXP-09"
      plannedFeatures={[
        'Categorized operating expenses (Rent, Electricity, Refrigerator maintenance, Salaries)',
        'Petty cash register & daily register closing reconciliation',
        'Receipt photo uploads & voucher numbering',
        'Net profit calculation after factoring all recurring overheads',
      ]}
    />
  );
}
