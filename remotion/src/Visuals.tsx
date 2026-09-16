import React from 'react';
import {Easing, Img, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';

export type VisualBeat = {
  visual: string;
  text: string;
  seconds: number;
  emphasis?: string;
  assetSrc?: string;
  label?: string;
  value?: number;
  unit?: string;
  sources?: string[];
  mode?: string;
  motif?: string;
  chapter?: number;
  variant?: number;
};

const ACCENT = '#7fc1ff';
const INK = 'rgba(255,255,255,.92)';
const MUTED = 'rgba(255,255,255,.48)';

/** Deterministic 0..1 hash: the same string always seeds the same value, so
 * every motif, camera path and layout variant is reproducible per shot. */
export function hashStr(s: string): number {
  let h = 2166136261 >>> 0;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return (h >>> 0) / 4294967296;
}

export type ChapterField = {
  bg: string;
  grid: number;
  glows: string[];
  accent: string;
};

/** Per-chapter ambient field. Deterministic hue/mood from the chapter index:
 * two chapters never share a background, so a chapter boundary is a visible
 * scene change, and the motif layer + camera sit on top of it. */
export function chapterField(chapter?: number): ChapterField {
  const c = chapter && Number.isFinite(chapter) ? Math.max(0, chapter) : 0;
  const hue = Math.round((210 + c * 47) % 360);
  const hue2 = Math.round((hue + 55) % 360);
  const gx = 16 + ((c * 43) % 34);
  const gy = 22 + ((c * 29) % 40);
  const gx2 = 84 - ((c * 37) % 30);
  const gy2 = 62 - ((c * 19) % 36);
  return {
    bg: `hsl(${hue} 28% 6%)`,
    grid: 64 + (c % 5) * 16,
    glows: [
      `radial-gradient(circle at ${gx}% ${gy}%, hsl(${hue} 62% 50% / 0.2), transparent 42%)`,
      `radial-gradient(circle at ${gx2}% ${gy2}%, hsl(${hue2} 55% 48% / 0.16), transparent 40%)`,
    ],
    accent: `hsl(${hue} 78% 72%)`,
  };
}

// ---------------------------------------------------------------- motifs 

const OrbitMotif: React.FC<{accent: string; t: number; seed: number}> = ({accent, t, seed}) => {
  const cx = 1230 + Math.round(seed * 140);
  const cy = 210 + Math.round((seed * 113) % 120);
  const rings = [300, 222, 160, 112].map((r, i) => {
    const ang = t * (14 + i * 9) + seed * 40;
    return {r, ang};
  });
  const nodeAng = t * 6 + seed * 5;
  return (
    <div style={{position: 'absolute', inset: 0, overflow: 'hidden', opacity: 0.65}}>
      {rings.map(({r, ang}, i) => (
        <div key={i} style={{
          position: 'absolute', left: cx - r, top: cy - r * 0.42,
          width: r * 2, height: r * 2 * 0.42, borderRadius: '50%',
          border: '1px solid ' + (i === 0 ? accent + '55' : accent + '2b'),
          transform: `rotate(${ang}rad)`,
          transformOrigin: `${r}px ${r * 0.42}px`,
        }} />
      ))}
      <div style={{
        position: 'absolute', left: cx + 300 * Math.cos(nodeAng) - 7,
        top: cy + 300 * 0.42 * Math.sin(nodeAng) - 7, width: 14, height: 14,
        borderRadius: '50%', background: accent, boxShadow: `0 0 26px 6px ${accent}66`,
      }} />
      <div style={{
        position: 'absolute', left: cx - 40, top: cy - 40, width: 80, height: 80,
        borderRadius: '50%', border: `2px dashed ${accent}40`,
      }} />
    </div>
  );
};

const WaveMotif: React.FC<{accent: string; t: number; seed: number}> = ({accent, t, seed}) => {
  const cy = 300 + Math.round((seed * 197) % 240);
  const amp = 26 + Math.round((seed * 41) % 26);
  let p1: string[] = [];
  let p2: string[] = [];
  for (let x = 0; x <= 1920; x += 16) {
    p1.push(`${x},${(cy + amp * Math.sin(x / 72 + t * 2.3 + seed * 6) + amp * 0.5 * Math.sin(x / 24 - t * 1.6)).toFixed(1)}`);
    p2.push(`${x},${(cy + amp * Math.sin(x / 90 - t * 1.9 + seed * 3) + amp * 0.6 * Math.sin(x / 31 + t * 1.1)).toFixed(1)}`);
  }
  const tickX = ((t * 340) % 2150) - 115;
  return (
    <svg style={{position: 'absolute', inset: 0, opacity: 0.62}} width={1920} height={1080} viewBox="0 0 1920 1080">
      <defs>
        <linearGradient id="waveGrad1" x1="0" x2="1">
          <stop offset="0" stopColor={accent} stopOpacity="0" />
          <stop offset="0.5" stopColor={accent} stopOpacity="0.95" />
          <stop offset="1" stopColor={accent} stopOpacity="0" />
        </linearGradient>
      </defs>
      <polyline points={p2.join(' ')} fill="none" stroke={accent} strokeOpacity="0.28" strokeWidth="2" />
      <polyline points={p1.join(' ')} fill="none" stroke="url(#waveGrad1)" strokeWidth="3" />
      <line x1={tickX} y1={cy - amp * 2.2} x2={tickX} y2={cy + amp * 2.2} stroke={accent} strokeOpacity="0.4" strokeWidth="2" strokeDasharray="10 7" />
    </svg>
  );
};

const GridMotif: React.FC<{accent: string; t: number; seed: number}> = ({accent, t, seed}) => {
  const hub = [210 + Math.round(seed * 90), 660 - Math.round((seed * 131) % 220)];
  const nodes = Array.from({length: 7}, (_, i) => {
    const s = hashStr(`grid${i}|${seed}`);
    return {
      x: 60 + s * 620, y: 180 + hashStr(`gdy${i}|${seed}`) * 660,
      r: 5 + s * 7, delay: i * 9,
    };
  });
  return (
    <div style={{position: 'absolute', inset: 0, opacity: 0.7, overflow: 'hidden'}}>
      <div style={{
        position: 'absolute', inset: -60, opacity: 0.5,
        backgroundImage: `radial-gradient(circle, ${accent}30 1px, transparent 1px), radial-gradient(circle, ${accent}22 1px, transparent 1px)`,
        backgroundSize: '140px 140px, 140px 140px',
        backgroundPosition: '0 0, 70px 70px',
        transform: `translate3d(${t * 22}px,${t * 9}px,0)`,
      }} />
      {nodes.map((n, i) => {
        const grow = Math.max(0, Math.min(1, (t * 10 - n.delay) / 3));
        const dx = n.x - hub[0], dy = n.y - hub[1];
        const len = Math.hypot(dx, dy);
        const ang = Math.atan2(dy, dx);
        return (
          <React.Fragment key={i}>
            <div style={{
              position: 'absolute', left: hub[0], top: hub[1], width: len * grow, height: 2,
              background: `${accent}55`, transform: `rotate(${ang}rad)`,
              transformOrigin: '0 0',
            }} />
            <div style={{
              position: 'absolute', left: n.x - n.r, top: n.y - n.r, width: n.r * 2, height: n.r * 2,
              borderRadius: '50%', background: i === 0 ? accent : 'rgba(255,255,255,.85)',
              boxShadow: i === 0 ? `0 0 0 ${8 + 3 * Math.sin(t * 3 + i)}px ${accent}33` : 'none',
              opacity: 0.45 + 0.4 * Math.min(1, grow * 1.5),
            }} />
          </React.Fragment>
        );
      })}
      <div style={{position: 'absolute', left: hub[0] - 6, top: hub[1] - 6, width: 12, height: 12,
        borderRadius: '50%', background: accent, boxShadow: `0 0 30px 10px ${accent}44`}} />
    </div>
  );
};

const RoutesMotif: React.FC<{accent: string; t: number; seed: number}> = ({accent, t, seed}) => {
  const arcs = [
    {x1: 120, y1: 920, x2: 1780, y2: 480, c1: 500 + seed * 260, c2: 320, s: 0, d: 70},
    {x1: 240, y1: 700, x2: 1700, y2: 330, c1: 620, c2: 900, s: 40, d: 150},
    {x1: 360, y1: 990, x2: 1810, y2: 660, c1: 900, c2: 480, s: 95, d: 220},
  ];
  const path = (a: {x1: number; y1: number; x2: number; y2: number; c1: number; c2: number}) =>
    `M ${a.x1} ${a.y1} C ${a.c1} ${a.c2}, ${a.x2 - 320} ${a.y2 + 120}, ${a.x2} ${a.y2}`;
  return (
    <svg style={{position: 'absolute', inset: 0, opacity: 0.55}} width={1920} height={1080} viewBox="0 0 1920 1080">
      <defs>
        <linearGradient id="routeGrad" x1="0" y1="1" x2="1" y2="0">
          <stop offset="0" stopColor={accent} stopOpacity="0.1" />
          <stop offset="1" stopColor={accent} stopOpacity="0.85" />
        </linearGradient>
      </defs>
      {arcs.map((a, i) => {
        const dash = ((t * 90 + a.s) % 340) - 100;
        return (
          <React.Fragment key={i}>
            <path d={path(a)} fill="none" stroke="url(#routeGrad)" strokeWidth="2" strokeOpacity="0.35" />
            <path d={path(a)} fill="none" stroke={accent} strokeWidth="3" strokeDasharray={`34 220`} strokeDashoffset={-dash} strokeLinecap="round" />
          </React.Fragment>
        );
      })}
    </svg>
  );
};

const ChipMotif: React.FC<{accent: string; t: number; seed: number}> = ({accent, t, seed}) => {
  const cx = 1330 + Math.round(seed * 120);
  const cy = 360 + Math.round((seed * 97) % 140);
  const rings = [330, 286, 244, 206, 172].map((r, i) => ({r, dash: (t * 26 + i * 30) % 140}));
  return (
    <div style={{position: 'absolute', inset: 0, overflow: 'hidden', opacity: 0.6}}>
      {rings.map(({r, dash}, i) => (
        <div key={i} style={{
          position: 'absolute', left: cx - r, top: cy - r, width: r * 2, height: r * 2,
          borderRadius: 28, border: `2px dashed ${i % 2 ? accent + '30' : accent + '4e'}`,
          transform: `rotate(${t * 7 + i * 11 + seed * 30}deg)`,
          transformOrigin: `${r}px ${r}px`,
        }} />
      ))}
      {Array.from({length: 8}, (_, i) => {
        const ang = (i / 8) * Math.PI * 2 + t * 0.25 + seed * 2;
        const r1 = 198;
        return (
          <div key={i} style={{
            position: 'absolute', left: cx + Math.cos(ang) * r1, top: cy + Math.sin(ang) * r1,
            width: 22, height: 22, borderRadius: 6, background: i % 3 ? 'rgba(255,255,255,.8)' : accent,
            transform: `rotate(${ang}rad)`,
          }} />
        );
      })}
      <div style={{position: 'absolute', left: cx - 34, top: cy - 34, width: 68, height: 68,
        borderRadius: 14, background: accent, boxShadow: `0 0 40px 12px ${accent}55`}} />
    </div>
  );
};

const AccountsMotif: React.FC<{accent: string; t: number; seed: number}> = ({accent, t, seed}) => {
  const bars = Array.from({length: 12}, (_, i) => {
    const s = hashStr(`acct${i}|${seed}`);
    const height = (0.24 + s * 0.5) * 620;
    const breath = 0.75 + 0.25 * Math.sin(t * 1.4 + i * 0.8 + seed * 6);
    return {x: 90 + i * 96, height, breath, hot: i === Math.floor(seed * 12)};
  });
  const line = bars.map((b, i) => `${b.x + 22},${980 - b.height * b.breath}`).join(' ');
  return (
    <div style={{position: 'absolute', inset: 0, opacity: 0.55, overflow: 'hidden'}}>
      {[0, 1, 2, 3].map((g) => (
        <div key={g} style={{position: 'absolute', left: 40, right: 60, top: 350 + g * 210, height: 1, background: `${accent}18`}} />
      ))}
      <svg width={1920} height={1080} viewBox="0 0 1920 1080">
        {bars.map((b, i) => (
          <rect key={i} x={b.x} y={980 - b.height * b.breath} width={44} height={b.height * b.breath}
            fill={b.hot ? accent : `${accent}33`} rx={6} />
        ))}
        <polyline points={line} fill="none" stroke={accent} strokeWidth="3" strokeOpacity="0.9" />
      </svg>
    </div>
  );
};

const CosmosMotif: React.FC<{accent: string; t: number; seed: number}> = ({accent, t, seed}) => {
  const dots = Array.from({length: 110}, (_, i) => ({
    x: hashStr(`cx${i}|${seed}`) * 1920,
    y: hashStr(`cy${i}|${seed}`) * 1080,
    r: 1 + hashStr(`cr${i}|${seed}`) * 2.6,
    o: 0.14 + hashStr(`co${i}|${seed}`) * 0.35,
    p: hashStr(`cp${i}|${seed}`) * 20,
  }));
  return (
    <div style={{position: 'absolute', inset: 0, overflow: 'hidden', opacity: 0.7,
      transform: `translate3d(${t * 14}px,${t * 8}px,0)`}}>
      {dots.map((d, i) => (
        <div key={i} style={{
          position: 'absolute', left: d.x, top: d.y, width: d.r, height: d.r, borderRadius: '50%',
          background: i % 11 === 0 ? accent : 'rgba(255,255,255,.9)',
          opacity: d.o * (0.7 + 0.3 * Math.sin(t * 2 + d.p)),
        }} />
      ))}
    </div>
  );
};

export const MotifLayer: React.FC<{motif?: string; accent: string; chapter?: number}> = ({motif, accent, chapter}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps;
  const seed = (chapter && Number.isFinite(chapter) ? Math.max(0, chapter) : 0) || 0;
  switch (motif) {
    case 'orbit': return <OrbitMotif accent={accent} t={t} seed={seed} />;
    case 'wave': return <WaveMotif accent={accent} t={t} seed={seed} />;
    case 'grid': return <GridMotif accent={accent} t={t} seed={seed} />;
    case 'routes': return <RoutesMotif accent={accent} t={t} seed={seed} />;
    case 'chip': return <ChipMotif accent={accent} t={t} seed={seed} />;
    case 'accounts': return <AccountsMotif accent={accent} t={t} seed={seed} />;
    case 'chapter': return null;
    default: return <CosmosMotif accent={accent} t={t} seed={seed} />;
  }
};

// ----------------------------------------------------------- text atoms 

const Rich: React.FC<{text: string}> = ({text}) => {
  const parts = text.split(/([$]?\d[\d,]*(?:\.\d+)?(?:\s*(?:%|million|billion|trillion|percent|nm|mm|GHz|MHz|GB|TB|GW|MW|km|years))?)/g);
  return (
    <>{parts.map((part, i) => i % 2 === 1
      ? <span key={i} style={{color: ACCENT, fontWeight: 800}}>{part}</span>
      : <React.Fragment key={i}>{part}</React.Fragment>)}</>
  );
};

const Kicker: React.FC<{children: React.ReactNode}> = ({children}) => (
  <div style={{fontSize: 22, letterSpacing: 6, color: MUTED, textTransform: 'uppercase', marginBottom: 26}}>{children}</div>
);

const Rule: React.FC<{delay?: number}> = ({delay = 8}) => {
  const frame = useCurrentFrame();
  return (
    <div style={{width: 96, height: 5, background: ACCENT, marginBottom: 32, transformOrigin: 'left', transform: `scaleX(${Math.max(0, Math.min(1, (frame - delay) / 24))})`}} />
  );
};

const Glass: React.FC<{children: React.ReactNode; style?: React.CSSProperties; accent?: boolean}> = ({children, style, accent}) => (
  <div style={{background: 'rgba(10,15,22,.72)', border: '1px solid rgba(255,255,255,.12)', borderLeft: accent ? `5px solid ${ACCENT}` : '1px solid rgba(255,255,255,.12)', boxShadow: '0 30px 80px rgba(0,0,0,.35)', borderRadius: 18, backdropFilter: 'blur(12px)', ...style}}>{children}</div>
);

const SourceFooter: React.FC<{sources?: string[]}> = ({sources}) => {
  if (!sources?.length) return null;
  const text = sources.length === 1 ? sources[0] : `${sources[0]} + ${sources.length - 1} more source${sources.length > 2 ? 's' : ''}`;
  return <div style={{position: 'absolute', left: 80, right: 80, bottom: 52, fontSize: 17, color: 'rgba(255,255,255,.42)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis'}}>SOURCE&nbsp;·&nbsp;{text}</div>;
};

const MotionShell: React.FC<{children: React.ReactNode; mode?: string}> = ({children, mode = 'hold'}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const config = mode === 'punch'
    ? {damping: 14, stiffness: 220, mass: 0.5}
    : mode === 'establish'
      ? {damping: 24, stiffness: 90, mass: 0.8}
      : {damping: 34, stiffness: 70};
  const enter = spring({frame, fps, config});
  const y = interpolate(enter, [0, 1], [mode === 'punch' ? -20 : 30, 0], {easing: Easing.out(Easing.cubic)});
  const scale = 1 + (mode === 'punch' ? interpolate(frame, [0, 50], [0, 0.04], {extrapolateRight: 'clamp'}) : 0);
  const opacity = interpolate(enter, [0, 1], [0, 1]);
  return (
    <div style={{width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', opacity, transform: `translateY(${y}px) scale(${scale})`}}>{children}</div>
  );
};

/** Claim-card layout sub-variants. A plain claim stays honest: the anchor is
 * its motif, and these compose the card differently so two adjacent claims
 * never share a frame. */
const claimLayout = (variant: number): {justify: string; align: React.CSSProperties['textAlign']; pad: string; width: number} => {
  switch (variant % 4) {
    case 1: return {justify: 'flex-start', align: 'left', pad: '0 0 0 120px', width: 1080};
    case 2: return {justify: 'flex-end', align: 'left', pad: '0 120px 0 0', width: 1080};
    case 3: return {justify: 'center', align: 'center', pad: '0 140px', width: 1500};
    default: return {justify: 'center', align: 'center', pad: '0 0 0 0', width: 1320};
  }
};

export const StatVisual: React.FC<VisualBeat> = ({text, value = 0, unit = '', sources, label = 'KEY FIGURE', emphasis, variant}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const p = spring({frame, fps, config: {damping: 180, stiffness: 80}});
  const n = Math.round(interpolate(p, [0, 1], [0, Math.abs(value)]));
  const grouped = n.toLocaleString('en-US');
  const progress = unit === '%' ? Math.min(100, n) : Math.min(100, n * 10);
  const layout = claimLayout(variant ?? 0);
  return (
    <MotionShell mode="count">
      <Glass accent style={{padding: 54, width: 820, position: 'relative', ...(variant !== undefined ? {alignSelf: layout.justify === 'flex-start' ? 'flex-start' : layout.justify === 'flex-end' ? 'flex-end' : 'center'} : {})}}>
        <Kicker>{label}</Kicker>
        <div style={{fontSize: emphasis === 'high' ? 138 : 118, fontWeight: 850, letterSpacing: -7, lineHeight: 1}}>{grouped}<span style={{fontSize: 54, marginLeft: 12, opacity: 0.65}}>{unit}</span></div>
        <div style={{height: 8, background: 'rgba(255,255,255,.1)', margin: '30px 0', borderRadius: 8}}>
          <div style={{height: '100%', width: `${progress}%`, background: ACCENT, borderRadius: 8}} />
        </div>
        <div style={{fontSize: 28, lineHeight: 1.35, color: 'rgba(255,255,255,.8)', maxWidth: 720}}>{text}</div>
        <SourceFooter sources={sources} />
      </Glass>
    </MotionShell>
  );
};

export const ClaimVisual: React.FC<VisualBeat> = ({text, sources, mode, label = 'THE CLAIM', variant}) => {
  const layout = claimLayout(variant ?? 0);
  return (
    <MotionShell mode={mode}>
      {variant !== undefined && variant % 4 === 3 ? (
        <div style={{position: 'relative', width: 1500, padding: '0 0 0 40px', textAlign: 'left'}}>
          <div style={{width: 110, height: 5, background: ACCENT, marginBottom: 30}} />
          <div style={{fontSize: 88, lineHeight: 1.06, fontWeight: 800, maxWidth: 1400, letterSpacing: -2}}><Rich text={text} /></div>
        </div>
      ) : (
        <div style={{display: 'flex', justifyContent: layout.justify, width: '100%'}}>
          <Glass style={{padding: '66px 52px', width: layout.width, position: 'relative', margin: layout.justify === 'flex-start' ? '0 auto 0 60px' : layout.justify === 'flex-end' ? '0 60px 0 auto' : 0}}>
            <Kicker>{label}</Kicker>
            <Rule />
            <div style={{fontSize: layout.justify === 'center' ? 64 : 58, lineHeight: 1.1, fontWeight: 720, maxWidth: layout.width - 100, letterSpacing: -0.5, textAlign: layout.align}}><Rich text={text} /></div>
            <SourceFooter sources={sources} />
          </Glass>
        </div>
      )}
    </MotionShell>
  );
};

export const QuoteVisual: React.FC<VisualBeat> = ({text, sources, mode, label}) => (
  <MotionShell mode={mode}>
    <Glass accent style={{padding: 66, width: 1320, position: 'relative'}}>
      <div style={{fontSize: 110, lineHeight: 0.4, color: ACCENT, fontWeight: 800, fontFamily: 'Georgia,serif'}}>“</div>
      <div style={{fontSize: 56, lineHeight: 1.16, fontWeight: 640, maxWidth: 1180, marginTop: 34}}><Rich text={text} /></div>
      {label ? <div style={{fontSize: 20, letterSpacing: 5, color: MUTED, marginTop: 34, textTransform: 'uppercase'}}>{label}</div> : null}
      <SourceFooter sources={sources} />
    </Glass>
  </MotionShell>
);

export const TimelineVisual: React.FC<VisualBeat> = ({text, sources, mode, label = 'THE TIMELINE'}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const reveal = interpolate(spring({frame, fps, config: {damping: 90, stiffness: 60}}), [0, 1], [0, 1]);
  const positions = [8, 27, 46, 65, 84];
  const active = positions.map((x) => Math.max(0, Math.min(1, (frame - x) / 40)));
  const scan = interpolate(frame, [0, 160], [0, 100], {extrapolateRight: 'clamp'});
  return (
    <MotionShell mode={mode}>
      <Glass style={{padding: 54, width: 1320, position: 'relative'}}>
        <Kicker>{label}</Kicker>
        <div style={{position: 'relative', height: 130, marginTop: 10}}>
          <div style={{position: 'absolute', left: 40, right: 40, top: 48, height: 4, background: 'rgba(255,255,255,.18)', transformOrigin: 'left', transform: `scaleX(${reveal})`}} />
          {positions.map((x, i) => (
            <div key={i} style={{position: 'absolute', left: `${x}%`, top: 34, width: 34, height: 34, borderRadius: '50%', background: i === 4 ? ACCENT : 'rgba(255,255,255,.9)', boxShadow: '0 0 0 10px rgba(255,255,255,.07)', opacity: active[i], transform: `translateY(${interpolate(active[i], [0, 1], [10, 0])}px)`}} />
          ))}
          <div style={{position: 'absolute', left: `${scan}%`, top: 40, width: 14, height: 14, borderRadius: '50%', background: ACCENT, transform: 'translateX(-50%)'}} />
        </div>
        <div style={{fontSize: 34, lineHeight: 1.3, maxWidth: 1150, color: 'rgba(255,255,255,.85)'}}><Rich text={text} /></div>
        <SourceFooter sources={sources} />
      </Glass>
    </MotionShell>
  );
};

export const MapVisual: React.FC<VisualBeat> = ({text, sources, mode, label = 'THE CONNECTION'}) => {
  const frame = useCurrentFrame();
  const drift = interpolate(frame, [0, 200], [0, -46], {extrapolateRight: 'clamp'});
  const nodes = [[260, 168], [650, 292], [1010, 178], [860, 452], [420, 420]];
  const path = [[0, 1], [1, 2], [2, 3], [3, 4], [4, 0]];
  return (
    <MotionShell mode={mode}>
      <Glass style={{padding: 36, width: 1360, height: 620, overflow: 'hidden', position: 'relative'}}>
        <Kicker>{label}</Kicker>
        <div style={{position: 'absolute', inset: -100, transform: `translateX(${drift}px)`, opacity: 0.9, backgroundImage: 'radial-gradient(circle,rgba(255,255,255,.3) 1px,transparent 1px)', backgroundSize: '34px 34px'}} />
        <div style={{position: 'absolute', right: 60, top: 170, width: 540, height: 330, border: '1px solid rgba(255,255,255,.14)', borderRadius: 16, transform: 'rotate(-7deg)'}} />
        {path.map(([from, to], i) => {
          const [x1, y1] = nodes[from];
          const [x2, y2] = nodes[to];
          const len = Math.hypot(x2 - x1, y2 - y1);
          const ang = Math.atan2(y2 - y1, x2 - x1);
          const grow = Math.max(0, Math.min(1, (frame - i * 26) / 40));
          return <div key={i} style={{position: 'absolute', left: x1, top: y1, width: len * grow, height: 3, transform: `rotate(${ang}rad) translateY(50%)`, transformOrigin: '0 0', background: 'rgba(255,255,255,.4)'}} />;
        })}
        {nodes.map(([x, y], i) => {
          const pulse = 0.5 + 0.5 * Math.sin(frame / 14 + i);
          return <div key={i} style={{position: 'absolute', left: x, top: y, width: 26, height: 26, borderRadius: '50%', background: i === 2 ? ACCENT : 'white', boxShadow: `0 0 0 ${10 + pulse * 8}px rgba(255,255,255,.07)`}} />;
        })}
        <div style={{position: 'absolute', left: 46, bottom: 46, fontSize: 31, maxWidth: 980}}><Rich text={text} /></div>
        <SourceFooter sources={sources} />
      </Glass>
    </MotionShell>
  );
};

export const ChartVisual: React.FC<VisualBeat> = ({text, value, unit = '', sources, label = 'KEY FIGURE', mode}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const hash = Array.from(text).reduce((a, c) => a + (c.charCodeAt(0) || 0), 0);
  const base = [0.5, 0.68, 0.82, 0.6, 0.96];
  const heights = base.map((_, i) => base[(i + hash) % base.length]);
  const highlight = heights.indexOf(Math.max(...heights));
  const bars = heights.map((h, i) => {
    const p = spring({frame: Math.max(0, frame - i * 7), fps, config: {damping: 24, stiffness: 140}});
    return {height: h * 320 * p, hot: i === highlight};
  });
  const hot = bars[highlight];
  const hotValue = value !== undefined ? Math.round(value).toLocaleString('en-US') : 'PEAK';
  return (
    <MotionShell mode={mode}>
      <Glass style={{padding: 54, width: 1320, position: 'relative', display: 'flex', flexDirection: 'column'}}>
        <Kicker>{label}</Kicker>
        <div style={{position: 'relative', height: 380, margin: '10px 20px 0'}}>
          {[0, 1, 2, 3].map((g) => (
            <div key={g} style={{position: 'absolute', left: 0, right: 0, top: `${g * 25}%`, height: 1, background: 'rgba(255,255,255,.07)'}} />
          ))}
          {bars.map((b, i) => (
            <div key={i} style={{position: 'absolute', bottom: 0, left: `${38 + i * 18}%`, width: 64, height: Math.max(2, b.height), background: b.hot ? ACCENT : 'rgba(255,255,255,.8)', borderRadius: '6px 6px 0 0'}} />
          ))}
          {hot && (
            <div style={{position: 'absolute', bottom: hot.height + 14, left: `${38 + highlight * 18}%`, fontSize: 34, fontWeight: 800, color: ACCENT}}>{hotValue}{unit && <span style={{fontSize: 22, marginLeft: 6, opacity: 0.7}}>{unit}</span>}</div>
          )}
        </div>
        <div style={{fontSize: 30, lineHeight: 1.3, maxWidth: 1120, marginTop: 22}}><Rich text={text} /></div>
        <SourceFooter sources={sources} />
      </Glass>
    </MotionShell>
  );
};

export const TitleVisual: React.FC<VisualBeat> = ({text, mode}) => (
  <MotionShell mode={mode}>
    <Glass style={{padding: 70, width: 1400}}>
      <div style={{fontSize: 84, fontWeight: 850, lineHeight: 1.02, letterSpacing: -3}}><Rich text={text} /></div>
    </Glass>
  </MotionShell>
);

export const ChapterVisual: React.FC<VisualBeat> = ({text, label = 'PART', mode, chapter}) => {
  const frame = useCurrentFrame();
  const field = chapterField(chapter);
  const n = text.match(/\d+/)?.[0] ?? '';
  return (
    <div style={{position: 'relative', width: '100%', height: '100%', overflow: 'hidden'}}>
      <div style={{position: 'absolute', inset: 0, background: field.bg, overflow: 'hidden'}}>
        <div style={{position: 'absolute', inset: 0, background: field.glows.join(',')}} />
        <div style={{position: 'absolute', top: '22%', right: '16%', width: 340, height: 340, borderRadius: '50%', border: `1px solid ${field.accent}`, opacity: 0.35, transform: `translate(${frame * 0.4}px,${frame * 0.25}px)`}} />
        <div style={{position: 'absolute', top: '12%', left: '18%', width: 420, height: 420, border: '1px solid rgba(255,255,255,.12)', transform: `translate(-${frame * 0.3}px,-${frame * 0.2}px)`}} />
      </div>
      <Letterbox />
      <div style={{position: 'absolute', inset: 0, background: 'linear-gradient(90deg,rgba(0,0,0,.55),rgba(0,0,0,.05))'}} />
      <MotionShell mode={mode}>
        <div style={{position: 'absolute', left: 140, bottom: 140, maxWidth: 1200}}>
          {n && <div style={{fontSize: 300, fontWeight: 850, lineHeight: 0.7, letterSpacing: -12, color: field.accent, opacity: 0.28, marginBottom: 18}}>{n}</div>}
          <div style={{fontSize: 22, letterSpacing: 8, color: MUTED, textTransform: 'uppercase', marginBottom: 22}}>{label}</div>
          <div style={{fontSize: 74, fontWeight: 850, lineHeight: 1.05, letterSpacing: -2}}><Rich text={text} /></div>
        </div>
      </MotionShell>
      <SourceFooter sources={[]} />
    </div>
  );
};

const Letterbox = () => (
  <>
    <div style={{position: 'absolute', top: 0, left: 0, right: 0, height: 96, background: 'linear-gradient(180deg, rgba(0,0,0,.9), rgba(0,0,0,0))'}} />
    <div style={{position: 'absolute', bottom: 0, left: 0, right: 0, height: 130, background: 'linear-gradient(0deg, rgba(0,0,0,.9), rgba(0,0,0,0))'}} />
  </>
);

export const AssetVisual: React.FC<VisualBeat> = ({text, assetSrc, sources, mode, label}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const rate = mode === 'move' ? 200 : 260;
  const scale = interpolate(frame, [0, rate], [1.02, 1.14], {extrapolateRight: 'clamp'});
  const drift = interpolate(frame, [0, rate], [0, -26], {extrapolateRight: 'clamp'});
  const src = assetSrc
    ? (assetSrc.startsWith('http://') || assetSrc.startsWith('https://')
      ? assetSrc
      : staticFile(assetSrc.replace(/^public\//, '').replace(/^\//, '')))
    : undefined;
  return (
    <div style={{position: 'relative', width: '100%', height: '100%', overflow: 'hidden'}}>
      {src
        ? <Img src={src} style={{width: '100%', height: '100%', objectFit: 'cover', transform: `translateX(${drift}px) scale(${scale})`, filter: 'brightness(.5) saturate(.82)'}} />
        : <div style={{position: 'absolute', inset: 0, background: 'linear-gradient(135deg,#101923,#2c3948)', overflow: 'hidden'}}>
            <div style={{position: 'absolute', inset: -80, backgroundImage: 'radial-gradient(circle,rgba(255,255,255,.14) 1px,transparent 1px)', backgroundSize: '44px 44px', transform: `translateY(${frame * 0.6}px)`, opacity: 0.8}} />
            <div style={{position: 'absolute', left: '16%', top: '24%', width: 360, height: 360, border: '1px solid rgba(255,255,255,.12)'}} />
            <div style={{position: 'absolute', right: '18%', bottom: '22%', width: 260, height: 260, borderRadius: '50%', border: '2px solid ' + ACCENT, opacity: 0.55}} />
            <div style={{position: 'absolute', left: '16%', top: '24%', width: 360, height: 360, transform: `translate(${frame * 0.3}px,${frame * 0.18}px)`}} />
          </div>}
      <Letterbox />
      <div style={{position: 'absolute', inset: 0, background: 'linear-gradient(90deg,rgba(0,0,0,.82),rgba(0,0,0,.06))'}} />
      <MotionShell mode={mode}>
        <div style={{position: 'absolute', left: 120, bottom: 120, maxWidth: 1150}}>
          {label ? <div style={{fontSize: 20, letterSpacing: 6, color: ACCENT, textTransform: 'uppercase', marginBottom: 16}}>{label}</div> : null}
          <div style={{fontSize: 58, fontWeight: 750, lineHeight: 1.08}}><Rich text={text} /></div>
        </div>
      </MotionShell>
      <SourceFooter sources={sources} />
    </div>
  );
};

export const Visual: React.FC<VisualBeat> = (props) => {
  switch (props.visual) {
    case 'title': return <TitleVisual {...props} />;
    case 'chapter': case 'section': return <ChapterVisual {...props} />;
    case 'stat': case 'counter': return <StatVisual {...props} />;
    case 'chart': return <ChartVisual {...props} />;
    case 'timeline': return <TimelineVisual {...props} />;
    case 'map': return <MapVisual {...props} />;
    case 'quote': return <QuoteVisual {...props} />;
    case 'claim': case 'text': return <ClaimVisual {...props} />;
    case 'broll': case 'image': case 'portrait': case 'logo': return <AssetVisual {...props} />;
    default: return <AssetVisual {...props} />;
  }
};