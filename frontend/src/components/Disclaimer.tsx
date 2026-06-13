import React from 'react';
import { COPY } from '@/lib/copy';

export function Disclaimer() {
  return (
    <div className="w-full px-4 py-3 text-center text-sm font-medium text-amber-900">
      {COPY.GLOBAL.DISCLAIMER}
    </div>
  );
}
