import React from 'react';
import {Composition, registerRoot} from 'remotion';
import {Documentary, DocumentaryProps} from './Documentary';

const calculateMetadata = ({props}: {props: DocumentaryProps}) => {
  const beats = props.beats ?? [];
  const seconds = Math.max(30, beats.reduce((sum, beat) => sum + Math.max(0.5, beat.seconds || 0), 0));
  return {durationInFrames: Math.ceil(seconds * (props.fps || 30))};
};

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="Documentary"
      component={Documentary}
      durationInFrames={900}
      fps={30}
      width={1920}
      height={1080}
      defaultProps={{
        title: 'THE CHIP THAT CHANGED EVERYTHING',
        subtitle: 'A FLVYT documentary prototype',
        fps: 30,
        width: 1920,
        height: 1080,
        beats: [],
      }}
      calculateMetadata={calculateMetadata}
    />
  );
};

registerRoot(RemotionRoot);
