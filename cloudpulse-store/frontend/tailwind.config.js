/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        navy: {
          50: '#f0f4fa',
          100: '#dce5f3',
          200: '#b9cbe6',
          300: '#8aa8d3',
          400: '#5a80bb',
          500: '#3b62a3',
          600: '#2c4d87',
          700: '#233d6c',
          800: '#1b2f54',
          900: '#13223d',
          950: '#0c1628',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'Segoe UI', 'Roboto', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
