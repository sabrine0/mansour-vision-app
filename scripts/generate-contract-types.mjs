#!/usr/bin/env node
/**
 * Generate TypeScript types from the event contract's JSON Schema.
 *
 * `packages/contracts` is the single source of truth (ADR 0007). The Python
 * services import the pydantic models directly; the dashboard consumes the types
 * this script emits. CI runs it with `--check`, so a contract change that is not
 * propagated to both sides fails the build — rather than failing at 2am on the
 * spine, when a consumer meets a field it has never seen.
 *
 * The input is `spine.schema.json`, the bundled document, not the five per-event
 * files. Compiling those independently emits every shared `$def` — `DensityLevel`,
 * `DetectionClass`, `CameraState` — once per file, and the concatenation does not
 * compile. The bundle carries them once.
 *
 *   node scripts/generate-contract-types.mjs           # write
 *   node scripts/generate-contract-types.mjs --check   # verify, exit 1 if stale
 */

import { readFile, writeFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { compile } from "json-schema-to-typescript";

const here = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(here, "..");
const schemaDir = join(repoRoot, "packages", "contracts", "schema");
const bundlePath = join(schemaDir, "spine.schema.json");
const indexPath = join(schemaDir, "index.json");
const outFile = join(repoRoot, "packages", "contracts", "typescript", "events.ts");

const HEADER = `/**
 * GENERATED FILE — DO NOT EDIT.
 *
 * Source: packages/contracts/schema/spine.schema.json
 * Regenerate: npm run contracts:generate
 *
 * The event contract for the MANSOUR Vision spine (ADR 0007).
 *
 * Note what is absent, and deliberately so: no track identifier, no person
 * identifier, no embedding, no biometric attribute. A crossing is decided from a
 * track's centroid history inside the worker; the track dies there and is never
 * published (ADR 0004).
 */

/* eslint-disable */
`;

async function build() {
  if (!existsSync(bundlePath)) {
    throw new Error(
      `bundled schema not found: ${bundlePath}\n` +
        "run: python -m mansour_contracts.export",
    );
  }

  const bundle = JSON.parse(await readFile(bundlePath, "utf8"));
  const index = JSON.parse(await readFile(indexPath, "utf8"));

  const types = await compile(bundle, "SpineEvent", {
    bannerComment: "",
    style: { singleQuote: false, semi: true },
    additionalProperties: false,
    unknownAny: true,
    enableConstEnums: false,
  });

  return [
    HEADER,
    types.trim(),
    "",
    "/** Bumped when a field is removed or its meaning changes. */",
    `export const SCHEMA_VERSION = ${index.schema_version};`,
    "",
    "/** Every event type carried on the spine. */",
    `export const SPINE_EVENT_TYPES = ${JSON.stringify(index.event_types)} as const;`,
    "",
    "export type SpineEventType = (typeof SPINE_EVENT_TYPES)[number];",
    "",
  ].join("\n");
}

const content = await build();

if (process.argv.includes("--check")) {
  const current = existsSync(outFile) ? await readFile(outFile, "utf8") : "";
  if (current !== content) {
    console.error(
      "TypeScript contract types are out of date.\nrun: npm run contracts:generate",
    );
    process.exit(1);
  }
  console.log("contract types are up to date");
} else {
  await writeFile(outFile, content, "utf8");
  console.log(`wrote ${outFile}`);
}
