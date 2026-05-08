import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // Kairos AI Design System (matching Lovable UI screenshots)
        kairos: {
          teal: "#2DD4BF",       // Primary teal/green accent
          "teal-dark": "#0F9D8E", // Darker teal for hover
          "teal-light": "#CCFBF1", // Light teal bg
          sidebar: "#0F172A",    // Dark sidebar background
          "sidebar-active": "#1E3A5F", // Active nav item
          red: "#FF0000",        // Emergency red
          "red-dark": "#DC2626", // Dark red
          "red-light": "#FEE2E2", // Light red bg
          green: "#16A34A",      // Safe green (confirmed)
          "green-light": "#DCFCE7",
          amber: "#D97706",      // Warning amber
          "amber-light": "#FEF3C7",
          bg: "#F0FDF9",         // Light mint background
          card: "#FFFFFF",       // Card background
          text: "#0F172A",       // Dark text
          "text-muted": "#64748B", // Muted text
          border: "#E2E8F0",     // Border color
          "badge-pink": "#FCE7F3", // Allergy badge
          "badge-pink-text": "#BE185D",
          "badge-teal": "#CCFBF1", // Blood group badge
          "badge-teal-text": "#0F766E",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
      },
      animation: {
        "pulse-red": "pulse-red 1s ease-in-out infinite",
        "fade-in-up": "fadeInUp 0.4s ease-out",
        "slide-in": "slideIn 0.3s ease-out",
        "spin-slow": "spin 2s linear infinite",
        "flash-red": "flashRed 0.5s ease-in-out 3",
      },
      keyframes: {
        "pulse-red": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.5" },
        },
        fadeInUp: {
          "0%": { opacity: "0", transform: "translateY(10px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        slideIn: {
          "0%": { opacity: "0", transform: "translateX(-10px)" },
          "100%": { opacity: "1", transform: "translateX(0)" },
        },
        flashRed: {
          "0%, 100%": { backgroundColor: "transparent" },
          "50%": { backgroundColor: "#FEE2E2" },
        },
      },
      minHeight: {
        "tap": "48px",
      },
      minWidth: {
        "tap": "48px",
      },
    },
  },
  plugins: [],
};

export default config;
