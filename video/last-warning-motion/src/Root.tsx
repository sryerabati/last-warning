import React from 'react';
import {Composition, cancelRender, continueRender, delayRender, staticFile} from 'remotion';
import {loadFont} from '@remotion/fonts';
import {Title, EndCard, Results, Architecture, Pivot} from './Scenes';
import content from './content.json';
import './style.css';

const handle = delayRender('Loading bundled fonts');
Promise.all([
  loadFont({family: 'Inter', url: staticFile('fonts/Inter.ttf'), weight: '100 900'}),
  loadFont({family: 'Pixelify Sans', url: staticFile('fonts/PixelifySans.ttf'), weight: '400 700'}),
]).then(() => continueRender(handle)).catch(cancelRender);

export const Root = () => <>
  <Composition id="Title" component={Title} width={1920} height={1080} fps={30} durationInFrames={180} defaultProps={content}/>
  <Composition id="EndCard" component={EndCard} width={1920} height={1080} fps={30} durationInFrames={90} defaultProps={content}/>
  <Composition id="Results" component={Results} width={1920} height={1080} fps={30} durationInFrames={510} defaultProps={content}/>
  <Composition id="Architecture" component={Architecture} width={1920} height={1080} fps={30} durationInFrames={960} defaultProps={content}/>
  <Composition id="GPUPivot" component={Pivot} width={1920} height={1080} fps={30} durationInFrames={510} defaultProps={content}/>
</>;
