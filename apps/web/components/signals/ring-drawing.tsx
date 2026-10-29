import * as React from "react";
import type { SignalDetail } from "@/lib/types";

const COLLEGE_HUES = ["var(--hue-blue)", "var(--hue-seal)", "var(--hue-teal)", "var(--hue-caution)", "var(--hue-ok)"];

/**
 * A node-link drawing of a shared contact ring: each shared contact is a
 * square in the middle, members are dots around it, coloured by college,
 * and a line joins a member to each contact it shares. It is decorative
 * support only (W4-6): the facts table beside it is the evidence, and the
 * figure's text alternative says what it shows. Hidden below 768 px.
 */
export function RingDrawing({ signal, label }: { signal: SignalDetail; label: string }) {
  const W = 360;
  const H = 300;
  const cx = W / 2;
  const cy = H / 2;
  const hubs = signal.shared.slice(0, 8);
  const members = signal.members.slice(0, 60);
  const colleges = [...new Set(members.map((m) => m.institution.id))];

  const hubAt = (i: number) => {
    const a = (i / Math.max(1, hubs.length)) * Math.PI * 2 - Math.PI / 2;
    const r = hubs.length > 1 ? 52 : 0;
    return { x: cx + Math.cos(a) * r, y: cy + Math.sin(a) * r };
  };
  const memberAt = (i: number) => {
    const a = (i / Math.max(1, members.length)) * Math.PI * 2 - Math.PI / 2;
    const r = 118 + (i % 2) * 12;
    return { x: cx + Math.cos(a) * r, y: cy + Math.sin(a) * (r * 0.82) };
  };
  // Each contact is shared by `students` members; walk the member list so every member links to at least one hub.
  const edges: [number, number][] = [];
  let cursor = 0;
  hubs.forEach((h, hi) => {
    const n = Math.min(h.students, members.length);
    for (let k = 0; k < n; k++) edges.push([hi, (cursor + k) % Math.max(1, members.length)]);
    cursor = (cursor + Math.ceil(n / 2)) % Math.max(1, members.length);
  });

  return (
    <figure className="m-0">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={label} className="h-auto w-full max-w-[420px]">
        <g stroke="var(--rule-strong)" strokeWidth="0.75" opacity="0.7">
          {edges.map(([h, m], i) => {
            const a = hubAt(h);
            const b = memberAt(m);
            return <line key={i} x1={a.x} y1={a.y} x2={b.x} y2={b.y} />;
          })}
        </g>
        {members.map((m, i) => {
          const p = memberAt(i);
          return <circle key={m.enrolment_id} cx={p.x} cy={p.y} r="4.5" fill={COLLEGE_HUES[colleges.indexOf(m.institution.id) % COLLEGE_HUES.length]} />;
        })}
        {hubs.map((h, i) => {
          const p = hubAt(i);
          return <rect key={`${h.kind}-${i}`} x={p.x - 7} y={p.y - 7} width="14" height="14" rx="2" fill="var(--paper-raised)" stroke="var(--ink)" strokeWidth="1.5" />;
        })}
      </svg>
      <figcaption className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-muted">
        {colleges.map((id, i) => (
          <span key={id} className="inline-flex items-center gap-1.5">
            <span className="inline-block size-2.5 rounded-full" style={{ background: COLLEGE_HUES[i % COLLEGE_HUES.length] }} aria-hidden="true" />
            {members.find((m) => m.institution.id === id)?.institution.name}
          </span>
        ))}
      </figcaption>
    </figure>
  );
}
