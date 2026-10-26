import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT_DIR = path.resolve(__dirname, '../../');
const WEB_JS_DIR = path.resolve(ROOT_DIR, 'web/js');
const INDEX_HTML_PATH = path.resolve(ROOT_DIR, 'web/index.html');

function getAllJsFiles(dir) {
  let results = [];
  const list = fs.readdirSync(dir);
  list.forEach(file => {
    const fullPath = path.resolve(dir, file);
    const stat = fs.statSync(fullPath);
    if (stat && stat.isDirectory()) {
      results = results.concat(getAllJsFiles(fullPath));
    } else if (file.endsWith('.js')) {
      results.push(fullPath);
    }
  });
  return results;
}

test('(a) Syntax-parses every web/js file', () => {
  const jsFiles = getAllJsFiles(WEB_JS_DIR);
  assert.ok(jsFiles.length >= 6, 'Should find web/js files');

  jsFiles.forEach(file => {
    try {
      execFileSync('node', ['--check', file], { stdio: 'pipe' });
      assert.ok(true, `Syntax check passed for ${path.relative(ROOT_DIR, file)}`);
    } catch (err) {
      assert.fail(`Syntax error in ${path.relative(ROOT_DIR, file)}: ${err.stderr?.toString() || err.message}`);
    }
  });
});

test('(b) Verifies every relative import resolves and every named import is exported', () => {
  const jsFiles = getAllJsFiles(WEB_JS_DIR);

  // Helper to extract exports from a file
  function getExportsFromFile(filePath) {
    const content = fs.readFileSync(filePath, 'utf-8');
    const exports = new Set();

    // export function name(...)
    const fnMatches = content.matchAll(/export\s+(?:async\s+)?function\s+([a-zA-Z0-9_$]+)/g);
    for (const m of fnMatches) exports.add(m[1]);

    // export const/let/var name = ...
    const varMatches = content.matchAll(/export\s+(?:const|let|var)\s+([a-zA-Z0-9_$]+)/g);
    for (const m of varMatches) exports.add(m[1]);

    // export class Name ...
    const classMatches = content.matchAll(/export\s+class\s+([a-zA-Z0-9_$]+)/g);
    for (const m of classMatches) exports.add(m[1]);

    // export { a, b as c, ... }
    const namedBlockMatches = content.matchAll(/export\s*\{([^}]+)\}/g);
    for (const m of namedBlockMatches) {
      const items = m[1].split(',');
      for (const item of items) {
        const trimmed = item.trim();
        if (!trimmed) continue;
        const parts = trimmed.split(/\s+as\s+/);
        exports.add(parts[parts.length - 1].trim());
      }
    }

    // export default ...
    if (/export\s+default\s+/.test(content)) {
      exports.add('default');
    }

    return exports;
  }

  jsFiles.forEach(file => {
    const content = fs.readFileSync(file, 'utf-8');
    // Match import ... from '...'
    const importRegex = /import\s+(?:([\w*\s{},]+)\s+from\s+)?['"]([^'"]+)['"]/g;
    let match;

    while ((match = importRegex.exec(content)) !== null) {
      const clause = match[1] ? match[1].trim() : '';
      const importPath = match[2].trim();

      // Only check relative or root-relative imports within web/
      if (importPath.startsWith('.') || importPath.startsWith('/')) {
        let resolvedPath;
        if (importPath.startsWith('/')) {
          resolvedPath = path.resolve(ROOT_DIR, 'web', importPath.slice(1));
        } else {
          resolvedPath = path.resolve(path.dirname(file), importPath);
        }

        assert.ok(
          fs.existsSync(resolvedPath),
          `Import target does not exist: ${importPath} in ${path.relative(ROOT_DIR, file)}`
        );

        if (clause && clause.includes('{')) {
          const namedSection = clause.match(/\{([^}]+)\}/);
          if (namedSection) {
            const targetExports = getExportsFromFile(resolvedPath);
            const importedNames = namedSection[1]
              .split(',')
              .map(s => s.trim().split(/\s+as\s+/)[0].trim())
              .filter(Boolean);

            importedNames.forEach(importedName => {
              assert.ok(
                targetExports.has(importedName),
                `Named import '${importedName}' is not exported by ${path.relative(ROOT_DIR, resolvedPath)} (imported in ${path.relative(ROOT_DIR, file)})`
              );
            });
          }
        }
      }
    }
  });
});

test('(c) Verifies element ids referenced in JS exist in web/index.html or are created by the views', () => {
  const htmlContent = fs.readFileSync(INDEX_HTML_PATH, 'utf-8');
  const htmlIds = new Set();
  const htmlIdMatches = htmlContent.matchAll(/id=["']([a-zA-Z0-9_\-]+)["']/g);
  for (const m of htmlIdMatches) {
    htmlIds.add(m[1]);
  }

  // Known dynamic element IDs created programmatically in views
  const dynamicIds = new Set([
    'phases-container',
    'input-refine-ideas',
    'btn-submit-refine',
    // view tabs generated via `view-${currentTab}`
    'view-overview',
    'view-budget',
    'view-timeline',
    'view-vendors',
    'view-ideas'
  ]);

  const jsFiles = getAllJsFiles(WEB_JS_DIR);

  jsFiles.forEach(file => {
    const content = fs.readFileSync(file, 'utf-8');

    // 1. Check getElementById('...')
    const getByIdMatches = content.matchAll(/getElementById\(\s*['"]([a-zA-Z0-9_\-]+)['"]\s*\)/g);
    for (const m of getByIdMatches) {
      const id = m[1];
      assert.ok(
        htmlIds.has(id) || dynamicIds.has(id),
        `getElementById('${id}') in ${path.relative(ROOT_DIR, file)} does not exist in web/index.html or dynamic view IDs`
      );
    }

    // 2. Check querySelector('#...')
    const qsMatches = content.matchAll(/querySelector\(\s*['"]#([a-zA-Z0-9_\-]+)['"]\s*\)/g);
    for (const m of qsMatches) {
      const id = m[1];
      assert.ok(
        htmlIds.has(id) || dynamicIds.has(id),
        `querySelector('#${id}') in ${path.relative(ROOT_DIR, file)} does not exist in web/index.html or dynamic view IDs`
      );
    }
  });
});
