import React from 'react';
import { COPY } from '@/lib/copy';

export function AsOfBadge({ date, sourceName }: { date: string, sourceName?: string }) {
  return (
    <div className="inline-flex items-center text-xs text-gray-500 bg-gray-100 rounded px-2 py-1">
      <span className="font-semibold mr-1">{COPY.GLOBAL.AS_OF}</span>
      <span>{date}</span>
      {sourceName && <span className="ml-1 opacity-75">({sourceName})</span>}
    </div>
  );
}
