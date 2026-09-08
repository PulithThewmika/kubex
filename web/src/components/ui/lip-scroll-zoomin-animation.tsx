import { useEffect, useRef, type ReactNode } from 'react';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';

if (typeof window !== 'undefined') {
  gsap.registerPlugin(ScrollTrigger);
}

// ── Exact SVG Lip Silhouette ──────────
const SEROTONIN_LIP_PATH =
  'M94.5053 14.6345C101.806 21.8528 109.576 28.4892 117.183 35.3664C117.5 35.6528 118.143 36.1983 118.391 36.4777C118.488 36.586 118.486 36.8137 118.583 36.8866C118.626 36.919 118.776 36.8339 118.94 36.9271C119.6 37.3015 120.309 38.3035 121 38.7073C119.258 40.2498 117.259 41.4714 115.196 42.5291C111.659 51.5094 106.633 60.1751 101.083 68.0401C97.8398 72.6351 94.5254 76.9982 89.8775 80.236C83.5141 84.67 75.4141 87.7104 67.7704 88.9421C66.7866 89.101 65.7837 89.1475 64.8229 89.3641L64.7727 88.9593L64.5214 89.2123L64.7214 89.3631C63.5999 89.4694 62.4773 89.6728 61.3538 89.768C54.7181 90.3297 47.6582 89.9663 41.3773 87.6223C35.851 85.5596 31.0704 81.9727 26.533 78.2786V77.726C26.3532 77.6622 26.2848 77.8909 26.1823 77.894C26.0014 77.899 23.7433 75.8455 23.4157 75.551C19.9707 72.4519 16.7739 69.0664 13.6143 65.6769L13.6686 65.1759C13.0294 65.3388 13.2998 65.2639 13.0214 64.9704C10.2759 62.0809 7.78657 58.9545 5.32644 55.8139L0.100663 54.5468C0.306679 54.3292 -0.0219412 54.1126 0.00117277 53.9952C0.0162471 53.9162 0.230302 53.8707 0.304669 53.7644C0.692582 53.2098 1.20813 52.2847 1.65433 51.81C1.81512 51.639 2.17891 51.5206 2.19499 51.4943C2.25228 51.4001 2.18193 51.1684 2.26032 51.0044C2.32664 50.8657 2.59597 50.805 2.70953 50.636C2.78892 50.5186 2.72461 50.3425 2.7638 50.2888C2.82912 50.2008 3.00901 50.2969 3.06529 50.2028C3.16076 50.0429 3.18789 49.7231 3.33663 49.4559C4.94456 46.5825 7.1635 43.7001 8.86188 40.7498C13.6475 32.4364 17.2563 22.875 22.6308 15.0434C29.4715 5.07617 41.4999 -0.321381 51.9042 8.29668C52.5886 8.86346 53.3966 9.8877 54.0156 10.3199C54.101 10.3796 54.1151 10.4606 54.2668 10.4191C55.911 4.51951 61.7437 1.02472 67.4951 0.208961C73.7771 -0.68169 80.8248 1.30709 85.5753 5.55793C88.6354 8.29668 91.5447 11.7105 94.5013 14.6345H94.5053Z';

const LIP_MASK_SVG_URI = `data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 121 90" fill="%23000000"><path d="${SEROTONIN_LIP_PATH}"/></svg>`;

export interface LipScrollZoominAnimationProps {
  title?: string;
  subtitle?: ReactNode;
  outroTitle?: ReactNode;
  outroSubtitle?: ReactNode;
  videoSrc?: string;
  posterSrc?: string;
  className?: string;
}

export function LipScrollZoominAnimation({
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
  videoSrc = 'https://res.cloudinary.com/dsuwzuaxp/video/upload/cinematic_drone_videos_shew9q.mp4',
  posterSrc = 'https://images.unsplash.com/photo-1451187580459-43490279c0fa?auto=format&fit=crop&w=1920&q=80',
  className = '',
}: LipScrollZoominAnimationProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const pinRef = useRef<HTMLDivElement>(null);
  const maskLayerRef = useRef<HTMLDivElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    if (!containerRef.current || !pinRef.current) return;

    if (videoRef.current) {
      videoRef.current.defaultMuted = true;
      videoRef.current.muted = true;
      videoRef.current.play().catch(() => {});
    }

    const ctx = gsap.context(() => {
      const getInitialSize = () => {
        if (typeof window === 'undefined') return 360;
        if (window.innerWidth < 640) return 260;
        if (window.innerWidth < 1024) return 340;
        return 420;
      };

      const initialSize = getInitialSize();

      if (maskLayerRef.current) {
        maskLayerRef.current.style.setProperty('--maskW', `${initialSize}px`);
        maskLayerRef.current.style.webkitMaskSize = `${initialSize}px`;
        maskLayerRef.current.style.maskSize = `${initialSize}px`;
      }

      const tl = gsap.timeline({
        scrollTrigger: {
          trigger: containerRef.current,
          start: 'top top',
          end: '+=260%',
          scrub: 1.2,
          pin: pinRef.current,
          pinSpacing: true,
          anticipatePin: 1,
          onUpdate: (self) => {
            const progress = self.progress;
            const startSize = getInitialSize();
            const currentSize = startSize + Math.pow(progress, 2.3) * 4500;
            if (maskLayerRef.current) {
              maskLayerRef.current.style.setProperty('--maskW', `${currentSize}px`);
              maskLayerRef.current.style.webkitMaskSize = `${currentSize}px`;
              maskLayerRef.current.style.maskSize = `${currentSize}px`;
            }
          },
        },
      });

      tl.to(
        videoRef.current,
        {
          scale: 1.22,
          ease: 'none',
        },
        0
      );
    }, containerRef);

    return () => ctx.revert();
  }, []);

  return (
    <div className={`w-full bg-background text-text selection:bg-accent selection:text-background ${className}`}>
      {/* 1. INTRO SECTION */}
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

      {/* 2. PURE SOLO LIP SCROLL DIVE SECTION */}
      <div
        ref={containerRef}
        className="relative w-full bg-background text-text selection:bg-accent selection:text-background"
        style={{ minHeight: '360vh' }}
      >
        <div
          ref={pinRef}
          className="motion-section__pin sticky top-0 w-full h-screen overflow-hidden flex items-center justify-center bg-background select-none relative"
        >
          {/* Top-Left Corner */}
          <div className="absolute top-[10px] left-[10px] z-30 pointer-events-none w-4 h-4 sm:w-5 sm:h-5 text-text">
            <svg xmlns="http://www.w3.org/2000/svg" width="100%" height="100%" viewBox="0 0 10 10" fill="none" className="w-full h-full">
              <path d="M10 0V1H1V10H0V0H10Z" fill="currentColor" style={{ mixBlendMode: 'difference' }} />
            </svg>
          </div>

          {/* Top-Right Corner */}
          <div className="absolute top-[10px] right-[10px] z-30 pointer-events-none w-4 h-4 sm:w-5 sm:h-5 text-text">
            <svg xmlns="http://www.w3.org/2000/svg" width="100%" height="100%" viewBox="0 0 10 10" fill="none" className="w-full h-full">
              <path d="M10 0V10H9V1H0V0H10Z" fill="currentColor" style={{ mixBlendMode: 'difference' }} />
            </svg>
          </div>

          {/* Bottom-Left Corner */}
          <div className="absolute bottom-[10px] left-[10px] z-30 pointer-events-none w-4 h-4 sm:w-5 sm:h-5 text-text">
            <svg xmlns="http://www.w3.org/2000/svg" width="100%" height="100%" viewBox="0 0 10 10" fill="none" className="w-full h-full">
              <path d="M-4.37116e-07 0L1 -4.37114e-08L1 9L10 9L10 10L0 10L-4.37116e-07 0Z" fill="currentColor" style={{ mixBlendMode: 'difference' }} />
            </svg>
          </div>

          {/* Bottom-Right Corner */}
          <div className="absolute bottom-[10px] right-[10px] z-30 pointer-events-none w-4 h-4 sm:w-5 sm:h-5 text-text">
            <svg xmlns="http://www.w3.org/2000/svg" width="100%" height="100%" viewBox="0 0 10 10" fill="none" className="w-full h-full">
              <path d="M10 10L-4.37114e-07 10L-3.93402e-07 9L9 9L9 -4.37114e-08L10 0L10 10Z" fill="currentColor" style={{ mixBlendMode: 'difference' }} />
            </svg>
          </div>

          {/* Subtle Ambient Background Watermark */}
          <div className="absolute inset-0 flex items-center justify-center opacity-[0.04] pointer-events-none select-none z-0">
            <span className="font-heading text-[20vw] font-black uppercase tracking-tighter text-text">
              KUBEX
            </span>
          </div>

          {/* Pure Solo Lip Mask Video Portal */}
          <div className="absolute inset-0 w-full h-full z-10 flex items-center justify-center">
            <div
              ref={maskLayerRef}
              className="motion-section__bottom w-full h-full relative overflow-hidden flex items-center justify-center"
              style={{
                WebkitMaskImage: `url('${LIP_MASK_SVG_URI}')`,
                maskImage: `url('${LIP_MASK_SVG_URI}')`,
                WebkitMaskPosition: '50% 50%',
                maskPosition: '50% 50%',
                WebkitMaskRepeat: 'no-repeat',
                maskRepeat: 'no-repeat',
                WebkitMaskSize: 'var(--maskW, 420px)',
                maskSize: 'var(--maskW, 420px)',
                transition: 'mask-size 0.04s linear, -webkit-mask-size 0.04s linear',
              }}
            >
              <video
                ref={videoRef}
                className="motion-section__video lazy-video-section w-full h-full object-cover will-change-transform bg-black"
                loop
                muted
                playsInline
                autoPlay
                preload="auto"
                poster={posterSrc}
                style={{
                  transform: 'scale(1.0)',
                  transformOrigin: '50% 50%',
                }}
              >
                <source src={videoSrc} type="video/mp4" />
                <source src="https://res.cloudinary.com/dsuwzuaxp/video/upload/856381-hd_1920_1080_30fps_gsq11b.mp4" type="video/mp4" />
              </video>
            </div>
          </div>
        </div>
      </div>

      {/* 3. OUTRO SECTION */}
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

      <style
        dangerouslySetInnerHTML={{
          __html: `
            .pin-spacer {
              background-color: #0A0B0D !important;
            }
          `,
        }}
      />
    </div>
  );
}

export default LipScrollZoominAnimation;
