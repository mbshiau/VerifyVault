import type { Config } from "tailwindcss";

export default {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        stone: {
          50: "#fafaf9",
          100: "#f5f5f4",
          200: "#e7e5e4",
          300: "#d6d3d1",
          400: "#a8a29e",
          500: "#78716b",
          600: "#57534e",
          700: "#44403c",
          800: "#292524",
          900: "#1c1917",
        },
        brand: {
          50: "#f9f7f4",
          100: "#f3ede7",
          200: "#e3d5c9",
          300: "#d4bcab",
          400: "#b8976f",
          500: "#9d7d52",
          600: "#866d45",
          700: "#6b5637",
          800: "#563f29",
          900: "#44301d",
        },
        blueberry: {
          50: "#f0f4fd",
          100: "#e1ebfb",
          200: "#c3d6f7",
          300: "#9eb5f0",
          400: "#7a94e8",
          500: "#5a73e0",
          600: "#4557d4",
          700: "#3944c2",
          800: "#2f389f",
          900: "#2a2f7f",
        },
      },
      borderRadius: {
        xs: "0.25rem",
        sm: "0.375rem",
        DEFAULT: "0.5rem",
        md: "0.625rem",
        lg: "0.75rem",
      },
    },
  },
  plugins: [],
} satisfies Config;
