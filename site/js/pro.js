// Mode professionnel : nuage (D3), vue liste, fiche, réseau d'une structure, mode chemin.
const parId = new Map(S.map(s => [s.id, s]));
const PART = PART_BRUTS.map(p => ({ source: parId.get(p.de), target: parId.get(p.vers), kind: "part", besoin: p.besoin }))
  .filter(l => l.source && l.target);
const partenariatsDe = s => PART.filter(l => l.source === s || l.target === s);
const libBesoin = b => (BESOINS[b] || [, b])[1];
const D3_OK = typeof d3 !== "undefined";
const DUREE = matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : 600;

/* ---------- Contributions (préparation V2) ----------
   Point d'entrée unique : aujourd'hui un courriel prérempli à l'animateur du réseau,
   plus tard un formulaire avec modération, sans changer le reste de l'interface. */
const CONTRIBUTIONS = {
  modification: ["Proposer une modification", "Information à corriger : \nNouvelle information : "],
  obsolete: ["Signaler une information obsolète", "Information obsolète : "],
  partenariat: ["Proposer un partenariat", "Oriente vers (structure partenaire) : \nPour quel besoin : \nContact du référent : "],
};
function lienContribution(type, s) {
  if (!courriel(CONFIG.CONTACT_ANIMATEUR)) return null;
  const [titre, corps] = CONTRIBUTIONS[type];
  return `mailto:${CONFIG.CONTACT_ANIMATEUR}?subject=${encodeURIComponent(`${titre} — ${s.nom}`)}&body=${encodeURIComponent(`Structure : ${s.nom} (${s.id})\n${corps}`)}`;
}

/* ---------- État ---------- */
let pret = false, selection = null, reseauDe = null, inclureBassin = false, modeChemin = false, chemin = [];
let visibles = [], liens = [], origineFocus = null;
const AIDE_PANNEAU = $("panneau").innerHTML;
const filtre = id => $(id).value;
const vueListe = () => $("bt-vue").getAttribute("aria-pressed") === "true";

function ouvrirPro() {
  if (!pret) { init(); pret = true; }
  dessiner();
}

function init() {
  const remplir = (id, tout, vals, libelle) => { $(id).add(new Option(tout, "")); vals.forEach(v => $(id).add(new Option(libelle(v), v))); };
  remplir("f-besoin", "Tous", Object.keys(BESOINS), libBesoin);
  remplir("f-public", "Tous", [...new Set(S.flatMap(s => s.publics))].sort(), p => lib(PUBLICS, p));
  remplir("f-bassin", "Tout le 05", [...new Set(S.map(s => s.bassin))].sort(), b => b);
  remplir("f-type", "Tous", [...new Set(S.map(typeDe))], t => lib(TYPES, t));
  ["f-besoin", "f-public", "f-bassin", "f-type", "f-lien", "f-couleur", "f-taille"].forEach(id => $(id).onchange = dessiner);
  $("recherche").oninput = dessiner;
  $("bt-vue").onclick = () => vue(!vueListe());
  $("bt-chemin").onclick = basculerChemin;
  $("bt-reset").onclick = reinitialiser;
  $("panneau").onclick = $("vue-liste").onclick = $("bandeau-reseau").onclick = actions;
  $("bandeau-reseau").onchange = e => { if (e.target.id === "reseau-bassin") { inclureBassin = e.target.checked; dessiner(); } };
  if (D3_OK) initGraphe();
  else {
    $("bt-vue").hidden = $("bt-chemin").hidden = true;
    $("f-couleur").parentNode.hidden = $("f-taille").parentNode.hidden = true;
  }
  if (!D3_OK || matchMedia("(max-width: 700px)").matches) vue(true); // sur téléphone, la liste d'abord
}

// Délégation des clics : ouvrir une fiche, voir un réseau, fermer, quitter le réseau
function actions(e) {
  const b = e.target.closest("button");
  if (!b) return;
  if (b.dataset.id) ouvrir(parId.get(b.dataset.id));
  else if (b.dataset.reseau) voirReseau(parId.get(b.dataset.reseau));
  else if (b.id === "fermer-fiche") fermer();
  else if (b.id === "quitter-reseau") quitterReseau();
}

/* ---------- Sélection des structures et des liens ---------- */
function correspondFiltres(s) {
  return (!filtre("f-besoin") || s.besoins.includes(filtre("f-besoin"))) && (!filtre("f-public") || s.publics.includes(filtre("f-public")))
    && (!filtre("f-bassin") || s.bassin === filtre("f-bassin")) && (!filtre("f-type") || typeDe(s) === filtre("f-type"));
}
function reseau(s) {
  const partenaires = [...new Set(partenariatsDe(s).map(l => l.source === s ? l.target : l.source))];
  const proches = S.filter(x => !partenaires.includes(x) && enCommun(s, x).length);
  const bassin = S.filter(x => x !== s && x.bassin === s.bassin && !partenaires.includes(x) && !proches.includes(x));
  return { partenaires, proches, bassin };
}
function calculer() {
  const b = filtre("f-besoin"), fl = filtre("f-lien");
  if (reseauDe) {
    const r = reseau(reseauDe);
    visibles = [reseauDe, ...[...r.partenaires, ...r.proches, ...(inclureBassin ? r.bassin : [])].filter(correspondFiltres)];
  } else visibles = S.filter(correspondFiltres);
  const ids = new Set(visibles);
  const theme = reseauDe // en mode réseau : uniquement les liens de la structure choisie (étoile lisible)
    ? visibles.filter(x => enCommun(reseauDe, x, b).length).map(x => ({ source: reseauDe, target: x, kind: "theme", communs: enCommun(reseauDe, x, b) }))
    : b ? thematiques(visibles, b) : [];
  liens = [...(fl !== "theme" ? PART.filter(l => ids.has(l.source) && ids.has(l.target)) : []), ...(fl !== "part" ? theme : [])];
}
const recherche = () => $("recherche").value.trim().toLowerCase();
const correspond = (s, q) => !!q && (s.nom + " " + s.commune + " " + s.description + " " + s.services.map(v => v.nom + " " + v.description).join(" ")).toLowerCase().includes(q);

function dessiner() {
  calculer();
  const q = recherche(), nbPart = liens.filter(l => l.kind === "part").length, nbTheme = liens.length - nbPart;
  $("compte").textContent = `${visibles.length} structure${visibles.length > 1 ? "s" : ""}, ${nbPart} partenariat${nbPart > 1 ? "s" : ""} validé${nbPart > 1 ? "s" : ""}, ${nbTheme} lien${nbTheme > 1 ? "s" : ""} de proximité thématique`
    + (q ? ` — ${visibles.filter(s => correspond(s, q)).length} correspondent à « ${q} »` : "")
    + (!D3_OK ? ". Le graphique n'a pas pu être chargé : la vue liste donne accès à toutes les informations." : "")
    + (!reseauDe && !filtre("f-besoin") && D3_OK ? ". Choisissez un besoin pour voir la proximité thématique." : "");
  if (D3_OK && !vueListe()) graphe(q);
  tableau(q);
  legende();
}

/* ---------- Graphe ---------- */
let svg, zoom, gBassins, gLiens, gChemin, gNoeuds, sim, couleurType, couleurBesoin;
const couleur = s => s.fraicheur === "ancien" ? "#a7adb2" : filtre("f-couleur") === "type" ? couleurType(typeDe(s)) : s.principal ? couleurBesoin(s.principal) : "#555";
const rayon = s => 5 + 2.2 * Math.sqrt(filtre("f-taille") === "services" ? s.services.length : partenariatsDe(s).length);

function initGraphe() {
  svg = d3.select("#graphe");
  const racine = svg.append("g");
  svg.append("defs").append("marker").attr("id", "fleche").attr("viewBox", "0 -5 10 10").attr("refX", 10)
    .attr("markerWidth", 6).attr("markerHeight", 6).attr("orient", "auto").append("path").attr("d", "M0,-5L10,0L0,5").attr("fill", "#c2410c");
  zoom = d3.zoom().scaleExtent([.3, 6]).on("zoom", e => racine.attr("transform", e.transform));
  svg.call(zoom);
  gBassins = racine.append("g").attr("aria-hidden", "true");
  gLiens = racine.append("g");
  gChemin = racine.append("g");
  gNoeuds = racine.append("g");
  couleurType = d3.scaleOrdinal(Object.keys(TYPES), d3.schemeTableau10);
  couleurBesoin = d3.scaleOrdinal(Object.keys(BESOINS), d3.schemePaired);
  sim = d3.forceSimulation().force("charge", d3.forceManyBody().strength(-25)).on("tick", () => {
    gNoeuds.selectAll(".noeud").attr("transform", s => `translate(${s.x},${s.y})`);
    gLiens.selectAll("line").each(function (l) { bout(d3.select(this), l); });
    gChemin.selectAll("line").each(function (l) { bout(d3.select(this), l); });
  });
}
function bout(sel, l) { // raccourcit le trait pour que la flèche touche le bord du point
  const dx = l.target.x - l.source.x, dy = l.target.y - l.source.y, d = Math.hypot(dx, dy) || 1, r = l.kind === "part" ? rayon(l.target) + 2 : 0;
  sel.attr("x1", l.source.x).attr("y1", l.source.y).attr("x2", l.target.x - dx / d * r).attr("y2", l.target.y - dy / d * r);
}

function graphe(q) {
  const W = $("graphe").clientWidth || 800, H = $("graphe").clientHeight || 600;
  // Ancre géographique : chaque bassin attire ses structures, à sa place approximative sur la carte du 05
  const proj = (lat, lon) => [40 + (lon - 5.55) / 1.6 * (W - 80), 40 + (45.1 - lat) / .95 * (H - 80)];
  const ancres = new Map(d3.rollups(S.filter(s => s.lat != null), v => proj(d3.mean(v, s => s.lat), d3.mean(v, s => s.lon)), s => s.bassin));
  ancres.set("Non localisé", [W - 60, H - 40]);
  gBassins.selectAll("text").data([...ancres], d => d[0]).join("text").attr("x", d => d[1][0]).attr("y", d => d[1][1] - 60)
    .attr("text-anchor", "middle").attr("fill", "#9c9483").attr("font-size", 15).attr("font-weight", 700).text(d => d[0]);

  gLiens.selectAll("line").data(liens).join(enter => enter.append("line").call(l => l.append("title")))
    .attr("stroke", l => l.kind === "part" ? "#c2410c" : "#8a959d").attr("stroke-opacity", l => l.kind === "part" ? .9 : .35)
    .attr("stroke-width", l => l.kind === "part" ? 3 : 1).attr("marker-end", l => l.kind === "part" ? "url(#fleche)" : null)
    .select("title").text(l => l.kind === "part"
      ? `Partenariat validé : ${l.source.nom} oriente vers ${l.target.nom}${l.besoin ? ` (${libBesoin(l.besoin)})` : ""}`
      : `Proximité thématique : ${l.communs.map(libBesoin).join(", ")}, même bassin`);

  gNoeuds.selectAll(".noeud").data(visibles, s => s.id).join(entree => {
    const g = entree.append("g").attr("class", "noeud").attr("tabindex", 0).attr("role", "button");
    g.append("circle").attr("stroke", "#fff").attr("stroke-width", 1.5);
    g.on("mouseenter focus", (e, s) => survol(s, e)).on("mousemove", e => bulle(e)).on("mouseleave blur", () => survol(null))
      .on("click", (e, s) => clic(s))
      .on("keydown", (e, s) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); clic(s); } })
      .call(d3.drag().on("start", (e, s) => { if (!e.active) sim.alphaTarget(.2).restart(); s.fx = s.x; s.fy = s.y; })
        .on("drag", (e, s) => { s.fx = e.x; s.fy = e.y; }).on("end", (e, s) => { if (!e.active) sim.alphaTarget(0); s.fx = s.fy = null; }));
    return g;
  }).attr("aria-label", s => `${s.nom}, ${s.commune}${s.fraicheur === "ancien" ? ", fiche ancienne" : ""} — ouvrir la fiche`)
    .classed("halo", s => correspond(s, q)).classed("choisi", s => s === selection)
    .select("circle").attr("r", rayon).attr("fill", couleur);

  visibles.forEach(s => { if (s.x == null) { const a = ancres.get(s.bassin) || [W / 2, H / 2]; s.x = a[0] + Math.random() * 40 - 20; s.y = a[1] + Math.random() * 40 - 20; } });
  const ancre = s => ancres.get(s.bassin) || [W / 2, H / 2];
  sim.nodes(visibles)
    .force("x", d3.forceX(s => ancre(s)[0]).strength(reseauDe ? .03 : .12)).force("y", d3.forceY(s => ancre(s)[1]).strength(reseauDe ? .03 : .12))
    .force("lien", d3.forceLink(liens).strength(l => l.kind === "part" ? .3 : reseauDe ? .1 : .01))
    .force("collide", d3.forceCollide(s => rayon(s) + 2)).alpha(.8).restart();
  dessinerChemin();
}

function voisins(s) {
  const v = new Set([s]);
  liens.forEach(l => { if (l.source === s) v.add(l.target); if (l.target === s) v.add(l.source); });
  return v;
}
function bulle(e) {
  if (!e || e.clientX == null) return;
  $("bulle").style.left = e.clientX + 12 + "px";
  $("bulle").style.top = e.clientY + 12 + "px";
}
function survol(s, e) {
  $("bulle").hidden = !s || !e || e.type === "focus";
  if (s) { $("bulle").textContent = `${s.nom} — ${s.commune}`; bulle(e); }
  if (modeChemin) return;
  const v = s && voisins(s);
  gNoeuds.selectAll(".noeud").classed("estompe", n => !!v && !v.has(n));
  gLiens.selectAll("line").classed("estompe", l => !!s && l.source !== s && l.target !== s);
}
function centrer(s) {
  if (!D3_OK || vueListe() || s.x == null) return;
  const W = $("graphe").clientWidth, H = $("graphe").clientHeight;
  svg.transition().duration(DUREE).call(zoom.transform, d3.zoomIdentity.translate(W / 2, H / 2).scale(1.6).translate(-s.x, -s.y));
}
function clic(s) {
  if (!modeChemin) return ouvrir(s);
  chemin = chemin.length >= 2 ? [s] : [...chemin, s];
  dessinerChemin();
}

function legende() {
  const parType = filtre("f-couleur") === "type";
  const entrees = parType ? Object.keys(TYPES).filter(t => S.some(s => typeDe(s) === t)).map(t => [couleurType ? couleurType(t) : "#555", TYPES[t]])
    : Object.keys(BESOINS).map(k => [couleurBesoin ? couleurBesoin(k) : "#555", libBesoin(k)]);
  $("legende").innerHTML = (D3_OK && !vueListe() ? entrees.map(([c, t]) => `<span><i style="background:${c}"></i>${esc(t)}</span>`).join("") : "")
    + '<span><i style="background:#a7adb2"></i>Fiche ancienne (plus de 12 mois)</span>'
    + '<span><i class="trait"></i>Proximité thématique (calculée)</span><span><i class="trait part"></i>Partenariat validé (oriente vers)</span>'
    + (D3_OK && !vueListe() ? `<span>Taille : ${filtre("f-taille") === "services" ? "nombre de services" : "nombre de partenariats"}</span>` : "");
}

/* ---------- Fiche ---------- */
function ouvrir(s) {
  if (!s) return;
  origineFocus = document.activeElement;
  selection = s;
  fiche(s);
  $("fiche-titre").focus();
  if (D3_OK) gNoeuds.selectAll(".noeud").classed("choisi", n => n === s);
  centrer(s);
}
function fermer() {
  selection = null;
  $("panneau").innerHTML = AIDE_PANNEAU;
  if (D3_OK) gNoeuds.selectAll(".noeud").classed("choisi", false);
  if (origineFocus && document.contains(origineFocus)) origineFocus.focus();
}

function fiche(s) {
  const btn = x => `<button class="lienfiche" data-id="${esc(x.id)}">${esc(x.nom)}</button>`;
  const r = reseau(s), tel = telephone(s.tel), web = urlSure(s.web), mail = courriel(s.mail);
  const maj = s.maj ? `Mise à jour le ${dateFr(s.maj)}` : "Date de mise à jour non communiquée par la source";
  const contributions = Object.keys(CONTRIBUTIONS).map(t => [t, lienContribution(t, s)]).filter(([, u]) => u);
  $("panneau").innerHTML = `
    <div class="entete-fiche"><h2 id="fiche-titre" tabindex="-1">${esc(s.nom)}</h2>
      <button class="bouton" id="fermer-fiche" aria-label="Fermer la fiche">✕</button></div>
    <div><span class="badge">${esc(lib(TYPES, typeDe(s)))}</span><span class="badge">${esc(s.bassin)}</span>
      <span class="badge f-${s.fraicheur}">${esc(FRAICHEUR[s.fraicheur] || FRAICHEUR.inconnue)}</span></div>
    <p class="info">${maj}</p>
    <div class="actions"><button class="sec" data-reseau="${esc(s.id)}">Voir le réseau de cette structure</button></div>
    ${s.description ? `<p>${esc(s.description)}</p>` : ""}
    <h3>Ce qu'elle fait (${s.services.length} service${s.services.length > 1 ? "s" : ""})</h3>
    ${s.services.map(v => `<div class="service"><strong>${esc(v.nom)}</strong>
      ${v.description ? `<div class="info">${esc(v.description)}${v.description.length >= 400 ? "…" : ""}</div>` : ""}
      ${v.besoins.length ? `<div>Besoins : ${v.besoins.map(libBesoin).join(", ")}</div>` : ""}
      ${v.publics.length ? `<div>Pour qui : ${v.publics.map(p => esc(lib(PUBLICS, p))).join(", ")}</div>` : ""}
      ${v.conditions ? `<div>Conditions : ${esc(v.conditions)}</div>` : ""}
      ${v.frais ? `<div>Coût : ${esc(lib(FRAIS, v.frais))}${v.frais_precisions ? " — " + esc(v.frais_precisions) : ""}</div>` : ""}
      ${v.modes.length ? `<div>Modalités : ${v.modes.map(m => esc(m.replace(/-/g, " "))).join(", ")}</div>` : ""}</div>`).join("") || '<p class="info">Aucun service détaillé.</p>'}
    <h3>Contact</h3>
    ${tel ? `<div>📞 <a href="${tel.lien}">${tel.texte}</a></div>` : ""}
    ${mail ? `<div>✉️ <a href="mailto:${esc(mail)}">${esc(mail)}</a></div>` : ""}
    ${web ? `<div>🌐 <a href="${esc(web)}" target="_blank" rel="noopener">${esc(s.web)}</a></div>` : ""}
    ${s.adresse || s.commune ? `<div>📍 ${esc([s.adresse, s.cp, s.commune].filter(Boolean).join(" "))}</div>` : ""}
    ${s.horaires ? `<div>🕒 ${esc(s.horaires)}</div>` : ""}
    ${urlSure(s.accessibilite) ? `<div>♿ <a href="${esc(urlSure(s.accessibilite))}" target="_blank" rel="noopener">Accessibilité du lieu</a></div>` : ""}
    ${!tel && !mail && !web && !s.adresse ? '<p class="info">Aucun contact direct connu.</p>' : ""}
    <h3>Partenariats déclarés et validés</h3>
    ${partenariatsDe(s).map(l => `<div>${l.source === s ? "→ oriente vers " : "← reçoit des personnes de "}${btn(l.source === s ? l.target : l.source)}${l.besoin ? ` (${esc(libBesoin(l.besoin))})` : ""}</div>`).join("")
      || '<p class="info">Aucun partenariat déclaré pour l\'instant.</p>'}
    <h3>Proximité thématique (${r.proches.length})</h3>
    <p class="info">Même bassin, au moins un besoin en commun, publics compatibles. C'est une complémentarité possible, pas un partenariat.</p>
    ${r.proches.slice(0, 12).map(x => `<div>${btn(x)} <span class="info">— en commun : ${enCommun(s, x).map(libBesoin).join(", ")}</span></div>`).join("") || '<p class="info">Aucune.</p>'}
    ${r.proches.length > 12 ? `<p class="info">… et ${r.proches.length - 12} autres : voir le réseau.</p>` : ""}
    <h3>Autres structures du bassin ${esc(s.bassin)} (${r.bassin.length})</h3>
    ${r.bassin.length ? `<details><summary>Afficher la liste</summary>${r.bassin.map(x => `<div>${btn(x)}</div>`).join("")}</details>` : '<p class="info">Aucune.</p>'}
    <h3>Mettre à jour</h3>
    ${s.liens_source.map((u, i) => urlSure(u) ? `<div><a href="${esc(urlSure(u))}" target="_blank" rel="noopener">Corriger la fiche sur ${esc(s.sources[i])}</a> (la structure modifie ses informations à la source)</div>` : "").join("")}
    ${contributions.length ? `<div class="actions">${contributions.map(([t, u]) => `<a class="sec" href="${esc(u)}">${CONTRIBUTIONS[t][0]}</a>`).join("")}</div>`
      : '<p class="info">Proposer une modification ou un partenariat : contact de l\'animateur du réseau à configurer.</p>'}`;
}

/* ---------- Réseau d'une structure ---------- */
function voirReseau(s) {
  reseauDe = s;
  inclureBassin = false;
  const r = reseau(s);
  $("bandeau-reseau").innerHTML = `<span>Réseau de <strong>${esc(s.nom)}</strong> : ${r.partenaires.length} partenariat(s) validé(s),
    ${r.proches.length} structure(s) en proximité thématique, ${r.bassin.length} autre(s) structure(s) du bassin. Les filtres en cours s'appliquent.</span>
    <label><input type="checkbox" id="reseau-bassin"> Afficher aussi les autres structures du bassin</label>
    <button class="bouton" id="quitter-reseau">Revenir à toutes les structures</button>`;
  $("bandeau-reseau").hidden = false;
  dessiner();
  ouvrir(s);
}
function quitterReseau() {
  reseauDe = null;
  $("bandeau-reseau").hidden = true;
  dessiner();
  $("titre-pro").focus();
}

/* ---------- Mode chemin ---------- */
let grapheChemins = null;
function plusCourt(a, b) { // parcours en largeur sur les partenariats et la proximité thématique
  if (!grapheChemins) {
    grapheChemins = new Map(S.map(s => [s, []]));
    [...PART, ...thematiques(S, "")].forEach(l => { grapheChemins.get(l.source).push(l.target); grapheChemins.get(l.target).push(l.source); });
  }
  const prec = new Map([[a, null]]), file = [a];
  while (file.length) {
    const n = file.shift();
    if (n === b) { const p = []; for (let x = b; x; x = prec.get(x)) p.unshift(x); return p; }
    grapheChemins.get(n).forEach(v => { if (!prec.has(v)) { prec.set(v, n); file.push(v); } });
  }
  return null;
}
function dessinerChemin() {
  const p = chemin.length === 2 ? plusCourt(...chemin) : null;
  const seg = p ? p.slice(1).map((x, i) => ({ source: p[i], target: x, kind: "chemin" })) : [];
  gChemin.selectAll("line").data(seg).join("line").attr("stroke", "#f2a900").attr("stroke-width", 6).attr("stroke-linecap", "round")
    .each(function (l) { bout(d3.select(this), l); });
  if (!modeChemin) return;
  gNoeuds.selectAll(".noeud").classed("estompe", n => !!p && !p.includes(n));
  $("panneau").innerHTML = `<h2 id="fiche-titre" tabindex="-1">Mode chemin</h2>` + (chemin.length < 2
    ? `<p>Choisissez ${chemin.length ? "la structure d'arrivée" : "deux structures"} dans le nuage.</p>${chemin.length ? `<p>Départ : <strong>${esc(chemin[0].nom)}</strong></p>` : ""}`
    : p ? `<ol>${p.map(x => `<li><button class="lienfiche" data-id="${esc(x.id)}">${esc(x.nom)}</button> <span class="info">(${esc(x.commune)})</span></li>`).join("")}</ol>
        <p class="info">Chemin calculé sur les partenariats validés et la proximité thématique (qui ne relie que des structures d'un même bassin).</p>`
    : `<p>Aucun chemin entre <strong>${esc(chemin[0].nom)}</strong> et <strong>${esc(chemin[1].nom)}</strong> : elles ne sont reliées ni par des partenariats, ni par la proximité thématique.</p>`);
}
function basculerChemin() {
  modeChemin = !modeChemin;
  chemin = [];
  $("bt-chemin").setAttribute("aria-pressed", modeChemin);
  gNoeuds.selectAll(".noeud").classed("estompe", false);
  if (modeChemin) dessinerChemin(); else { dessinerChemin(); fermer(); }
}

/* ---------- Vue liste : toute l'information du nuage, sans le nuage ---------- */
function tableau(q) {
  const lignes = visibles.slice().sort((a, b) => (correspond(b, q) - correspond(a, q)) || (b === reseauDe) - (a === reseauDe) || a.nom.localeCompare(b.nom));
  const publics = s => s.publics.length ? s.publics.slice(0, 3).map(p => lib(PUBLICS, p)).join(", ") + (s.publics.length > 3 ? "…" : "") : "—";
  $("vue-liste").innerHTML = `<div class="tableau"><table>
    <caption>${lignes.length} structures ${reseauDe ? `du réseau de ${esc(reseauDe.nom)}` : "correspondant aux filtres"}</caption>
    <thead><tr><th scope="col">Structure</th><th scope="col">Commune et bassin</th><th scope="col">Type</th><th scope="col">Besoins</th>
      <th scope="col">Publics</th><th scope="col">Partenariats</th><th scope="col">Fraîcheur</th><th scope="col"><span class="sr-only">Actions</span></th></tr></thead>
    <tbody>${lignes.map(s => `<tr>
      <td><button class="lienfiche" data-id="${esc(s.id)}">${esc(s.nom)}</button>${correspond(s, q) ? ' <span aria-hidden="true">★</span><span class="sr-only">(correspond à la recherche)</span>' : ""}</td>
      <td>${esc(s.commune)}<br><span class="info">${esc(s.bassin)}</span></td>
      <td>${esc(lib(TYPES, typeDe(s)))}</td>
      <td>${s.besoins.map(libBesoin).join(", ") || "—"}</td>
      <td>${esc(publics(s))}</td>
      <td>${partenariatsDe(s).length}</td>
      <td><span class="badge f-${s.fraicheur}">${esc(FRAICHEUR[s.fraicheur] || FRAICHEUR.inconnue)}</span>${s.maj ? `<br><span class="info">${dateFr(s.maj)}</span>` : ""}</td>
      <td><button class="bouton" data-reseau="${esc(s.id)}">Voir le réseau</button></td></tr>`).join("")}</tbody></table></div>`;
}

function vue(liste) {
  $("bt-vue").setAttribute("aria-pressed", liste);
  $("bt-vue").textContent = liste ? "Vue nuage" : "Vue liste";
  $("graphe").hidden = liste;
  $("vue-liste").hidden = !liste;
  dessiner();
}

function reinitialiser() {
  document.querySelectorAll(".outils select").forEach(s => s.selectedIndex = 0);
  $("recherche").value = "";
  if (modeChemin) basculerChemin();
  if (reseauDe) { reseauDe = null; $("bandeau-reseau").hidden = true; }
  if (D3_OK) svg.transition().duration(DUREE).call(zoom.transform, d3.zoomIdentity);
  fermer();
  dessiner();
}
