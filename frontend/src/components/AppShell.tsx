import Link from 'next/link';
import { Disclaimer } from '@/components/Disclaimer';
import { GlobalDataAsOf } from '@/components/GlobalDataAsOf';
import { PortfolioSync } from '@/components/PortfolioSync';
import { StartupFreshnessGate } from '@/components/StartupFreshnessGate';

const NAV_LINKS = [
  { href: '/', label: 'Home' },
  { href: '/screen/midterm_52w_high_momentum', label: 'Screens' },
  { href: '/analyze', label: 'Analyze' },
  { href: '/sentiment', label: 'Sentiment' },
  { href: '/watchlist', label: 'Watchlist' },
  { href: '/portfolio', label: 'Portfolio' },
  { href: '/settings', label: 'Settings' },
  { href: '/help', label: 'Help' },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <body className="min-h-full bg-slate-50 text-slate-950">
      <PortfolioSync />
      <div className="flex min-h-screen flex-col">
        <header className="sticky top-0 z-40 border-b border-slate-200 bg-white/95 backdrop-blur">
          <div className="mx-auto flex max-w-7xl flex-col gap-3 px-4 py-3 sm:px-6 lg:px-8">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <Link className="text-base font-semibold tracking-normal text-slate-950" href="/">
                US Stock Screener
              </Link>
              <GlobalDataAsOf />
            </div>
            <nav aria-label="Primary" className="flex gap-1 overflow-x-auto">
              {NAV_LINKS.map((link) => (
                <Link
                  className="nav-link whitespace-nowrap px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100 hover:text-slate-950"
                  href={link.href}
                  key={link.href}
                >
                  {link.label}
                </Link>
              ))}
            </nav>
          </div>
        </header>
        <StartupFreshnessGate />
        <div className="flex-1">{children}</div>
        <footer className="border-t border-amber-200 bg-amber-50">
          <Disclaimer />
        </footer>
      </div>
    </body>
  );
}
