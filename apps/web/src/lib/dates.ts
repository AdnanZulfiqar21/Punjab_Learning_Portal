// Dates are shown in Pakistan time everywhere (P12.S4.T3, DAYS-01), the same day the API counts for a learner.
// Server-rendered pages would otherwise use the server's timezone (UTC in production) and show a different day from
// the phone app between midnight and 05:00; client components would not match their own server render.
export const TIME_ZONE = "Asia/Karachi";

/** The Pakistan calendar day `n` days from now, as YYYY-MM-DD (for date inputs and API date parameters). */
export function daysFromToday(n: number): string {
  const parts = new Intl.DateTimeFormat("en-GB", { timeZone: TIME_ZONE, year: "numeric", month: "2-digit", day: "2-digit" }).formatToParts(
    new Date(Date.now() + n * 86_400_000),
  );
  const part = (type: string) => parts.find((p) => p.type === type)?.value ?? "";
  return `${part("year")}-${part("month")}-${part("day")}`;
}
