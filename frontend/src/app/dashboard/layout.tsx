import { AppLayout } from '@/components/layout/AppLayout';
import { ResearchNavigation } from '@/components/monitoring/ResearchNavigation';

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return <AppLayout>
    <ResearchNavigation />
    <div className="min-h-0 flex-1 overflow-hidden print:overflow-visible">{children}</div>
  </AppLayout>;
}
