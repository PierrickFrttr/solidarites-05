// Fonctions sans effet de bord, utilisées par les deux modes et testées par tests/test_utils.js.

function esc(t) {
  return String(t == null ? "" : t).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
function lib(dico, k) { return dico[k] || String(k).replace(/-/g, " "); }
function typeDe(s) { return s.sources[0]; }
function dateFr(d) { return d ? d.slice(0, 10).split("-").reverse().join("/") : ""; }

// Téléphone affichable et appelable, ou null s'il n'a pas assez de chiffres.
function telephone(t) {
  const n = String(t || "").replace(/[^\d+]/g, "").replace(/^\+33/, "0");
  return /^\d{10}$/.test(n) ? { lien: "tel:" + n, texte: n.replace(/(\d{2})(?=\d)/g, "$1 ") } : null;
}
// Adresse web sûre (http/https uniquement), ou null.
function urlSure(u) {
  if (!u) return null;
  try {
    const url = new URL(/^https?:\/\//i.test(u) ? u : "https://" + u.trim());
    return /^https?:$/.test(url.protocol) && url.hostname.includes(".") ? url.href : null;
  } catch (e) { return null; }
}
function courriel(m) { return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(m || "") ? m : null; }

// Distance en km (formule de haversine).
function dist(a, b) {
  const r = Math.PI / 180, x = Math.sin((b.lat - a.lat) * r / 2) ** 2 + Math.cos(a.lat * r) * Math.cos(b.lat * r) * Math.sin((b.lon - a.lon) * r / 2) ** 2;
  return 12742 * Math.asin(Math.sqrt(x));
}
function principal(s) {
  const n = {};
  s.services.forEach(sv => sv.besoins.forEach(b => n[b] = (n[b] || 0) + 1));
  return Object.keys(n).sort((a, b) => n[b] - n[a])[0] || "";
}
// Publics compatibles : l'une est ouverte à tous (ou ne précise rien), ou elles partagent un public.
function pubOk(a, b) {
  return !a.publics.length || !b.publics.length || a.publics.includes("tous-publics") || b.publics.includes("tous-publics")
    || a.publics.some(p => b.publics.includes(p));
}
// Besoins en commun justifiant un lien thématique (même bassin + publics compatibles), [] sinon.
function enCommun(a, b, besoin) {
  if (a === b || a.bassin !== b.bassin || !pubOk(a, b)) return [];
  const c = a.besoins.filter(x => b.besoins.includes(x));
  return besoin ? (c.includes(besoin) ? [besoin] : []) : c;
}
// ponytail: liens thématiques en O(n²) dans le navigateur, à précalculer à l'import au-delà de ~1000 structures
function thematiques(noeuds, besoin) {
  const L = [];
  for (let i = 0; i < noeuds.length; i++) for (let j = i + 1; j < noeuds.length; j++) {
    const c = enCommun(noeuds[i], noeuds[j], besoin);
    if (c.length) L.push({ source: noeuds[i], target: noeuds[j], kind: "theme", communs: c });
  }
  return L;
}

// Score de pertinence pour le mode public : déterministe, sert uniquement à ordonner les résultats.
// ctx = { besoin, public, position: {lat, lon} | null, bassin: bassin de la personne | null }
function score(s, ctx, P) {
  let pts = Math.min(s.services.filter(v => v.besoins.includes(ctx.besoin)).length, P.maxServices) * P.parService;
  if (ctx.public) pts += s.publics.includes(ctx.public) ? P.publicExact : (!s.publics.length || s.publics.includes("tous-publics")) ? P.publicTous : 0;
  if (ctx.position && s.lat != null) pts += P.proximiteMax * Math.max(0, 1 - dist(ctx.position, s) / P.proximiteKm);
  if (ctx.bassin && s.bassin === ctx.bassin) pts += P.memeBassin;
  if (telephone(s.tel)) pts += P.telephone;
  if (s.adresse) pts += P.adresse;
  if (s.horaires) pts += P.horaires;
  if (urlSure(s.web)) pts += P.site;
  return pts + (P.fraicheur[s.fraicheur] || 0);
}
// Structures adaptées à un besoin (et au public choisi), de la plus pertinente à la moins pertinente.
function classer(structures, ctx, P) {
  return structures
    .filter(s => s.besoins.includes(ctx.besoin) && (!ctx.public || !s.publics.length || s.publics.includes(ctx.public) || s.publics.includes("tous-publics")))
    .map(s => ({ s, pts: score(s, ctx, P) }))
    .sort((a, b) => b.pts - a.pts || a.s.nom.localeCompare(b.s.nom))
    .map(x => x.s);
}

if (typeof module !== "undefined") module.exports = { esc, telephone, urlSure, courriel, dist, principal, pubOk, enCommun, thematiques, score, classer, dateFr };
