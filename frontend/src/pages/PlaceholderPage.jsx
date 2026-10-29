import { NavLink } from 'react-router-dom';
import { PageHeader } from '../components/common/PageHeader';
import { Badge } from '../components/common/Badge';
import { Card, CardContent } from '../components/common/Card';
import { Button } from '../components/common/Button';
import {
  Sparkles,
  ArrowRight,
  Database,
  Construction,
  CheckCircle2,
} from 'lucide-react';

export function PlaceholderPage({
  title,
  subtitle,
  icon: Icon,
  plannedFeatures = [],
  moduleCode,
}) {
  return (
    <div className="space-y-6">
      <PageHeader
        title={title}
        subtitle={subtitle}
        badge={
          <Badge variant="warning" size="md" dot>
            Phase 2 Scope • Not Implemented Yet
          </Badge>
        }
        actions={
          <NavLink to="/dashboard">
            <Button variant="outline" size="sm" icon={ArrowRight} iconPosition="right">
              Back to Dashboard
            </Button>
          </NavLink>
        }
      />

      {/* Main Notice Banner */}
      <div className="rounded-xl border border-amber-200/80 bg-gradient-to-r from-amber-50/80 via-white to-amber-50/50 p-6 shadow-soft-sm">
        <div className="flex items-start gap-4">
          <div className="p-3 rounded-xl bg-amber-100 text-amber-700 shrink-0">
            {Icon ? <Icon className="w-6 h-6" /> : <Construction className="w-6 h-6" />}
          </div>
          <div className="space-y-1.5">
            <div className="flex items-center gap-2">
              <h3 className="font-bold text-slate-800 text-lg">
                {title} Module Placeholder
              </h3>
              <span className="text-xs font-mono font-bold px-2 py-0.5 rounded bg-amber-100 text-amber-800">
                {moduleCode || 'PHASE-2'}
              </span>
            </div>
            <p className="text-slate-600 text-sm leading-relaxed max-w-2xl">
              This module route is registered and scaffolding is configured as part of{' '}
              <strong>Phase 1: Project Setup</strong>. The UI forms, Supabase tables, and
              business logic for this section are scheduled for upcoming development phases.
            </p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Planned Features List */}
        <div className="lg:col-span-2">
          <Card>
            <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-brand-600" />
                <h4 className="font-semibold text-slate-800 text-sm">
                  Planned Roadmap & Architecture
                </h4>
              </div>
              <Badge variant="brand" size="sm">
                Spec Ready
              </Badge>
            </div>
            <CardContent className="space-y-4">
              <p className="text-xs text-slate-500">
                The following features and data contracts are mapped for {title}:
              </p>
              <ul className="space-y-2.5">
                {plannedFeatures.map((feat, idx) => (
                  <li
                    key={idx}
                    className="flex items-start gap-3 p-3 rounded-lg bg-slate-50 border border-slate-100 text-sm text-slate-700"
                  >
                    <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                    <span>{feat}</span>
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        </div>

        {/* Integration Status Card */}
        <div>
          <Card>
            <div className="px-5 py-4 border-b border-slate-100 flex items-center gap-2">
              <Database className="w-4 h-4 text-sky-600" />
              <h4 className="font-semibold text-slate-800 text-sm">
                Backend & Database Status
              </h4>
            </div>
            <CardContent className="space-y-4 text-xs text-slate-600">
              <div className="p-3 rounded-lg bg-sky-50/70 border border-sky-100 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-sky-900">Supabase Connection</span>
                  <Badge variant="neutral" size="sm">
                    Pending Phase 2
                  </Badge>
                </div>
                <p className="text-sky-700 leading-normal">
                  No database tables or remote authentication active in Phase 1 per design guidelines.
                </p>
              </div>

              <div className="space-y-2">
                <div className="flex items-center justify-between py-1.5 border-b border-slate-100">
                  <span className="text-slate-500">Validation Schema</span>
                  <span className="font-medium text-emerald-600">Zod Ready</span>
                </div>
                <div className="flex items-center justify-between py-1.5 border-b border-slate-100">
                  <span className="text-slate-500">Form Controller</span>
                  <span className="font-medium text-emerald-600">React Hook Form</span>
                </div>
                <div className="flex items-center justify-between py-1.5 border-b border-slate-100">
                  <span className="text-slate-500">Routing</span>
                  <span className="font-medium text-emerald-600">React Router v7</span>
                </div>
                <div className="flex items-center justify-between py-1.5">
                  <span className="text-slate-500">Styling System</span>
                  <span className="font-medium text-emerald-600">Tailwind CSS v3</span>
                </div>
              </div>

              <div className="pt-2">
                <NavLink to="/dashboard" className="w-full block">
                  <Button variant="secondary" size="sm" className="w-full">
                    Return to Dashboard
                  </Button>
                </NavLink>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
