/** Minimal inline stroke icons (24×24, currentColor) — no icon dependency. */
type P = { size?: number };
const base = (size = 20) => ({
  width: size,
  height: size,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.8,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
});

export const HomeIcon = ({ size }: P) => (
  <svg {...base(size)}>
    <path d="M3 10.5 12 4l9 6.5" />
    <path d="M5 9.5V20h14V9.5" />
  </svg>
);
export const ListIcon = ({ size }: P) => (
  <svg {...base(size)}>
    <path d="M8 6h13M8 12h13M8 18h13" />
    <circle cx="3.5" cy="6" r="1" fill="currentColor" stroke="none" />
    <circle cx="3.5" cy="12" r="1" fill="currentColor" stroke="none" />
    <circle cx="3.5" cy="18" r="1" fill="currentColor" stroke="none" />
  </svg>
);
export const SparkIcon = ({ size }: P) => (
  <svg {...base(size)}>
    <path d="M12 3v4M12 17v4M3 12h4M17 12h4M6.5 6.5l2 2M15.5 15.5l2 2M17.5 6.5l-2 2M8.5 15.5l-2 2" />
  </svg>
);
export const CalendarIcon = ({ size }: P) => (
  <svg {...base(size)}>
    <rect x="3" y="5" width="18" height="16" rx="2" />
    <path d="M3 9h18M8 3v4M16 3v4" />
  </svg>
);
export const SettingsIcon = ({ size }: P) => (
  <svg {...base(size)}>
    <circle cx="12" cy="12" r="3" />
    <path d="M19 12a7 7 0 0 0-.1-1l2-1.5-2-3.4-2.3 1a7 7 0 0 0-1.7-1l-.3-2.5H9.4L9 6.6a7 7 0 0 0-1.7 1l-2.3-1-2 3.4L3 11a7 7 0 0 0 0 2l-2 1.5 2 3.4 2.3-1a7 7 0 0 0 1.7 1l.4 2.5h4.2l.3-2.5a7 7 0 0 0 1.7-1l2.3 1 2-3.4-2-1.5a7 7 0 0 0 .1-1Z" />
  </svg>
);
export const SearchIcon = ({ size }: P) => (
  <svg {...base(size)}>
    <circle cx="11" cy="11" r="7" />
    <path d="m20 20-3.5-3.5" />
  </svg>
);
export const PlusIcon = ({ size }: P) => (
  <svg {...base(size)}>
    <path d="M12 5v14M5 12h14" />
  </svg>
);
export const UploadIcon = ({ size }: P) => (
  <svg {...base(size)}>
    <path d="M12 16V4M7 9l5-5 5 5" />
    <path d="M5 20h14" />
  </svg>
);
export const MicIcon = ({ size }: P) => (
  <svg {...base(size)}>
    <rect x="9" y="3" width="6" height="11" rx="3" />
    <path d="M5 11a7 7 0 0 0 14 0M12 18v3" />
  </svg>
);
export const BotIcon = ({ size }: P) => (
  <svg {...base(size)}>
    <rect x="4" y="8" width="16" height="11" rx="3" />
    <path d="M12 8V4M9 13h.01M15 13h.01" />
  </svg>
);
export const ChevronDown = ({ size }: P) => (
  <svg {...base(size)}>
    <path d="m6 9 6 6 6-6" />
  </svg>
);
export const DotsIcon = ({ size }: P) => (
  <svg {...base(size)}>
    <circle cx="12" cy="5" r="1.4" fill="currentColor" stroke="none" />
    <circle cx="12" cy="12" r="1.4" fill="currentColor" stroke="none" />
    <circle cx="12" cy="19" r="1.4" fill="currentColor" stroke="none" />
  </svg>
);
export const LogoutIcon = ({ size }: P) => (
  <svg {...base(size)}>
    <path d="M15 4h3a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-3M10 12H3M6 8l-3 4 3 4" />
  </svg>
);
export const BackIcon = ({ size }: P) => (
  <svg {...base(size)}>
    <path d="M15 18l-6-6 6-6" />
  </svg>
);
export const CheckSquareIcon = ({ size }: P) => (
  <svg {...base(size)}>
    <path d="M9 11.5l2.2 2.2L15.5 9" />
    <rect x="3.5" y="3.5" width="17" height="17" rx="4" />
  </svg>
);
export const CheckIcon = ({ size }: P) => (
  <svg {...base(size)}>
    <path d="M5 12.5l4.5 4.5L19 7" />
  </svg>
);
