// Éléments communs (erreurs, données, modes) + mode « J'ai besoin d'aide ». Ce mode ne dépend pas de D3.
const $ = id => document.getElementById(id);
const URGENCE = "En cas d'urgence : 115 (dormir ce soir), 3919 (violences), 119 (enfant en danger), 15 (urgence médicale).";

function afficherErreur(texte) {
  const e = $("erreur");
  e.textContent = texte;
  e.hidden = false;
}
window.addEventListener("error", () => afficherErreur("Une erreur est survenue. Rechargez la page. " + URGENCE));

const DONNEES_OK = !!(window.DATA && Array.isArray(DATA.structures) && DATA.structures.length);
const S = DONNEES_OK ? DATA.structures : [];
const PART_BRUTS = DONNEES_OK ? DATA.partenariats || [] : [];
S.forEach(s => s.principal = principal(s));
if (!DONNEES_OK) {
  afficherErreur("Les informations n'ont pas pu être chargées. Réessayez dans quelques minutes. " + URGENCE);
  $("grille").hidden = $("bt-pro").hidden = true;
} else if (DATA.genere_le) {
  $("date-donnees").textContent = ` (dernière : ${dateFr(DATA.genere_le)})`;
}

/* ---------- Modes ---------- */
function mode(pro) {
  $("bt-public").setAttribute("aria-pressed", !pro);
  $("bt-pro").setAttribute("aria-pressed", pro);
  $("public").hidden = pro;
  $("pro").hidden = !pro;
  if (pro) ouvrirPro();
  (pro ? $("titre-pro") : $("etape-liste").hidden ? $("titre-public") : $("titre-liste")).focus();
}
$("bt-public").onclick = () => mode(false);
$("bt-pro").onclick = () => mode(true);

/* ---------- Grand public ---------- */
let besoinChoisi = null, position = null;

$("grille").innerHTML = Object.entries(BESOINS).map(([k, [ic, t]]) =>
  `<button type="button" data-b="${k}"><span aria-hidden="true">${ic}</span>${t}</button>`).join("");
$("grille").onclick = e => {
  const b = e.target.closest("button");
  if (!b) return;
  besoinChoisi = b.dataset.b;
  afficherListe();
  $("titre-liste").focus();
};
$("retour").onclick = () => {
  $("etape-liste").hidden = true;
  $("etape-besoin").hidden = false;
  $("titre-public").focus();
};

// Communes connues : centre moyen des structures géolocalisées de la commune
const communes = new Map();
S.filter(s => s.lat != null).forEach(s => {
  const c = communes.get(s.commune) || { lat: 0, lon: 0, n: 0 };
  c.lat += s.lat; c.lon += s.lon; c.n++;
  communes.set(s.commune, c);
});
[...communes.keys()].sort((a, b) => a.localeCompare(b)).forEach(c => $("commune").add(new Option(c, c)));
$("commune").onchange = () => {
  const c = communes.get($("commune").value);
  position = c ? { lat: c.lat / c.n, lon: c.lon / c.n } : null;
  $("geo-statut").textContent = "";
  afficherListe();
};
$("pourqui").onchange = afficherListe;

// Géolocalisation : la position reste dans le navigateur, elle ne sert qu'à calculer des distances.
$("localiser").onclick = () => {
  const bt = $("localiser"), statut = $("geo-statut");
  if (!("geolocation" in navigator)) {
    statut.textContent = "Votre navigateur ne permet pas la localisation. Choisissez votre commune dans la liste.";
    return;
  }
  statut.textContent = "";
  bt.disabled = true;
  bt.textContent = "📍 Recherche de votre position…";
  const fin = () => { bt.disabled = false; bt.textContent = "📍 Me localiser"; };
  navigator.geolocation.getCurrentPosition(p => {
    fin();
    position = { lat: p.coords.latitude, lon: p.coords.longitude };
    $("commune").value = "";
    afficherListe();
  }, err => {
    fin();
    statut.textContent = ({
      1: "Vous n'avez pas autorisé la localisation. Choisissez votre commune dans la liste.",
      2: "Votre position n'est pas disponible pour le moment. Choisissez votre commune dans la liste.",
      3: "La localisation a pris trop de temps. Réessayez, ou choisissez votre commune dans la liste.",
    })[err.code] || "La localisation n'a pas fonctionné. Choisissez votre commune dans la liste.";
  }, { enableHighAccuracy: false, timeout: 10000, maximumAge: 600000 });
};

function bassinDe(pos) {
  let meilleur = null, d = Infinity;
  S.forEach(s => { if (s.lat != null && dist(pos, s) < d) { d = dist(pos, s); meilleur = s.bassin; } });
  return meilleur;
}

function afficherListe() {
  $("etape-besoin").hidden = true;
  $("etape-liste").hidden = false;
  const [ic, titre] = BESOINS[besoinChoisi];
  $("titre-liste").innerHTML = `<span aria-hidden="true">${ic}</span> ${esc(titre)}`;
  const ctx = { besoin: besoinChoisi, public: $("pourqui").value, position, bassin: position && bassinDe(position) };
  const r = classer(S, ctx, CONFIG.SCORE).slice(0, CONFIG.NB_RESULTATS);
  $("ordre").textContent = !r.length ? "" : `${r.length} lieu${r.length > 1 ? "x" : ""}, classé${r.length > 1 ? "s" : ""} selon `
    + (position ? "la distance, " : "") + "ce qu'ils proposent pour ce besoin et les informations disponibles."
    + (position ? "" : " Indiquez où vous êtes pour voir les plus proches.");
  $("liste").innerHTML = r.length ? r.map(carte).join("") : `<div class="resultat">
    <h3>Nous n'avons pas encore de lieu pour ce besoin${$("pourqui").value ? " et ce public" : ""}.</h3>
    <p>Appelez le <a href="tel:3939">3939</a> (Allô Service Public) : on vous dira où aller.
    ${besoinChoisi === "violences" ? 'Pour des violences, appelez le <a href="tel:3919">3919</a> (gratuit, anonyme, 24 h/24) ; en danger immédiat, le <a href="tel:17">17</a>.' : ""}</p></div>`;
  constellation(r, ic);
}

function carte(s, i) {
  const tel = telephone(s.tel), web = urlSure(s.web), mail = courriel(s.mail);
  const km = position && s.lat != null ? dist(position, s) : null;
  const services = [...new Set(s.services.filter(v => v.besoins.includes(besoinChoisi)).map(v => v.nom))];
  const itineraire = s.lat != null ? `https://www.openstreetmap.org/directions?route=%3B${s.lat}%2C${s.lon}`
    : s.adresse ? `https://www.openstreetmap.org/search?query=${encodeURIComponent([s.adresse, s.cp, s.commune].join(" "))}` : null;
  const modes = [...new Set(s.services.flatMap(v => v.modes))].map(m => m.replace(/-/g, " "));
  const frais = [...new Set(s.services.filter(v => v.besoins.includes(besoinChoisi)).map(v => v.frais).filter(Boolean))].map(f => lib(FRAIS, f));
  const plus = [
    s.adresse && `<div>📍 ${esc([s.adresse, s.cp, s.commune].filter(Boolean).join(" "))}</div>`,
    s.horaires && `<div>🕒 Horaires : ${esc(s.horaires)}</div>`,
    modes.length && `<div>Accueil : ${esc(modes.join(", "))}</div>`,
    frais.length && `<div>Coût : ${esc(frais.join(", "))}</div>`,
    mail && `<div>✉️ <a href="mailto:${esc(mail)}">${esc(mail)}</a></div>`,
  ].filter(Boolean).join("");
  const neuf = '<span class="sr-only"> (nouvel onglet)</span>';
  const fraicheur = s.fraicheur === "recent" ? "Fiche mise à jour récemment"
    : s.fraicheur === "inconnue" ? "Date de mise à jour non communiquée" : `Fiche à vérifier — informations du ${dateFr(s.maj)}`;
  return `<article class="resultat" id="r${i}" aria-labelledby="r${i}-t">
    <h3 id="r${i}-t">${i + 1}. ${esc(s.nom)}</h3>
    <p class="ou">${esc(lib(TYPES, typeDe(s)))} · ${esc(s.commune)}${km != null ? ` · à ${km < 1 ? "moins d'1" : Math.round(km)} km` : ""}</p>
    ${services.length ? `<p class="pourquoi">Propose : ${services.slice(0, 2).map(n => `« ${esc(n)} »`).join(", ")}</p>` : ""}
    <div class="actions">
      ${tel ? `<a href="${tel.lien}">📞 Appeler le ${tel.texte}</a>` : ""}
      ${itineraire ? `<a class="sec" href="${esc(itineraire)}" target="_blank" rel="noopener">🗺️ Itinéraire${neuf}</a>` : ""}
      ${web ? `<a class="sec" href="${esc(web)}" target="_blank" rel="noopener">🌐 Voir le site${neuf}</a>` : ""}
      ${!tel && mail ? `<a class="sec" href="mailto:${esc(mail)}">✉️ Écrire</a>` : ""}
    </div>
    ${!tel && !itineraire && !web && !mail ? '<p class="info">Aucun moyen de contact connu pour ce lieu pour le moment.</p>' : ""}
    ${plus ? `<details><summary>Adresse, horaires, accueil</summary>${plus}</details>` : ""}
    <p class="fraicheur">${fraicheur}</p>
  </article>`;
}

// Constellation : le besoin au centre, les lieux autour (repère visuel, la liste reste la référence).
function constellation(r, ic) {
  const c = 160, R = 115;
  $("constellation").innerHTML = r.map((s, i) => {
    const a = i / r.length * 2 * Math.PI - Math.PI / 2, x = c + R * Math.cos(a), y = c + R * Math.sin(a);
    return `<line x1="${c}" y1="${c}" x2="${x}" y2="${y}" stroke="#c9c2b4" stroke-width="2"/>
      <a href="#r${i}" tabindex="-1"><circle cx="${x}" cy="${y}" r="18" fill="${s.fraicheur === "ancien" ? "#8a9197" : "#0b5c7a"}"/>
      <text x="${x}" y="${y + 5}" text-anchor="middle" fill="#fff" font-weight="700">${i + 1}</text></a>`;
  }).join("") + `<circle cx="${c}" cy="${c}" r="38" fill="#f7f5f0" stroke="#0b5c7a" stroke-width="3"/>
    <text x="${c}" y="${c + 13}" text-anchor="middle" font-size="36">${ic}</text>`;
}
