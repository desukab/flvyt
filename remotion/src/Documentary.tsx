import React from 'react';
import {AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';

type Props = {title: string; subtitle: string};

const Background: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const drift = interpolate(frame, [0, 900], [0, -80], {extrapolateRight: 'clamp'});
  return (
    <AbsoluteFill style={{background: '#070b10', overflow: 'hidden'}}>
      <div style={{position: 'absolute', inset: -120, transform: `translate3d(${drift}px, ${drift * 0.35}px, 0)`, background: 'radial-gradient(circle at 20% 30%, rgba(70,130,180,.22), transparent 34%), radial-gradient(circle at 80% 65%, rgba(160,80,210,.18), transparent 30%)'}} />
      <div style={{position: 'absolute', inset: 0, backgroundImage: 'linear-gradient(rgba(255,255,255,.035) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.035) 1px, transparent 1px)', backgroundSize: '80px 80px', opacity: 0.35}} />
      <div style={{position: 'absolute', inset: 0, background: 'radial-gradient(ellipse at center, transparent 35%, rgba(0,0,0,.72) 100%)'}} />
      <div style={{position: 'absolute', right: 70, bottom: 55, fontFamily: 'Arial, sans-serif', fontSize: 22, letterSpacing: 5, color: 'rgba(255,255,255,.32)'}}>FLVYT / 001</div>
    </AbsoluteFill>
  );
};

export const Documentary: React.FC<Props> = ({title, subtitle}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const intro = spring({frame, fps, config: {damping: 200, stiffness: 90}});
  const titleY = interpolate(intro, [0, 1], [90, 0]);
  const titleOpacity = interpolate(intro, [0, 1], [0, 1]);
  const line = interpolate(frame, [20, 60], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const pulse = interpolate(Math.sin(frame / 18), [-1, 1], [0.35, 0.75]);

  return (
    <AbsoluteFill style={{fontFamily: 'Arial, Helvetica, sans-serif', color: 'white'}}>
      <Background />
      <AbsoluteFill style={{padding: '0 150px', justifyContent: 'center'}}>
        <div style={{opacity: titleOpacity, transform: `translateY(${titleY}px)`}}>
          <div style={{fontSize: 28, letterSpacing: 8, color: 'rgba(255,255,255,.62)', marginBottom: 28}}>THE HIDDEN STORY</div>
          <div style={{fontSize: 92, lineHeight: 0.98, fontWeight: 800, maxWidth: 1500, letterSpacing: -3}}>{title}</div>
          <div style={{width: `${line * 520}px`, height: 5, marginTop: 42, background: '#fff', boxShadow: `0 0 30px rgba(150,210,255,${pulse})`}} />
          <div style={{fontSize: 30, marginTop: 28, color: 'rgba(255,255,255,.68)', maxWidth: 1050}}>{subtitle}</div>
        </div>
      </AbsoluteFill>
      <div style={{position: 'absolute', left: 150, bottom: 90, width: 320, height: 2, background: 'rgba(255,255,255,.18)'}} />
    </AbsoluteFill>
  );
};
