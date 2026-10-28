import React from 'react';
import { Tags } from 'lucide-react';
import { PlaceholderPage } from './PlaceholderPage';

export function CategoriesPage() {
  return (
    <PlaceholderPage
      title="Medicine Categories"
      subtitle="Therapeutic classes and drug groups classification"
      icon={Tags}
      moduleCode="CAT-02"
      plannedFeatures={[
        'Therapeutic category hierarchy (Antibiotics, Analgesics, Antidiabetic, etc.)',
        'Storage requirement rules (Refrigerated 2-8°C, Cool & Dry place)',
        'Drug rack & shelf location mapping in store',
        'Category-wise revenue & volume breakdown',
      ]}
    />
  );
}
