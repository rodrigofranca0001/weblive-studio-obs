/**
 * Gerador do Executável Portátil Único (WebLiveStudio.exe)
 * Lê todos os arquivos da pasta /public (HTML, CSS, JS), embute em C# (EmbeddedBundle.cs)
 * e invoca o compilador nativo do Windows (csc.exe) para gerar `WebLiveStudio.exe`
 * que funciona em qualquer máquina Windows com um único arquivo!
 */
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const ROOT = __dirname;
const PUBLIC_DIR = path.join(ROOT, 'public');
const LAUNCHER_DIR = path.join(ROOT, 'launcher');
const BUNDLE_CS = path.join(LAUNCHER_DIR, 'EmbeddedBundle.cs');
const OUTPUT_EXE = path.join(ROOT, 'WebLiveStudio.exe');

function getMime(ext) {
  const map = {
    '.html': 'text/html; charset=utf-8',
    '.css': 'text/css; charset=utf-8',
    '.js': 'application/javascript; charset=utf-8',
    '.json': 'application/json; charset=utf-8'
  };
  return map[ext] || 'application/octet-stream';
}

function walkFiles(dir, base = '') {
  let results = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const rel = `${base}/${entry.name}`;
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      results = results.concat(walkFiles(full, rel));
    } else {
      results.push({ rel, full, ext: path.extname(entry.name).toLowerCase() });
    }
  }
  return results;
}

const files = walkFiles(PUBLIC_DIR);

let cs = `using System;\nusing System.Collections.Generic;\nnamespace WebLiveStudio {\n  public static class EmbeddedBundle {\n    public static readonly Dictionary<string, EmbeddedAsset> Files = new Dictionary<string, EmbeddedAsset>(StringComparer.OrdinalIgnoreCase) {\n`;

for (const f of files) {
  const b64 = fs.readFileSync(f.full).toString('base64');
  const mime = getMime(f.ext);
  cs += `      { "${f.rel}", new EmbeddedAsset { MimeType = "${mime}", Content = Convert.FromBase64String("${b64}") } },\n`;
}

cs += `    };\n  }\n}\n`;
fs.writeFileSync(BUNDLE_CS, cs, 'utf8');

const cscPath = 'C:\\Windows\\Microsoft.NET\\Framework64\\v4.0.30319\\csc.exe';
const cmd = `"${cscPath}" /target:winexe /out:"${OUTPUT_EXE}" /optimize+ /r:System.dll /r:System.Drawing.dll /r:System.Windows.Forms.dll "${path.join(LAUNCHER_DIR, 'Launcher.cs')}" "${BUNDLE_CS}"`;

try {
  execSync('taskkill /F /IM WebLiveStudio.exe', { stdio: 'ignore' });
} catch (_) {}

console.log('🔨 Compilando executável portátil WebLiveStudio.exe...');
execSync(cmd, { stdio: 'inherit' });
console.log('✅ WebLiveStudio.exe gerado com sucesso em:', OUTPUT_EXE);

