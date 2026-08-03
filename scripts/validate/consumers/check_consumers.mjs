#!/usr/bin/env node
/**
 * Consumer-contract check for announcements.
 *
 * An announcement is parsed three separate times before it reaches a reader,
 * by three parsers written independently of each other:
 *
 *   1. Quarto's YAML reader           -> the announcements listing page
 *   2. js/news-loader.js parseYAML()  -> the homepage news feed
 *   3. sendAnnouncement.js            -> the email sent to every subscriber
 *
 * (2) and (3) are hand-rolled and, historically, wrong in ways nothing on the
 * site revealed. This script runs the REAL shipped code -- not a
 * re-implementation, which could drift and would prove nothing -- against
 * every real post, and asserts that all three agree.
 *
 * Exit codes: 0 all contracts hold, 1 a contract is broken, 2 harness error.
 */

import { createRequire } from 'node:module';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(HERE, '..', '..', '..');
const POSTS = join(ROOT, 'docs', 'announcements', 'posts');
const METADATA = join(POSTS, '_metadata.yml');

// The pure parser, not the handler: requiring the handler would pull in the
// AWS SDK. This is the same module the deployed Lambda calls.
const { extractTitleAndContent } = require(
  join(ROOT, 'docs/announcements/backend/lambda/parseAnnouncement.js')
);
const { parseYAML, formatDate, parseDate } = require(
  join(ROOT, 'js/news-loader.js')
);

const findings = [];
const fail = (path, rule, message, hint) =>
  findings.push({ path, rule, message, hint });

/** Minimal YAML front-matter reader, used only as the ground truth to compare
 *  the two hand-rolled parsers against. */
function groundTruth(text) {
  const lines = text.replace(/^﻿/, '').split('\n');
  if (lines[0].trim() !== '---') return null;
  const end = lines.findIndex((l, i) => i > 0 && /^(---|\.\.\.)\s*$/.test(l.trim()));
  if (end === -1) return null;

  const out = {};
  let key = null;
  let block = null;

  for (const line of lines.slice(1, end)) {
    if (block !== null) {
      if (line.trim() === '' || /^\s+/.test(line)) {
        block.push(line.trim());
        continue;
      }
      out[key] = block.join(' ').trim();
      block = null;
    }
    const m = /^([A-Za-z_][\w.-]*)\s*:(.*)$/.exec(line);
    if (!m) continue;
    key = m[1];
    const raw = stripComment(m[2]).trim();
    if (raw === '|' || raw === '>' || raw === '|-' || raw === '>-') {
      block = [];
    } else {
      out[key] = unquote(raw);
    }
  }
  if (block !== null) out[key] = block.join(' ').trim();
  return out;
}

function unquote(v) {
  if (v.length >= 2 && (v[0] === '"' || v[0] === "'") && v[v.length - 1] === v[0]) {
    return v.slice(1, -1);
  }
  return v;
}

/** Drop a trailing "# ..." comment, respecting quotes. The ground truth must
 *  understand comments even though the Lambda does not -- that asymmetry is
 *  precisely what makes the comment-leak detectable. */
function stripComment(line) {
  let quote = null;
  for (let i = 0; i < line.length; i++) {
    const c = line[i];
    if (quote) {
      if (c === quote) quote = null;
    } else if (c === '"' || c === "'") {
      quote = c;
    } else if (c === '#' && (i === 0 || /\s/.test(line[i - 1]))) {
      return line.slice(0, i);
    }
  }
  return line;
}

const norm = (s) => String(s ?? '').replace(/\s+/g, ' ').trim().replace(/^"|"$/g, '').trim();

// ---------------------------------------------------------------------------
// Contract 1..4 -- the email Lambda, run against every post
// ---------------------------------------------------------------------------

const postDirs = readdirSync(POSTS)
  .filter((d) => !d.startsWith('_') && statSync(join(POSTS, d)).isDirectory())
  .sort();

if (postDirs.length === 0) {
  console.error('harness error: no announcement posts found');
  process.exit(2);
}

for (const dir of postDirs) {
  const files = readdirSync(join(POSTS, dir)).filter((f) => f.endsWith('.qmd')).sort();
  if (files.length === 0) continue;

  const rel = `docs/announcements/posts/${dir}/${files[0]}`;
  const text = readFileSync(join(POSTS, dir, files[0]), 'utf8');
  const truth = groundTruth(text);

  if (!truth) {
    fail(rel, 'consumer.frontmatter-unreadable',
      'Front matter could not be read.',
      'The file must start with --- and close the block with another ---.');
    continue;
  }

  let extracted;
  try {
    extracted = extractTitleAndContent(text);
  } catch (err) {
    fail(rel, 'consumer.lambda-throws',
      `The announcement email Lambda throws on this post: ${err.message}`,
      'The Lambda only logs the error, so no email is sent and nothing on ' +
      'the site indicates a failure.');
    continue;
  }

  if (norm(extracted.title) !== norm(truth.title)) {
    fail(rel, 'consumer.lambda-title-mismatch',
      `Subscribers would receive the title ${JSON.stringify(norm(extracted.title))} ` +
      `instead of ${JSON.stringify(norm(truth.title))}.`,
      'Usually a trailing "# ..." comment on the title line; the Lambda ' +
      'parses with a regular expression that does not understand comments.');
  }

  if (norm(extracted.description) !== norm(truth.description)) {
    fail(rel, 'consumer.lambda-description-mismatch',
      'Subscribers would receive a different description than the front matter declares.',
      `Lambda sees ${JSON.stringify(norm(extracted.description).slice(0, 80))}, ` +
      `front matter says ${JSON.stringify(norm(truth.description).slice(0, 80))}`);
  }
}

// ---------------------------------------------------------------------------
// Contract 5..8 -- the homepage feed parser
// ---------------------------------------------------------------------------

const relMeta = 'docs/announcements/posts/_metadata.yml';
const feed = parseYAML(readFileSync(METADATA, 'utf8'));

if (feed.length === 0) {
  fail(relMeta, 'consumer.feed-empty',
    'The homepage feed parser reads zero announcements from _metadata.yml.',
    'The homepage news section would be blank. Regenerate with: ' +
    'python scripts/generate-announcements-metadata.py');
}

for (const item of feed) {
  for (const field of ['title', 'description', 'date', 'image', 'url', 'author']) {
    if (!item[field]) {
      fail(relMeta, 'consumer.feed-field-empty',
        `Feed entry ${JSON.stringify(item.title ?? '?')} has no ${field}.`,
        'Regenerate the feed after fixing the underlying post.');
    }
  }

  const when = parseDate(item.date);
  if (Number.isNaN(when.getTime())) {
    fail(relMeta, 'consumer.feed-date-invalid',
      `Feed entry ${JSON.stringify(item.title)} has an unparseable date ` +
      `${JSON.stringify(item.date)}.`,
      'Dates must be MM/DD/YYYY.');
  } else {
    // Guards the reversal bug that turned MM/DD/YYYY into YYYY-DD-MM, so
    // February 12 sorted as December 2.
    const [mm, dd, yyyy] = item.date.split('/').map(Number);
    if (when.getMonth() + 1 !== mm || when.getDate() !== dd || when.getFullYear() !== yyyy) {
      fail(relMeta, 'consumer.feed-date-misparsed',
        `Date ${item.date} is parsed as ${when.toDateString()}, which is not ` +
        `the date written.`,
        'Month and day are being swapped somewhere in the feed loader.');
    }
  }

  if (formatDate(item.date) === 'Invalid Date') {
    fail(relMeta, 'consumer.feed-date-unformattable',
      `formatDate() returns "Invalid Date" for ${JSON.stringify(item.date)}.`,
      'The homepage would display "Invalid Date" to every visitor.');
  }
}

// The feed must already be newest-first: the loader renders item 0 as the
// featured card.
const dates = feed.map((i) => parseDate(i.date).getTime());
const sorted = [...dates].sort((a, b) => b - a);
if (JSON.stringify(dates) !== JSON.stringify(sorted)) {
  fail(relMeta, 'consumer.feed-out-of-order',
    'The homepage feed is not in newest-first order.',
    'The featured card would show the wrong announcement. Regenerate with: ' +
    'python scripts/generate-announcements-metadata.py');
}

// ---------------------------------------------------------------------------

if (findings.length === 0) {
  console.log(
    `All announcement consumer contracts hold ` +
    `(${postDirs.length} posts, ${feed.length} feed entries).`
  );
  process.exit(0);
}

for (const f of findings) {
  const message = `${f.message}${f.hint ? ' — ' + f.hint : ''}`
    .replace(/%/g, '%25').replace(/\r/g, '%0D').replace(/\n/g, '%0A')
    .replace(/:/g, '%3A').replace(/,/g, '%2C');
  console.log(`::error file=${f.path},title=${f.rule}::${message}`);
}
console.error(`\n${findings.length} consumer-contract failure(s).`);
process.exit(1);
