import React from 'react';
import { COPY } from '@/lib/copy';
import type { Candidate } from '@/lib/api';

export function ScreenerTable({ candidates }: { candidates: Candidate[] }) {
  return (
    <div className="overflow-hidden rounded-lg shadow ring-1 ring-black ring-opacity-5">
      <table className="min-w-full divide-y divide-gray-300">
        <thead className="bg-gray-50">
          <tr>
            <th scope="col" className="py-3.5 pl-4 pr-3 text-left text-sm font-semibold text-gray-900 sm:pl-6">Ticker</th>
            <th scope="col" className="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">Sector</th>
            <th scope="col" className="px-3 py-3.5 text-right text-sm font-semibold text-gray-900">{COPY.ACTION.ENTRY_SUGGESTED}</th>
            <th scope="col" className="px-3 py-3.5 text-right text-sm font-semibold text-gray-900">{COPY.ACTION.STOP_LOSS}</th>
            <th scope="col" className="px-3 py-3.5 text-right text-sm font-semibold text-gray-900">{COPY.ACTION.TAKE_PROFIT}</th>
            <th scope="col" className="px-3 py-3.5 text-right text-sm font-semibold text-gray-900">Score</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-200 bg-white">
          {candidates.map((c) => (
            <tr key={c.ticker} className="hover:bg-gray-50">
              <td className="whitespace-nowrap py-4 pl-4 pr-3 text-sm font-medium text-gray-900 sm:pl-6">{c.ticker}</td>
              <td className="whitespace-nowrap px-3 py-4 text-sm text-gray-500">{c.sector}</td>
              <td className="whitespace-nowrap px-3 py-4 text-sm text-right text-gray-500">${Number(c.entry).toFixed(2)}</td>
              <td className="whitespace-nowrap px-3 py-4 text-sm text-right text-gray-500">${Number(c.stop_loss).toFixed(2)}</td>
              <td className="whitespace-nowrap px-3 py-4 text-sm text-right text-gray-500">${Number(c.take_profit).toFixed(2)}</td>
              <td className="whitespace-nowrap px-3 py-4 text-sm text-right text-gray-500">{c.score.toFixed(2)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
