// BRAND-LOGO-01 (owner, 2026-11-10): the Sirf Concepts mark (logo 2A: an idea rising from the open book), drawn as
// vector so it stays sharp at every size. Source: docs/brand/sirf-concepts-icon.svg. `animated` adds a gentle glow and
// ray pulse (globals.css .brand-anim) for the home hero only; it is still for users who reduce motion.

type Props = {
  /** Unique prefix for the gradient ids when the mark appears more than once on a page. */
  id: string;
  animated?: boolean;
  className?: string;
};

export function BrandMark({ id, animated = false, className = "" }: Props) {
  const g = (n: string) => `${id}-${n}`;
  const u = (n: string) => `url(#${g(n)})`;
  return (
    <svg viewBox="0 0 512 512" aria-hidden="true" focusable="false" className={`${animated ? "brand-anim " : ""}${className}`}>
      <defs>
        <linearGradient id={g("tl")} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#1497ae" />
          <stop offset=".55" stopColor="#0b5d73" />
          <stop offset="1" stopColor="#05303c" />
        </linearGradient>
        <linearGradient id={g("gl")} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#fff" stopOpacity=".26" />
          <stop offset=".45" stopColor="#fff" stopOpacity="0" />
        </linearGradient>
        <radialGradient id={g("bulb")} cx=".42" cy=".36" r=".72">
          <stop offset="0" stopColor="#fff6cf" />
          <stop offset=".45" stopColor="#ffd463" />
          <stop offset="1" stopColor="#d48c12" />
        </radialGradient>
        <radialGradient id={g("halo")} cx=".5" cy=".5" r=".5">
          <stop offset="0" stopColor="#ffd463" stopOpacity=".55" />
          <stop offset="1" stopColor="#ffd463" stopOpacity="0" />
        </radialGradient>
        <linearGradient id={g("page")} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#ffffff" />
          <stop offset="1" stopColor="#d6eef4" />
        </linearGradient>
      </defs>
      <rect width="512" height="512" rx="116" fill={u("tl")} />
      <rect width="512" height="512" rx="116" fill={u("gl")} />
      <g transform="translate(256 256) scale(1.1111) translate(-256 -224)">
        <circle className="brand-glow" cx="256" cy="168" r="120" fill={u("halo")} />
        <path d="M256 404C214 376 156 368 98 376V258C156 250 214 256 256 286Z" fill={u("page")} />
        <path d="M256 404C298 376 356 368 414 376V258C356 250 298 256 256 286Z" fill={u("page")} />
        <path
          d="M256 404C214 376 156 368 98 376M256 404C298 376 356 368 414 376"
          fill="none"
          stroke="#05303c"
          strokeOpacity=".25"
          strokeWidth="8"
          strokeLinecap="round"
        />
        <path d="M256 288V402" stroke="#0b5d73" strokeOpacity=".35" strokeWidth="6" strokeLinecap="round" />
        <path
          d="M132 300C168 296 206 302 232 318M132 332C168 328 206 334 232 350M380 300C344 296 306 302 280 318M380 332C344 328 306 334 280 350"
          stroke="#0b5d73"
          strokeOpacity=".28"
          strokeWidth="9"
          strokeLinecap="round"
          fill="none"
        />
        <circle cx="256" cy="166" r="62" fill={u("bulb")} />
        <rect x="234" y="222" width="44" height="22" rx="9" fill="#e9f6f9" />
        <rect x="240" y="246" width="32" height="14" rx="7" fill="#bfe1ea" />
        <path d="M232 172q12-22 24 0q12 22 24 0" fill="none" stroke="#9a5f00" strokeOpacity=".55" strokeWidth="9" strokeLinecap="round" />
        <g stroke="#ffd463" strokeWidth="18" strokeLinecap="round">
          <path className="brand-ray" d="M256 76V52" />
          <path className="brand-ray" d="M180 106l-18-18" />
          <path className="brand-ray" d="M332 106l18-18" />
        </g>
      </g>
    </svg>
  );
}
