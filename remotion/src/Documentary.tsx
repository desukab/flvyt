import React from 'react';
import {AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';

export type DocumentaryBeat = {
  id: string;
  kind: string;
  text: string;
  seconds: number;
  visual: string;
  emphasis: string;
};

export type DocumentaryProps = {
  title: string;
  subtitle: string;
  fps: number;
  width: number;
  height: number;
  beats: DocumentaryBeat[];
};

const Background: React.FC = () => {
  const frame = useCurrentFrame();
  const drift = interpolate(frame, [0, 9000], [0, -160], {extrapolateRight: 'clamp'});
  return <AbsoluteFill style={{background: '#070b10', overflow: 'hidden'}}>
    <div style={{position: 'absolute', inset: -160, transform: `translate3d(${drift}px, ${drift * .35}px, 0)`, background: 'radial-gradient(circle at 20% 30%, rgba(70,130,180,.22), transparent 34%), radial-gradient(circle at 80% 65%, rgba(160,80,210,.18), transparent 30%)'}} />
    <div style={{position: 'absolute', inset: 0, backgroundImage: 'linear-gradient(rgba(255,255,255,.035) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.035) 1px, transparent 1px)', backgroundSize: '80px 80px', opacity: .35}} />
    <div style={{position: 'absolute', inset: 0, background: 'radial-gradient(ellipse at center, transparent 35%, rgba(0,0,0,.72) 100%)'}} />
    <div style={{position: 'absolute', right: 70, bottom: 55, fontSize: 22, letterSpacing: 5, color: 'rgba(255,255,255,.32)'}}>FLVYT / 001</div>
  </AbsoluteFill>;
};

export const Documentary: React.FC<DocumentaryProps> = ({title, subtitle, beats}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const intro = spring({frame, fps, config: {damping: 200, stiffness: 90}});
  const titleY = interpolate(intro, [0, 1], [90, 0]);
  const titleOpacity = interpolate(intro, [0, 1], [0, 1]);
  const introFrames = Math.min(150, Math.round(fps * 5));

  let cursor = introFrames;
  let active = -1;
  for (let i = 0; i < beats.length; i++) {
    const end = cursor + Math.max(15, Math.round(beats[i].seconds * fps));
    if (frame >= cursor && frame < end) { active = i; break; }
    cursor = end;
  }

  const beat = active >= 0 ? beats[active] : undefined;
  const localStart = active >= 0 ? cursor : 0;
  const local = Math.max(0, frame - localStart);
  const inAnim = spring({frame: local, fps, config: {damping: 180, stiffness: 100}});
  const y = interpolate(inAnim, [0, 1], [70, 0]);
  const opacity = interpolate(inAnim, [0, 1], [0, 1]);
  const accent = beat?.emphasis === 'high' ? '#ffffff' : '#9bc7ff';

  return <AbsoluteFill style={{fontFamily: 'Arial, Helvetica, sans-serif', color: 'white'}}>
    <Background />
    {frame < introFrames && <AbsoluteFill style={{padding: '0 150px', justifyContent: 'center'}}>
      <div style={{opacity: titleOpacity, transform: `translateY(${titleY}px)`}}>
        <div style={{fontSize: 28, letterSpacing: 8, color: 'rgba(255,255,255,.62)', marginBottom: 28}}>THE HIDDEN STORY</div>
        <div style={{fontSize: 92, lineHeight: .98, fontWeight: 800, maxWidth: 1500, letterSpacing: -3}}>{title}</div>
        <div style={{width: `${interpolate(frame, [20, 60], [0, 520], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'})}px`, height: 5, marginTop: 42, background: '#fff'}} />
        <div style={{fontSize: 30, marginTop: 28, color: 'rgba(255,255,255,.68)', maxWidth: 1050}}>{subtitle}</div>
      </div>
    </AbsoluteFill>}
    {beat && <AbsoluteFill style={{padding: '0 150px', justifyContent: 'center'}}>
      <div style={{opacity, transform: `translateY(${y}px)`, maxWidth: 1450}}>
        <div style={{fontSize: 24, letterSpacing: 6, textTransform: 'uppercase', color: accent, marginBottom: 24}}>{beat.visual} / {String(active + 1).padStart(2, '0')}</div>
        <div style={{fontSize: beat.visual === 'quote' ? 58 : 72, lineHeight: 1.06, fontWeight: 750, letterSpacing: -2}}>{beat.text}</div>
        <div style={{marginTop: 38, width: 420, height: 3, background: 'rgba(255,255,255,.28)'}} />
      </div>
    </AbsoluteFill>}
  </AbsoluteFill>;
};
