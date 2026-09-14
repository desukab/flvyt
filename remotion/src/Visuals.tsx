import React from 'react';
import {Img, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';

export type VisualBeat = {
  visual: string;
  text: string;
  seconds: number;
  emphasis?: string;
  assetSrc?: string;
  label?: string;
  value?: number;
  unit?: string;
};

const Glass: React.FC<{children: React.ReactNode; style?: React.CSSProperties}> = ({children, style}) => (
  <div style={{background:'rgba(10,15,22,.72)',border:'1px solid rgba(255,255,255,.12)',boxShadow:'0 30px 80px rgba(0,0,0,.35)',borderRadius:18,backdropFilter:'blur(12px)',...style}}>{children}</div>
);

export const StatVisual: React.FC<VisualBeat> = ({text,value=94,unit='%'}) => {
  const frame=useCurrentFrame(); const {fps}=useVideoConfig();
  const p=spring({frame,fps,config:{damping:180,stiffness:80}});
  const n=Math.round(interpolate(p,[0,1],[0,value]));
  return <Glass style={{padding:52,width:760}}>
    <div style={{fontSize:118,fontWeight:850,letterSpacing:-7}}>{n}<span style={{fontSize:54,marginLeft:10,opacity:.65}}>{unit}</span></div>
    <div style={{height:8,background:'rgba(255,255,255,.1)',margin:'30px 0',borderRadius:8}}><div style={{height:'100%',width:`${Math.min(100,n)}%`,background:'white',borderRadius:8}} /></div>
    <div style={{fontSize:28,lineHeight:1.25,color:'rgba(255,255,255,.76)'}}>{text}</div>
  </Glass>;
};

export const TimelineVisual: React.FC<VisualBeat> = ({text}) => <Glass style={{padding:50,width:1320}}>
  <div style={{fontSize:25,letterSpacing:6,opacity:.55,marginBottom:34}}>THE TIMELINE</div>
  <div style={{position:'relative',height:110}}>
    <div style={{position:'absolute',left:0,right:0,top:42,height:4,background:'rgba(255,255,255,.25)'}} />
    {[0,1,2,3,4].map(i=><div key={i} style={{position:'absolute',left:`${i*25}%`,top:23,width:42,height:42,borderRadius:'50%',background:'white',boxShadow:'0 0 0 8px rgba(255,255,255,.08)'}} />)}
  </div>
  <div style={{fontSize:34,lineHeight:1.25,maxWidth:1100}}>{text}</div>
</Glass>;

export const MapVisual: React.FC<VisualBeat> = ({text}) => {
  const frame=useCurrentFrame(); const drift=interpolate(frame,[0,180],[0,-40],{extrapolateRight:'clamp'});
  return <Glass style={{padding:35,width:1360,height:600,overflow:'hidden',position:'relative'}}>
    <div style={{position:'absolute',inset:-100,transform:`translateX(${drift}px)`,opacity:.9,backgroundImage:'radial-gradient(circle,rgba(255,255,255,.32) 1px,transparent 1px)',backgroundSize:'34px 34px'}} />
    <div style={{position:'absolute',left:220,top:150,width:900,height:3,background:'rgba(255,255,255,.18)',transform:'rotate(-8deg)'}} />
    {[[280,150],[650,275],[1010,180],[830,440]].map(([x,y],i)=><div key={i} style={{position:'absolute',left:x,top:y,width:24,height:24,borderRadius:'50%',background:'white',boxShadow:'0 0 0 14px rgba(255,255,255,.09)'}} />)}
    <div style={{position:'absolute',left:60,bottom:45,fontSize:31,maxWidth:950}}>{text}</div>
  </Glass>;
};

export const QuoteVisual: React.FC<VisualBeat> = ({text}) => <Glass style={{padding:65,width:1320,borderLeft:'5px solid white'}}>
  <div style={{fontSize:80,lineHeight:.8,opacity:.35}}>“</div>
  <div style={{fontSize:55,lineHeight:1.12,fontWeight:650,maxWidth:1180}}>{text}</div>
</Glass>;

export const AssetVisual: React.FC<VisualBeat> = ({text,assetSrc}) => {
  const frame=useCurrentFrame(); const scale=interpolate(frame,[0,180],[1,1.08],{extrapolateRight:'clamp'});
  const src=assetSrc ? (assetSrc.startsWith('http://') || assetSrc.startsWith('https://') ? assetSrc : staticFile(assetSrc.replace(/^\//,''))) : undefined;
  return <div style={{position:'relative',width:'100%',height:'100%',overflow:'hidden'}}>
    {src ? <Img src={src} style={{width:'100%',height:'100%',objectFit:'cover',transform:`scale(${scale})`,filter:'brightness(.55) saturate(.8)'}} /> : <div style={{position:'absolute',inset:0,background:'linear-gradient(135deg,#101923,#2c3948)'}} />}
    <div style={{position:'absolute',inset:0,background:'linear-gradient(90deg,rgba(0,0,0,.82),rgba(0,0,0,.08))'}} />
    <div style={{position:'absolute',left:120,bottom:110,maxWidth:1100,fontSize:58,fontWeight:750,lineHeight:1.08}}>{text}</div>
  </div>;
};

export const Visual: React.FC<VisualBeat> = props => {
  switch(props.visual){
    case 'stat': case 'counter': return <StatVisual {...props}/>;
    case 'timeline': return <TimelineVisual {...props}/>;
    case 'map': return <MapVisual {...props}/>;
    case 'quote': return <QuoteVisual {...props}/>;
    case 'broll': case 'image': return <AssetVisual {...props}/>;
    default: return <AssetVisual {...props}/>;
  }
};
