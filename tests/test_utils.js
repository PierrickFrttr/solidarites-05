// Tests des fonctions du site (site/js/config.js + site/js/utils.js). Lancer : node tests/test_utils.js
const assert = require("node:assert/strict"), fs = require("node:fs"), path = require("node:path"), vm = require("node:vm");
const ctx = vm.createContext({ URL });
for (const f of ["config.js", "utils.js"]) vm.runInContext(fs.readFileSync(path.join(__dirname, "../site/js", f), "utf8"), ctx);
const { CONFIG, esc, telephone, urlSure, courriel, dist, enCommun, thematiques, classer } = vm.runInContext(
  "({ CONFIG, esc, telephone, urlSure, courriel, dist, enCommun, thematiques, classer })", ctx);

let n = 0;
const same = (a, b) => assert.equal(JSON.stringify(a), JSON.stringify(b)); // objets issus du bac à sable vm
const test = (nom, f) => { f(); n++; };

test("échappement HTML", () => assert.equal(esc(`<a href="x">'&`), "&lt;a href=&quot;x&quot;&gt;&#39;&amp;"));
test("téléphone", () => {
  same(telephone("+33492553398"), { lien: "tel:0492553398", texte: "04 92 55 33 98" });
  assert.equal(telephone("12"), null);
  assert.equal(telephone(""), null);
});
test("site web", () => {
  assert.equal(urlSure("www.exemple.org"), "https://www.exemple.org/");
  assert.equal(urlSure("javascript:alert(1)"), null);
  assert.equal(urlSure(""), null);
});
test("courriel", () => { assert.equal(courriel("a@b.fr"), "a@b.fr"); assert.equal(courriel("pas un mail"), null); });
test("distance Gap-Briançon ≈ 64 km", () => assert.ok(Math.abs(dist({ lat: 44.559, lon: 6.078 }, { lat: 44.899, lon: 6.643 }) - 60) < 8));

const S = (id, o) => Object.assign({ id, nom: id, bassin: "Gap", publics: [], besoins: ["logement"], services: [{ besoins: ["logement"] }],
  tel: "", adresse: "", horaires: "", web: "", lat: null, lon: null, fraicheur: "inconnue" }, o);

test("liens thématiques : même bassin, besoin commun, publics compatibles", () => {
  const a = S("a"), b = S("b"), c = S("c", { bassin: "Queyras" }), d = S("d", { publics: ["jeunes"] }), e = S("e", { publics: ["seniors"] });
  same(enCommun(a, b), ["logement"]);
  same(enCommun(a, c), []);        // autre bassin
  same(enCommun(d, e), []);        // publics incompatibles
  same(enCommun(a, b, "sante"), []);
  assert.equal(thematiques([a, b, c, d, e]).length, 5); // a-b, a-d, a-e, b-d, b-e (pas c, pas d-e)
});

test("classement : filtre le besoin, puis proximité et informations pratiques", () => {
  const P = CONFIG.SCORE, ici = { lat: 44.56, lon: 6.08 };
  const loin = S("loin", { lat: 44.9, lon: 6.64, tel: "0492000000" });
  const proche = S("proche", { lat: 44.56, lon: 6.08 });
  const procheTel = S("procheTel", { lat: 44.56, lon: 6.08, tel: "0492000000", fraicheur: "recent" });
  const horsSujet = S("horsSujet", { besoins: ["sante"] });
  const r = classer([loin, proche, procheTel, horsSujet], { besoin: "logement", position: ici }, P).map(s => s.id);
  same(r, ["procheTel", "proche", "loin"]);
});
test("classement : public choisi", () => {
  const P = CONFIG.SCORE;
  const jeunes = S("jeunes", { publics: ["jeunes"] }), tous = S("tous", { publics: ["tous-publics"] }), seniors = S("seniors", { publics: ["seniors"] });
  same(classer([tous, seniors, jeunes], { besoin: "logement", public: "jeunes" }, P).map(s => s.id), ["jeunes", "tous"]);
});

console.log(`${n} tests JavaScript OK`);
