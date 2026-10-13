// 모션 자막 오버레이 컴포지션을 등록하고 길이·해상도를 props 에서 정한다.
import {Composition} from 'remotion';
import {Captions, CaptionProps} from './Captions';

const defaults: CaptionProps = {
  width: 1080, height: 1920, fps: 30, duration: 3,
  logo: 'AI 일잘러', fontFile: 'font.ttf',
  hook: {text: '훅 예시', end: 2, y: 760},
  captionY: 960,
  captions: [{text: '자막 예시', start: 0, end: 3, keyword: '예시', style: 'fade'}],
};

export const Root = () => (
  <Composition
    id="Captions"
    component={Captions}
    width={defaults.width}
    height={defaults.height}
    fps={defaults.fps}
    durationInFrames={90}
    defaultProps={defaults}
    calculateMetadata={({props}) => ({
      durationInFrames: Math.max(1, Math.ceil(props.duration * props.fps)),
      fps: props.fps,
      width: props.width,
      height: props.height,
    })}
  />
);
