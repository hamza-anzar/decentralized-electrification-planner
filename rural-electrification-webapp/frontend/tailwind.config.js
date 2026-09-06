/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#eef5fd",
          100: "#d9e9fb",
          200: "#b3d3f6",
          300: "#82b6ee",
          400: "#4f93e2",
          500: "#2a78d6",
          600: "#1f5fb3",
          700: "#1a4c8f",
          800: "#183f73",
          900: "#17355f",
        },
        ink: {
          50: "#f7f7f6",
          100: "#eeede9",
          200: "#e1e0d9",
          300: "#c3c2b7",
          400: "#989688",
          500: "#767468",
          600: "#59574d",
          700: "#43423a",
          800: "#2c2b26",
          900: "#0b0b0b",
        },
        sun: "#eda100",
        leaf: "#1baf7a",
        coral: "#eb6834",
        grape: "#7a5cd6",
        blossom: "#d65c9e",
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        display: ["Manrope", "Inter", "ui-sans-serif", "system-ui", "sans-serif"],
      },
      boxShadow: {
        card: "0 1px 2px rgba(11,11,11,0.04), 0 8px 24px -12px rgba(11,11,11,0.12)",
        "card-hover": "0 4px 12px rgba(11,11,11,0.08), 0 16px 40px -12px rgba(11,11,11,0.18)",
        glow: "0 0 0 4px rgba(42,120,214,0.12)",
      },
      backgroundImage: {
        "grid-fade": "radial-gradient(circle at 1px 1px, rgba(11,11,11,0.06) 1px, transparent 0)",
      },
      keyframes: {
        "fade-up": {
          "0%": { opacity: 0, transform: "translateY(8px)" },
          "100%": { opacity: 1, transform: "translateY(0)" },
        },
        "count-in": {
          "0%": { opacity: 0, transform: "scale(0.92)" },
          "100%": { opacity: 1, transform: "scale(1)" },
        },
      },
      animation: {
        "fade-up": "fade-up 0.45s ease-out both",
        "count-in": "count-in 0.35s ease-out both",
      },
    },
  },
  plugins: [],
}
