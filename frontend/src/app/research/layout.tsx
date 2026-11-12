import { AppLayout } from '@/components/layout/AppLayout';

export default function ResearchLayout({ children }: { children: React.ReactNode }) {
  return (
    <AppLayout>
      <div className="min-h-0 flex-1 flex flex-col h-full overflow-hidden print:overflow-visible">
        {children}
      </div>
    </AppLayout>
  );
}
