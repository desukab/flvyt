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
};

const ACCENT = '#7fc1ff';
const INK = 'rgba(255,255,255,.92)';
const MUTED = 'rgba(255,255,255,.48)';

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

export const StatVisual: React.FC<VisualBeat> = ({text, value = 0, unit = '', sources, label = 'KEY FIGURE', emphasis}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const p = spring({frame, fps, config: {damping: 180, stiffness: 80}});
  const n = Math.round(interpolate(p, [0, 1], [0, Math.abs(value)]));
  const grouped = n.toLocaleString('en-US');
  const progress = unit === '%' ? Math.min(100, n) : Math.min(100, n * 10);
  return (
    <MotionShell mode="count">
      <Glass accent style={{padding: 54, width: 820, position: 'relative'}}>
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

export const ClaimVisual: React.FC<VisualBeat> = ({text, sources, mode, label = 'THE CLAIM'}) => (
  <MotionShell mode={mode}>
    <Glass style={{padding: 66, width: 1320, position: 'relative'}}>
      <Kicker>{label}</Kicker>
      <Rule />
      <div style={{fontSize: 64, lineHeight: 1.1, fontWeight: 720, maxWidth: 1180, letterSpacing: -0.5}}><Rich text={text} /></div>
      <SourceFooter sources={sources} />
    </Glass>
  </MotionShell>
);

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