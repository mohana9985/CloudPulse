// The list must match backend/app/database/seed.py (slug + name + category).
import { mkdirSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const outDir = join(dirname(fileURLToPath(import.meta.url)), '..', 'public', 'products')

const categories = {
  Electronics: { bg: '#e8eef8', fg: '#233d6c',
    icon: '<rect x="130" y="110" width="140" height="95" rx="8" fill="none" stroke="FG" stroke-width="10"/><path d="M175 230h50M200 205v25" stroke="FG" stroke-width="10" stroke-linecap="round"/>' },
  'Home & Kitchen': { bg: '#eaf3f1', fg: '#1f5a52',
    icon: '<path d="M140 150h120v60a30 30 0 0 1-30 30h-60a30 30 0 0 1-30-30z" fill="none" stroke="FG" stroke-width="10" stroke-linejoin="round"/><path d="M260 165h18a14 14 0 0 1 0 28h-18M170 110v20M200 100v30M230 110v20" fill="none" stroke="FG" stroke-width="10" stroke-linecap="round"/>' },
  Books: { bg: '#f4efe6', fg: '#6b4a1e',
    icon: '<path d="M200 125c-25-15-55-15-75-8v110c20-7 50-7 75 8 25-15 55-15 75-8V117c-20-7-50-7-75 8z" fill="none" stroke="FG" stroke-width="10" stroke-linejoin="round"/><path d="M200 125v110" stroke="FG" stroke-width="10"/>' },
  'Sports & Fitness': { bg: '#eef4e8', fg: '#3c5a1f',
    icon: '<path d="M140 175h120" stroke="FG" stroke-width="12" stroke-linecap="round"/><rect x="118" y="140" width="22" height="70" rx="6" fill="FG"/><rect x="260" y="140" width="22" height="70" rx="6" fill="FG"/><rect x="100" y="155" width="18" height="40" rx="5" fill="FG"/><rect x="282" y="155" width="18" height="40" rx="5" fill="FG"/>' },
  Fashion: { bg: '#f3ecf3', fg: '#5b2d5b',
    icon: '<path d="M165 115l-45 25 15 35 20-8v73h90v-73l20 8 15-35-45-25c-5 15-18 22-35 22s-30-7-35-22z" fill="none" stroke="FG" stroke-width="10" stroke-linejoin="round"/>' },
  'Office Supplies': { bg: '#eef0f3', fg: '#37414f',
    icon: '<rect x="140" y="105" width="110" height="140" rx="8" fill="none" stroke="FG" stroke-width="10"/><path d="M162 145h66M162 175h66M162 205h40" stroke="FG" stroke-width="9" stroke-linecap="round"/><path d="M275 120l15 15-45 95-20 8 2-22z" fill="FG"/>' },
}

const products = [
  ['wireless-headphones', 'Wireless Noise-Cancelling Headphones', 'Electronics'],
  ['mechanical-keyboard', 'Mechanical Keyboard (TKL)', 'Electronics'],
  ['qhd-monitor', '27-inch QHD Monitor', 'Electronics'],
  ['power-bank', 'Portable Power Bank 20000mAh', 'Electronics'],
  ['steel-bottle', 'Stainless Steel Water Bottle 1L', 'Home & Kitchen'],
  ['frying-pan', 'Non-Stick Frying Pan 26cm', 'Home & Kitchen'],
  ['electric-kettle', 'Electric Kettle 1.5L', 'Home & Kitchen'],
  ['dinner-set', 'Ceramic Dinner Set (16 pieces)', 'Home & Kitchen'],
  ['book-cloud-computing', 'Cloud Computing: Concepts and Practice', 'Books'],
  ['book-reliable-systems', 'Designing Reliable Web Systems', 'Books'],
  ['book-python-data', 'Python for Data Engineers', 'Books'],
  ['book-linux-cli', 'Linux Command Line Handbook', 'Books'],
  ['yoga-mat', 'Yoga Mat 6mm', 'Sports & Fitness'],
  ['dumbbell-set', 'Adjustable Dumbbell Set 20kg', 'Sports & Fitness'],
  ['running-shoes', 'Running Shoes - Lightweight', 'Sports & Fitness'],
  ['badminton-racket', 'Badminton Racket Pair', 'Sports & Fitness'],
  ['cotton-tshirt', 'Classic Cotton T-Shirt', 'Fashion'],
  ['denim-jacket', 'Denim Jacket', 'Fashion'],
  ['leather-wallet', 'Leather Wallet', 'Fashion'],
  ['analog-watch', 'Analog Wrist Watch', 'Fashion'],
  ['notebook-pack', 'A5 Hardcover Notebook (Pack of 3)', 'Office Supplies'],
  ['office-chair', 'Ergonomic Office Chair', 'Office Supplies'],
  ['desk-organizer', 'Desk Organizer Set', 'Office Supplies'],
  ['gel-pens', 'Gel Pen Set (12 colours)', 'Office Supplies'],
]

const escape = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')

function wrap(text, max = 24) {
  const lines = ['']
  for (const word of text.split(' ')) {
    const current = lines[lines.length - 1]
    if ((current + ' ' + word).trim().length > max && current) lines.push(word)
    else lines[lines.length - 1] = (current + ' ' + word).trim()
  }
  return lines.slice(0, 2)
}

mkdirSync(outDir, { recursive: true })
for (const [slug, name, category] of products) {
  const { bg, fg, icon } = categories[category]
  const lines = wrap(name)
  const text = lines
    .map((line, i) => `<text x="200" y="${300 + i * 26}" text-anchor="middle" font-family="Helvetica, Arial, sans-serif" font-size="20" font-weight="600" fill="${fg}">${escape(line)}</text>`)
    .join('')
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 400" width="400" height="400" role="img" aria-label="${escape(name)}">
<rect width="400" height="400" fill="${bg}"/>
<circle cx="200" cy="172" r="105" fill="#ffffff" opacity="0.7"/>
${icon.replaceAll('FG', fg)}
${text}
<text x="200" y="372" text-anchor="middle" font-family="Helvetica, Arial, sans-serif" font-size="13" letter-spacing="2" fill="${fg}" opacity="0.7">${escape(category.toUpperCase())}</text>
</svg>
`
  writeFileSync(join(outDir, `${slug}.svg`), svg)
}
console.log(`Generated ${products.length} product images in ${outDir}`)
