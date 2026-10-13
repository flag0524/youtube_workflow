// 훅·자막·로고를 절제된 모션(페이드, 마지막 자막만 pop, 키워드 색 강조)으로 그리는 투명 오버레이
import React, {useEffect, useState} from 'react';
import {
  AbsoluteFill, continueRender, delayRender, interpolate,
  spring, staticFile, useCurrentFrame, useVideoConfig,
} from 'remotion';

export type Caption = {
  text: string; start: number; end: number;
  keyword: string | null; style: 'fade' | 'pop';
};
export type CaptionProps = {
  width: number; height: number; fps: number; duration: number;
  logo: string; fontFile: string; captionY: number;
  hook: {text: string; end: number; y: number};
  captions: Caption[];
};

const FAMILY = 'MotionFont';
const ACCENT = '#FFE500';
const FADE_FRAMES = 5;

const stroke = (px: number): React.CSSProperties => ({
  WebkitTextStroke: `${px}px #000`,
  paintOrder: 'stroke fill',
  textShadow: '0 4px 12px rgba(0,0,0,0.5)',
});

const useFont = (file: string) => {
  const [handle] = useState(() => delayRender('font'));
  useEffect(() => {
    new FontFace(FAMILY, `url(${staticFile(file)})`, {weight: '700'})
      .load()
      .then((f) => { document.fonts.add(f); continueRender(handle); })
      .catch(() => continueRender(handle));
  }, [file, handle]);
};

const Line: React.FC<{
  text: string; keyword: string | null; size: number; color: string;
  y: number; opacity: number; scale: number; dy: number;
}> = ({text, keyword, size, color, y, opacity, scale, dy}) => {
  const at = keyword ? text.indexOf(keyword) : -1;
  const parts = at < 0
    ? [text]
    : [text.slice(0, at), keyword as string, text.slice(at + (keyword as string).length)];
  return (
    <div style={{
      position: 'absolute', left: 60, right: 60, top: y,
      transform: `translateY(calc(-50% + ${dy}px)) scale(${scale})`,
      opacity, textAlign: 'center', fontFamily: FAMILY, fontWeight: 700,
      fontSize: size, lineHeight: 1.25, color, ...stroke(size * 0.18),
    }}>
      {at < 0 ? text : (
        <>
          {parts[0]}
          <span style={{color: ACCENT}}>{parts[1]}</span>
          {parts[2]}
        </>
      )}
    </div>
  );
};

export const Captions: React.FC<CaptionProps> = (p) => {
  useFont(p.fontFile);
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps;

  const active = p.captions.find((c) => t >= c.start && t < c.end);
  const hookOn = t < p.hook.end;

  const motion = (startSec: number, style: 'fade' | 'pop') => {
    const f = frame - Math.round(startSec * fps);
    if (style === 'pop') {
      const s = spring({frame: f, fps, config: {damping: 12, stiffness: 180}});
      return {opacity: Math.min(1, f / 3), scale: 0.82 + 0.18 * s, dy: 0};
    }
    const k = interpolate(f, [0, FADE_FRAMES], [0, 1], {extrapolateRight: 'clamp'});
    return {opacity: k, scale: 1, dy: (1 - k) * 18};
  };

  return (
    <AbsoluteFill>
      <div style={{
        position: 'absolute', left: 50, top: 50, fontFamily: FAMILY,
        fontWeight: 700, fontSize: 34, color: '#fff', ...stroke(5),
      }}>{p.logo}</div>

      {hookOn && (
        <Line text={p.hook.text} keyword={null} size={104} color={ACCENT}
              y={p.hook.y} {...motion(0, 'pop')} />
      )}
      {active && (
        <Line text={active.text} keyword={active.keyword} size={78}
              color="#fff" y={p.captionY} {...motion(active.start, active.style)} />
      )}
    </AbsoluteFill>
  );
};
