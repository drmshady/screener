import { glossaryDefinition } from '@/lib/glossary';

export function HelpTooltip({ term }: { term: string }) {
  const definition = glossaryDefinition(term);
  if (!definition) {
    return null;
  }

  return (
    <span className="tooltip-anchor inline-flex align-middle">
      <button
        aria-label={`${term}: ${definition}`}
        className="inline-flex h-5 w-5 items-center justify-center border border-slate-300 bg-white text-xs font-semibold text-slate-700"
        title={definition}
        type="button"
      >
        ?
      </button>
      <span className="tooltip-panel" role="tooltip">
        {definition}
      </span>
    </span>
  );
}
