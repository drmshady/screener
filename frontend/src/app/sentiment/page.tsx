"use client";

import { Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import { SentimentReport } from '@/components/SentimentReport';
import { SentimentSelection } from '@/lib/api';

export default function SentimentPage() {
  return (
    <Suspense fallback={<SentimentShell initialSelections={[]} />}>
      <SentimentPageContent />
    </Suspense>
  );
}

function SentimentPageContent() {
  const params = useSearchParams();
  const ticker = params.get('ticker')?.trim().toUpperCase();
  const origin = params.get('origin');
  const initialSelections: SentimentSelection[] =
    ticker && (origin === 'screener' || origin === 'holding' || origin === 'manual')
      ? [{ ticker, origin }]
      : [];

  return <SentimentShell initialSelections={initialSelections} />;
}

function SentimentShell({ initialSelections }: { initialSelections: SentimentSelection[] }) {
  return (
    <main className="mx-auto max-w-5xl space-y-6 px-4 py-6 sm:px-6 lg:px-8">
      <header className="border-b border-slate-200 pb-5">
        <h1 className="text-2xl font-semibold tracking-normal text-slate-950">Sentiment Report</h1>
        <p className="mt-2 max-w-3xl text-sm text-slate-600">
          Create an informational, sourced narrative only for the stocks you select.
        </p>
      </header>
      <SentimentReport initialSelections={initialSelections} />
    </main>
  );
}
