import "dotenv/config";
import { verifyCalendarAccess } from "./calendar.js";

console.log("Testing Google Calendar access via service account...\n");

try {
  const result = await verifyCalendarAccess();
  console.log("Success! Calendar is reachable.\n");
  console.log(`Calendar ID: ${result.calendarId}`);
  console.log(`Events found (sample window): ${result.eventCount}`);

  if (result.sample.length > 0) {
    console.log("\nSample events:");
    for (const event of result.sample) {
      console.log(`  - ${event.title} (${event.date} ${event.time})`);
    }
  } else {
    console.log("\nNo events in the current window (that is OK).");
  }
} catch (error) {
  console.error("Calendar test failed:\n");
  console.error(error.message);
  console.error("\nChecklist:");
  console.error("  1. Google Calendar API enabled in GCP");
  console.error("  2. service-account.json path is correct in server/.env");
  console.error("  3. Calendar shared with the service account email");
  console.error("  4. GOOGLE_CALENDAR_ID matches the shared calendar");
  process.exit(1);
}
