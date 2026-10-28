/**
 * Seats against admissions (API_CONTRACT A2.18). Approved seats are one
 * year's intake, so the only figure that may be set against them is
 * `admitted`, the ACTIVE enrolments of that intake. `enrolments` is every
 * student on roll across all years of study and is never divided by seats.
 *
 * `admitted` counts every route into the intake, supernumerary ones too, so
 * it may exceed approved seats without any excess (contract errata 3): the
 * two are shown side by side as counts, never as a percentage, and the
 * EXCESS_ADMISSION and QUOTA_BREACH flags carry any excess.
 *
 * `admitted` arrives with the Week 2 api. Until a response carries it these
 * helpers return null and the pages show seats and students on roll under
 * their own labels.
 */

/** `admitted` when the response carries it, else null. */
export function admittedOf(row: { admitted?: unknown } | null | undefined): number | null {
  const value = row?.admitted;
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

/**
 * An institution's admitted count: the field when present, else the sum of
 * its programmes' intake enrolments (A2.18: they are equal by definition).
 */
export function institutionAdmitted(detail: { admitted?: unknown; programmes: { enrolments: number }[] }): number {
  return admittedOf(detail) ?? detail.programmes.reduce((a, p) => a + p.enrolments, 0);
}

/** Seats held in a programme: `seated` from Week 2, else enrolments minus unseated. */
export function seatedOf(p: { seated?: unknown; enrolments: number; unseated: number }): number {
  return typeof p.seated === "number" ? p.seated : Math.max(0, p.enrolments - p.unseated);
}
