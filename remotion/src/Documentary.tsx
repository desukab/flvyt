import React from 'react';
import {AbsoluteFill, Easing, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {Visual} from './Visuals';

export type DocumentaryShot = {
  id: string;
  seconds: number;
  visual: string;
  text: string;
  mode?: string;
  transition?: 'cut' | 'fade' | 'dip';
  transitionFrames?: number;
};

export type DocumentaryBeat = {
  id: string;
  kind: string;
  text: string;
  seconds: number;
  visual: string;
  emphasis: string;
  assetSrc?: string;
  label?: string;
  value?: number;
  unit?: string;
  sources?: string[];
  shots?: DocumentaryShot[];
};

export type DocumentaryProps = {
  title: string;
  subtitle: string;
  fps: number;
  width: number;
  height: number;
  beats: DocumentaryBeat[];
};

type Segment = {
  beat: DocumentaryBeat;
  shot: DocumentaryShot;
  start: number;
  end: number;
};

const Background: React.FC = () => {
  const frame = useCurrentFrame();
  const drift = interpolate(frame, [0, 9000], [0, -180], {extrapolateRight: 'clamp'});
  return (
    <AbsoluteFill style={{background: '#070b10', overflow: 'hidden'}}>
      <div style={{position: 'absolute', inset: -180, transform: `translate3d(${drift}px,${drift * 0.35}px,0)`, background: 'radial-gradient(circle at 20% 30%,rgba(70,130,180,.22),transparent 34%),radial-gradient(circle at 80% 65%,rgba(160,80,210,.18),transparent 30%)'}} />
      <div style={{position: 'absolute', inset: 0, backgroundImage: 'linear-gradient(rgba(255,255,255,.035) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.035) 1px,transparent 1px)', backgroundSize: '80px 80px', opacity: 0.35}} />
      <div style={{position: 'absolute', inset: 0, background: 'radial-gradient(ellipse at center,transparent 35%,rgba(0,0,0,.72) 100%)'}} />
    </AbsoluteFill>
  );
};

const Intro: React.FC<{title: string; subtitle: string}> = ({title, subtitle}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const p = spring({frame, fps, config: {damping: 180, stiffness: 80}});
  const y = interpolate(p, [0, 1], [70, 0], {easing: Easing.out(Easing.cubic)});
  return (
    <AbsoluteFill style={{padding: '0 140px', justifyContent: 'center'}}>
      <div style={{opacity: p, transform: `translateY(${y}px)`}}>
        <div style={{fontSize: 26, letterSpacing: 8, color: 'rgba(255,255,255,.55)', marginBottom: 28}}>THE HIDDEN STORY / FLVYT</div>
        <div style={{fontSize: 92, lineHeight: 0.98, fontWeight: 850, maxWidth: 1500, letterSpacing: -4}}>{title}</div>
        <div style={{width: 520, height: 5, marginTop: 42, background: 'white', transformOrigin: 'left', transform: `scaleX(${interpolate(frame, [15, 55], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'})})`}} />
        <div style={{fontSize: 30, marginTop: 28, color: 'rgba(255,255,255,.68)', maxWidth: 1100, lineHeight: 1.25}}>{subtitle}</div>
      </div>
    </AbsoluteFill>
  );
};

function shotPlan(beat: DocumentaryBeat): DocumentaryShot[] {
  if (beat.shots?.length) return beat.shots;
  return [{id: 's1', seconds: beat.seconds, visual: beat.visual, text: beat.text, mode: 'hold', transition: 'cut'}];
}

const ShotContent: React.FC<{
  beat: DocumentaryBeat;
  shot: DocumentaryShot;
  index: number;
  total: number;
  local: number;
  forcedOpacity?: number;
}> = ({beat, shot, index, total, local, forcedOpacity}) => {
  const {fps} = useVideoConfig();
  const shotFrames = Math.max(15, Math.round(shot.seconds * fps));
  const p = spring({frame: local, fps, config: {damping: 170, stiffness: 95}});
  const x = interpolate(p, [0, 1], [45, 0], {extrapolateRight: 'clamp'});
  const opacityIn = interpolate(p, [0, 1], [0, 1], {extrapolateRight: 'clamp'});
  const outro = Math.max(0, shotFrames - 18);
  const outP = interpolate(local, [outro, outro + 18], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const opacity = forcedOpacity === undefined ? opacityIn * outP : forcedOpacity;
  return (
    <AbsoluteFill style={{opacity}}>
      <div style={{position: 'absolute', top: 62, left: 80, right: 80, display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
        <div style={{fontSize: 20, letterSpacing: 5, color: 'rgba(255,255,255,.48)'}}>{String(index + 1).padStart(2, '0')} / {String(total).padStart(2, '0')}</div>
        <div style={{fontSize: 20, letterSpacing: 4, color: 'rgba(255,255,255,.42)', textTransform: 'uppercase'}}>{beat.label || shot.visual}</div>
      </div>
      <AbsoluteFill style={{display: 'flex', alignItems: 'center', justifyContent: 'center', transform: `translateX(${x}px)`}}>
        <Visual {...beat} visual={shot.visual} text={shot.text} />
      </AbsoluteFill>
      <div style={{position: 'absolute', left: 80, right: 80, bottom: 35, height: 2, background: 'rgba(255,255,255,.12)'}}>
        <div style={{height: '100%', width: `${Math.min(100, (Math.max(0, local) / Math.max(1, shotFrames)) * 100)}%`, background: 'rgba(255,255,255,.72)'}} />
      </div>
    </AbsoluteFill>
  );
};

export const Documentary: React.FC<DocumentaryProps> = ({title, subtitle, beats}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const introFrames = Math.min(150, Math.round(fps * 5));

  const segments: Segment[] = [];
  let cursor = introFrames;
  for (const beat of beats) {
    for (const shot of shotPlan(beat)) {
      const segFrames = Math.max(15, Math.round(shot.seconds * fps));
      segments.push({beat, shot, start: cursor, end: cursor + segFrames});
      cursor += segFrames;
    }
  }

  if (frame < introFrames) {
    return (
      <AbsoluteFill style={{fontFamily: 'Arial,Helvetica,sans-serif', color: 'white'}}>
        <Background />
        <Intro title={title} subtitle={subtitle} />
      </AbsoluteFill>
    );
  }

  let idx = 0;
  for (let i = 0; i < segments.length; i++) {
    if (frame < segments[i].end) { idx = i; break; }
    idx = i;
  }
  if (segments.length === 0) {
    return (
      <AbsoluteFill style={{fontFamily: 'Arial,Helvetica,sans-serif', color: 'white'}}>
        <Background />
      </AbsoluteFill>
    );
  }

  const seg = segments[Math.min(idx, segments.length - 1)];
  const transition = seg.shot.transition ?? 'cut';
  const frames = Math.max(1, seg.shot.transitionFrames ?? 0);
  const inTransition = transition !== 'cut' && idx > 0 && frame < seg.start + frames;

  const renderSegment = (s: Segment, local: number, opacity: number | undefined, index: number) => (
    <ShotContent
      key={`${s.beat.id}-${s.shot.id}`}
      beat={s.beat}
      shot={s.shot}
      index={index}
      total={beats.length}
      local={Math.max(0, local)}
      forcedOpacity={opacity}
    />
  );

  if (!inTransition) {
    return (
      <AbsoluteFill style={{fontFamily: 'Arial,Helvetica,sans-serif', color: 'white'}}>
        <Background />
        {renderSegment(seg, frame - seg.start, undefined, idx)}
      </AbsoluteFill>
    );
  }

  const prev = segments[idx - 1];
  const t = (frame - seg.start) / frames;
  if (transition === 'fade') {
    const outOpacity = interpolate(t, [0, 1], [1, 0]);
    const inOpacity = interpolate(t, [0, 1], [0, 1]);
    return (
      <AbsoluteFill style={{fontFamily: 'Arial,Helvetica,sans-serif', color: 'white'}}>
        <Background />
        {renderSegment(prev, frame - prev.start, outOpacity, idx - 1)}
        {renderSegment(seg, frame - seg.start, inOpacity, idx)}
      </AbsoluteFill>
    );
  }

  const half = Math.max(1, Math.floor(frames / 2));
  if (t <= 0.5) {
    const outOpacity = interpolate(t, [0, 0.5], [1, 0], {extrapolateRight: 'clamp'});
    return (
      <AbsoluteFill style={{fontFamily: 'Arial,Helvetica,sans-serif', color: 'white'}}>
        <Background />
        {renderSegment(prev, frame - prev.start, outOpacity, idx - 1)}
        <AbsoluteFill style={{background: '#000', opacity: interpolate(t, [0, 0.5], [0, 1], {extrapolateRight: 'clamp'})}} />
      </AbsoluteFill>
    );
  }
  const inOpacity = interpolate(t, [0.5, 1], [0, 1], {extrapolateLeft: 'clamp'});
  return (
    <AbsoluteFill style={{fontFamily: 'Arial,Helvetica,sans-serif', color: 'white'}}>
      <Background />
      <AbsoluteFill style={{background: '#000', opacity: interpolate(t, [0.5, 1], [1, 0], {extrapolateLeft: 'clamp'})}} />
      <AbsoluteFill style={{opacity: inOpacity}}>
        {renderSegment(seg, frame - seg.start, undefined, idx)}
      </AbsoluteFill>
    </AbsoluteFill>
  );
};