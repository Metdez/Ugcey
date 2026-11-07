// Path+method allowlist for glasshand.internal (contract section 2). Checkout, billing, cancel, auth: all denied.
const ID = "[A-Za-z0-9-]+";
const RULES: [string, RegExp][] = [
  ["GET", /^\/v1\/rentals$/],
  ["GET", new RegExp(`^/v1/rentals/${ID}$`)],
  ["GET", new RegExp(`^/v1/rentals/${ID}/connection$`)],
  ["GET", new RegExp(`^/v1/rentals/${ID}/screenshot$`)],
  ["GET", /^\/v1\/me$/],
  ["POST", new RegExp(`^/v1/rentals/${ID}/input$`)],
];

export function glasshandAllowed(path: string, method = "GET"): boolean {
  return RULES.some(([m, re]) => m === method && re.test(path));
}
