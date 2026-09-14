import React from 'react';
import {AbsoluteFill, Easing, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {Visual} from './Visuals';

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
  const drift = interpolate(frame, [0, 9000], [0, -180], {extrapolateRight: 'clamp'});
  return <AbsoluteFill style={{background:'#070b10',overflow:'hidden'}}>
    <div style={{position:'absolute',inset:-180,transform:`translate3d(${drift}px,${drift*.35}px,0)`,background:'radial-gradient(circle at 20% 30%,rgba(70,130,180,.22),transparent 34%),radial-gradient(circle at 80% 65%,rgba(160,80,210,.18),transparent 30%)'}} />
    <div style={{position:'absolute',inset:0,backgroundImage:'linear-gradient(rgba(255,255,255,.035) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.035) 1px,transparent 1px)',backgroundSize:'80px 80px',opacity:.35}} />
    <div style={{position:'absolute',inset:0,background:'radial-gradient(ellipse at center,transparent 35%,rgba(0,0,0,.72) 100%)'}} />
  </AbsoluteFill>;
};

const Intro: React.FC<{title:string;subtitle:string}> = ({title,subtitle}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const p = spring({frame,fps,config:{damping:180,stiffness:80}});
  const y = interpolate(p,[0,1],[70,0],{easing:Easing.out(Easing.cubic)});
  return <AbsoluteFill style={{padding:'0 140px',justifyContent:'center'}}>
    <div style={{opacity:p,transform:`translateY(${y}px)`}}>
      <div style={{fontSize:26,letterSpacing:8,color:'rgba(255,255,255,.55)',marginBottom:28}}>THE HIDDEN STORY / FLVYT</div>
      <div style={{fontSize:92,lineHeight:.98,fontWeight:850,maxWidth:1500,letterSpacing:-4}}>{title}</div>
      <div style={{width:520,height:5,marginTop:42,background:'white',transformOrigin:'left',transform:`scaleX(${interpolate(frame,[15,55],[0,1],{extrapolateLeft:'clamp',extrapolateRight:'clamp'})})`}} />
      <div style={{fontSize:30,marginTop:28,color:'rgba(255,255,255,.68)',maxWidth:1100,lineHeight:1.25}}>{subtitle}</div>
    </div>
  </AbsoluteFill>;
};

export const Documentary: React.FC<DocumentaryProps> = ({title,subtitle,beats}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const introFrames = Math.min(150,Math.round(fps*5));
  let cursor = introFrames;
  let active = -1;
  let activeStart = 0;
  for (let i=0;i<beats.length;i++) {
    const end = cursor + Math.max(15,Math.round(beats[i].seconds*fps));
    if (frame >= cursor && frame < end) {active=i;activeStart=cursor;break;}
    cursor=end;
  }
  const beat = active >= 0 ? beats[active] : undefined;
  const local = Math.max(0,frame-activeStart);
  const p = beat ? spring({frame:local,fps,config:{damping:170,stiffness:95}}) : 0;
  const x = interpolate(p,[0,1],[45,0],{extrapolateRight:'clamp'});
  const opacity = interpolate(p,[0,1],[0,1],{extrapolateRight:'clamp'});
  const outro = beat ? Math.max(0,Math.round(beat.seconds*fps)-18) : 0;
  const outP = beat ? interpolate(local,[outro,outro+18],[1,0],{extrapolateLeft:'clamp',extrapolateRight:'clamp'}) : 1;
  return <AbsoluteFill style={{fontFamily:'Arial,Helvetica,sans-serif',color:'white'}}>
    <Background />
    {frame < introFrames && <Intro title={title} subtitle={subtitle} />}
    {beat && <AbsoluteFill style={{opacity:opacity*outP}}>
      <div style={{position:'absolute',top:62,left:80,right:80,display:'flex',justifyContent:'space-between',alignItems:'center'}}>
        <div style={{fontSize:20,letterSpacing:5,color:'rgba(255,255,255,.48)'}}>{String(active+1).padStart(2,'0')} / {String(beats.length).padStart(2,'0')}</div>
        <div style={{fontSize:20,letterSpacing:4,color:'rgba(255,255,255,.42)',textTransform:'uppercase'}}>{beat.label || beat.visual}</div>
      </div>
      <AbsoluteFill style={{display:'flex',alignItems:'center',justifyContent:'center',transform:`translateX(${x}px)`}}>
        <Visual {...beat} />
      </AbsoluteFill>
      <div style={{position:'absolute',left:80,right:80,bottom:35,height:2,background:'rgba(255,255,255,.12)'}}>
        <div style={{height:'100%',width:`${Math.min(100,(local/(Math.max(1,beat.seconds*fps)))*100)}%`,background:'rgba(255,255,255,.72)'}} />
      </div>
    </AbsoluteFill>}
  </AbsoluteFill>;
};
