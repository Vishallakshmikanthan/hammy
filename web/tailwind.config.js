/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ["class"],
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        navy: {
          DEFAULT: "#14213D",
          deep: "#0B1325",
          light: "#1E3056",
          surface: "rgba(20, 33, 61, 0.65)",
        },
        cream: {
          DEFAULT: "#F4EDE0",
          muted: "#D5CCBC",
          dim: "#9E9587",
        },
        coral: {
          DEFAULT: "#FF6B5B",
          hover: "#FF8274",
          deep: "#E05243",
          glow: "rgba(255, 107, 91, 0.35)",
        },
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      fontFamily: {
        sans: ['"Plus Jakarta Sans"', '"Inter"', "-apple-system", "BlinkMacSystemFont", "sans-serif"],
        display: ['"Instrument Serif"', '"Playfair Display"', "Georgia", "serif"],
        mono: ['"JetBrains Mono"', "ui-monospace", "SFMono-Regular", "monospace"],
      },
      boxShadow: {
        glass: "0 20px 50px rgba(7, 12, 24, 0.55), inset 0 1px 0 0 rgba(244, 237, 224, 0.16)",
        "glass-sm": "0 8px 24px rgba(7, 12, 24, 0.4), inset 0 1px 0 0 rgba(244, 237, 224, 0.12)",
        "coral-glow": "0 8px 30px rgba(255, 107, 91, 0.4), inset 0 1px 0 0 rgba(255, 255, 255, 0.25)",
      },
    },
  },
  plugins: [],
};

