import { useEffect, useRef, type ReactNode } from 'react';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';

if (typeof window !== 'undefined') {
  gsap.registerPlugin(ScrollTrigger);
}

// Pointy-top hexagon — a nod to Kubernetes' hex branding and the honeycomb of
// services KubeX watches. The scroll dives the viewer through it.
const HEX_PATH = 'M50 1 L93 25.5 L93 74.5 L50 99 L7 74.5 L7 25.5 Z';
const HEX_MASK_SVG_URI = `data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" fill="%23000000"><path d="${HEX_PATH}"/></svg>`;

export interface ScrollZoomRevealProps {
  title?: string;
  subtitle?: ReactNode;
  outroTitle?: ReactNode;
  outroSubtitle?: ReactNode;
  imageSrc?: string;
  className?: string;
}

export function ScrollZoomReveal({
  title = 'KNOW IF YOUR LAST DEPLOY MADE THINGS WORSE.',
  subtitle = (
    <>
      KUBEX CORRELATES <span className="text-accent font-black">GITHUB ACTIONS</span>, <span className="text-accent font-black">ARGOCD</span>,
      AND <span className="text-accent font-black">KUBERNETES</span> RUNTIME HEALTH INTO ONE DEPLOYMENT RECORD — THEN
      SCORES EVERY RELEASE <span className="text-accent font-black">AUTOMATICALLY</span>. NO DASHBOARDS TO BABYSIT.
    </>
  ),
  outroTitle = (
    <>
      SHIP WITH <span className="text-accent font-black">CONFIDENCE.</span>
    </>
  ),
  outroSubtitle = (
    <>
      <span className="text-accent font-black">DORA METRICS</span>, AUTONOMOUS HEALTH SCORING, AND
      NATURAL-LANGUAGE INCIDENT INVESTIGATION THROUGH AN <span className="text-accent font-black">MCP SERVER</span> — THE
      FULL DEPLOYMENT SURFACE, ONE PANE.
    </>
  ),
  imageSrc = 'https://images.unsplash.com/photo-1558494949-ef010cbdcc31?auto=format&fit=crop&w=1920&q=80',
  className = '',
}: ScrollZoomRevealProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const pinRef = useRef<HTMLDivElement>(null);
  const maskLayerRef = useRef<HTMLDivElement>(null);
  const imageRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current || !pinRef.current) return;

    const setMask = (px: number) => {
      const el = maskLayerRef.current;
      if (!el) return;
      el.style.setProperty('--maskW', `${px}px`);
      el.style.webkitMaskSize = `${px}px`;
      el.style.maskSize = `${px}px`;
    };

    // Reduced motion: no scroll-jacking pin, no tall spacer. Show the image at
    // full frame in a single viewport-height band.
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      containerRef.current.style.minHeight = '100vh';
      if (maskLayerRef.current) {
        maskLayerRef.current.style.webkitMaskImage = 'none';
        maskLayerRef.current.style.maskImage = 'none';
      }
      return;
    }

    const ctx = gsap.context(() => {
      const getInitialSize = () => {
        if (window.innerWidth < 640) return 240;
        if (window.innerWidth < 1024) return 320;
        return 400;
      };

      setMask(getInitialSize());

      gsap.timeline({
        scrollTrigger: {
          trigger: containerRef.current,
          start: 'top top',
          end: '+=260%',
          scrub: 1.2,
          pin: pinRef.current,
          pinSpacing: true,
          anticipatePin: 1,
          onUpdate: (self) => {
            const size = getInitialSize() + Math.pow(self.progress, 2.3) * 4500;
            setMask(size);
          },
        },
      }).to(imageRef.current, { scale: 1.22, ease: 'none' }, 0);
    }, containerRef);

    return () => ctx.revert();
  }, []);

  return (
    <div className={`w-full bg-background text-text selection:bg-accent selection:text-background ${className}`}>
      {/* 1. INTRO */}
      <section className="relative w-full min-h-screen bg-background flex flex-col items-center justify-center px-6 md:px-12 lg:px-16 py-12 select-none">
        <div className="w-full max-w-5xl mx-auto flex flex-col items-center text-center px-2 sm:px-4">
          <h1 className="font-heading text-[10vw] sm:text-[8vw] md:text-[6.5rem] lg:text-[7.8rem] font-black uppercase leading-[0.88] tracking-[-0.04em] text-text mb-6 select-none">
            {title}
          </h1>
          <p className="max-w-3xl text-xs sm:text-sm md:text-base uppercase font-bold leading-relaxed tracking-wider text-text-muted">
            {subtitle}
          </p>
        </div>
      </section>

      {/* 2. SCROLL-DIVE THROUGH THE HEXAGON */}
      <div
        ref={containerRef}
        className="relative w-full bg-background text-text"
        style={{ minHeight: '360vh' }}
      >
        <div
          ref={pinRef}
          className="sticky top-0 w-full h-screen overflow-hidden flex items-center justify-center bg-background select-none"
        >
          {/* Corner brackets */}
          {[
            'top-[10px] left-[10px]',
            'top-[10px] right-[10px] rotate-90',
            'bottom-[10px] right-[10px] rotate-180',
            'bottom-[10px] left-[10px] -rotate-90',
          ].map((pos) => (
            <div key={pos} className={`absolute z-30 pointer-events-none w-4 h-4 sm:w-5 sm:h-5 text-text ${pos}`}>
              <svg viewBox="0 0 10 10" fill="none" className="w-full h-full">
                <path d="M10 0V1H1V10H0V0H10Z" fill="currentColor" style={{ mixBlendMode: 'difference' }} />
              </svg>
            </div>
          ))}

          {/* Ambient watermark */}
          <div className="absolute inset-0 flex items-center justify-center opacity-[0.04] pointer-events-none select-none z-0">
            <span className="font-heading text-[20vw] font-black uppercase tracking-tighter text-text">KUBEX</span>
          </div>

          {/* Masked image portal */}
          <div className="absolute inset-0 w-full h-full z-10 flex items-center justify-center">
            <div
              ref={maskLayerRef}
              className="w-full h-full relative overflow-hidden flex items-center justify-center"
              style={{
                WebkitMaskImage: `url('${HEX_MASK_SVG_URI}')`,
                maskImage: `url('${HEX_MASK_SVG_URI}')`,
                WebkitMaskPosition: '50% 50%',
                maskPosition: '50% 50%',
                WebkitMaskRepeat: 'no-repeat',
                maskRepeat: 'no-repeat',
                WebkitMaskSize: 'var(--maskW, 400px)',
                maskSize: 'var(--maskW, 400px)',
                transition: 'mask-size 0.04s linear, -webkit-mask-size 0.04s linear',
              }}
            >
              <div
                ref={imageRef}
                className="w-full h-full bg-cover bg-center grayscale contrast-110 brightness-110 will-change-transform"
                style={{ backgroundImage: `url('${imageSrc}')`, transformOrigin: '50% 50%' }}
              />
            </div>
          </div>
        </div>
      </div>

      {/* 3. OUTRO */}
      <footer className="relative z-10 w-full min-h-screen bg-background text-text flex flex-col items-center justify-center px-6 md:px-12 lg:px-16 py-12 select-none">
        <div className="w-full max-w-5xl mx-auto flex flex-col items-center text-center px-2 sm:px-4">
          <h2 className="font-heading text-[10vw] sm:text-[8vw] md:text-[6.5rem] lg:text-[7.8rem] font-black uppercase leading-[0.88] tracking-[-0.04em] text-text mb-6 select-none">
            {outroTitle}
          </h2>
          <p className="max-w-3xl text-xs sm:text-sm md:text-base uppercase font-bold leading-relaxed tracking-wider text-text-muted">
            {outroSubtitle}
          </p>
        </div>
      </footer>

      <style dangerouslySetInnerHTML={{ __html: `.pin-spacer { background-color: #0A0B0D !important; }` }} />
    </div>
  );
}

export default ScrollZoomReveal;
