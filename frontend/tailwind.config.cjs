/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        display: ["Space Grotesk", "sans-serif"],
        body: ["IBM Plex Sans", "sans-serif"]
      },
      colors: {
        base: {
          50: "#f4f4ef",
          100: "#e3e4da",
          900: "#111310"
        },
        accent: {
          500: "#12806d",
          600: "#0d6355",
          700: "#07493e"
        },
        warm: {
          300: "#f7bf76",
          500: "#ec8f2f"
        }
      }
    }
  },
  plugins: []
};

