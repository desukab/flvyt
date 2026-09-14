import React from 'react';
import {Composition, registerRoot} from 'remotion';
import {Documentary} from './Documentary';

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
      }}
    />
  );
};

registerRoot(RemotionRoot);
