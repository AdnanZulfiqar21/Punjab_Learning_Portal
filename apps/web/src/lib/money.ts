// P14.S1.T1 (PRODUCTS-01): money is stored as integer minor units with an ISO 4217 currency code. The exponent comes
// from ISO 4217, not from Intl's display rules: Intl shows PKR with no decimals, so it would turn 2,500.50 (250050
// paisa) into "Rs 2,501". Amounts are shown with exactly the ISO number of decimals.
const ZERO = new Set(["BIF", "CLP", "DJF", "GNF", "ISK", "JPY", "KMF", "KRW", "PYG", "RWF", "UGX", "UYI", "VND", "VUV", "XAF", "XOF", "XPF"]);
const THREE = new Set(["BHD", "IQD", "JOD", "KWD", "LYD", "OMR", "TND"]);

export function minorExponent(currency: string): number {
  return ZERO.has(currency) ? 0 : THREE.has(currency) ? 3 : 2;
}

/** "2500.50" → 250050 for PKR; null when the text isn't a plain amount with at most the currency's decimals. */
export function toMinor(text: string, currency: string): number | null {
  const digits = minorExponent(currency);
  const m = text.trim().match(/^(\d{1,9})(?:\.(\d+))?$/);
  if (!m || (m[2] ?? "").length > digits) return null;
  return Number(m[1]) * 10 ** digits + Number((m[2] ?? "").padEnd(digits, "0") || "0");
}

export function formatMinor(minor: number, currency: string): string {
  const digits = minorExponent(currency);
  const major = (minor / 10 ** digits).toFixed(digits); // exact for integers below 2^53 at these exponents
  const [whole, frac] = major.split(".");
  const grouped = Number(whole).toLocaleString("en-US");
  return `${currency} ${frac ? `${grouped}.${frac}` : grouped}`;
}
