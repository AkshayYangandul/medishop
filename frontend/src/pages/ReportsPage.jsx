import React from 'react';
import { FileBarChart } from 'lucide-react';
import { PlaceholderPage } from './PlaceholderPage';

export function ReportsPage() {
  return (
    <PlaceholderPage
      title="Analytics & Compliance Reports"
      subtitle="Financial statements, GST reports, expiry logs, and Schedule H registers"
      icon={FileBarChart}
      moduleCode="REP-10"
      plannedFeatures={[
        'Daily/Monthly sales and profit margins analysis',
        'GSTR-1 and GSTR-3B compliant tax summaries',
        'Drug control authority audit register for controlled substances (Schedule H/X)',
        'Dead stock and slow-moving inventory alerts',
        'PDF & Excel export engine',
      ]}
    />
  );
}
