import React from 'react';
import { ShoppingCart } from 'lucide-react';
import { PlaceholderPage } from './PlaceholderPage';

export function SalesPage() {
  return (
    <PlaceholderPage
      title="Point of Sale (POS) & Billing"
      subtitle="Counter billing terminal, thermal receipt generation, and payment processing"
      icon={ShoppingCart}
      moduleCode="POS-08"
      plannedFeatures={[
        'High-speed keyboard-driven POS counter billing screen',
        'FEFO batch automatic selection with manual override option',
        'Multiple payment modes: Cash, UPI, Card, Store Credit, Split payments',
        'Tax invoice generation with GST breakup and thermal printing support',
        'Prescription compliance verification before checkout',
      ]}
    />
  );
}
