import { glossaryDefinition } from '@/lib/glossary';

/**
 * App-wide rule: every abbreviation/jargon term shown in the UI is wrapped in
 * <Abbr> so hovering (or focusing) reveals what it stands for. Definitions come
 * from the single glossary in lib/glossary.ts.
 *
 *   <Abbr term="ADV" />            -> shows "ADV", hover explains it
 *   <Abbr term="8-K">8-K</Abbr>    -> custom visible text, same lookup
 *
 * Unknown terms render as plain text (no underline), so it's always safe to wrap.
 */
export function Abbr({ term, children }: { term: string; children?: React.ReactNode }) {
  const definition = glossaryDefinition(term);
  const text = children ?? term;
  if (!definition) {
    return <>{text}</>;
  }
  return (
    <span className="abbr-anchor" tabIndex={0} title={`${term}: ${definition}`}>
      {text}
      <span className="tooltip-panel" role="tooltip">
        <span className="font-semibold">{term}</span> — {definition}
      </span>
    </span>
  );
}
