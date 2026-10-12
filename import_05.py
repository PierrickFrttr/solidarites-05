"""Import data·inclusion (+ associations RNA retenues) -> site/data.js, avec contrôles avant publication.

Usage : python import_05.py            (télécharge la dernière version sur data.gouv.fr)
        python import_05.py DOSSIER    (utilise structures.csv et services.csv déjà téléchargés)

Si un contrôle échoue, le script s'arrête avec un message clair et site/data.js n'est PAS modifié.
Pour accepter une baisse légitime : IGNORER_CONTROLES=structures,services python import_05.py (ou « tout »).
"""
import ast, csv, hashlib, io, json, math, os, re, sys, unicodedata, urllib.request
from collections import Counter
from datetime import date
from pathlib import Path

DATASET = "https://www.data.gouv.fr/api/1/datasets/6233723c2c1e4a54af2f6b2d/"
ICI = Path(__file__).parent
SORTIE = ICI / "site" / "data.js"

# ==================== PARAMÈTRES (voir README, « Modifier les paramètres ») ====================

# Liste centrale des besoins de l'application (libellés et pictos : site/js/config.js).
BESOINS = ["logement", "alimentation", "sante", "emploi", "argent", "droits",
           "famille", "handicap", "mobilite", "numerique", "francais", "violences"]

# Chaque catégorie data·inclusion doit figurer ici : un besoin, ou None si elle est volontairement non affichée.
# Une catégorie absente de cette table fait échouer l'import (rien n'est perdu sans qu'on le sache).
CATEGORIES_DI = {
    "logement-hebergement": "logement", "equipement-et-alimentation": "alimentation", "sante": "sante",
    "trouver-un-emploi": "emploi", "preparer-sa-candidature": "emploi", "choisir-un-metier": "emploi",
    "se-former": "emploi", "creer-une-entreprise": "emploi", "difficultes-financieres": "argent",
    "difficultes-administratives-ou-juridiques": "droits", "famille": "famille", "mobilite": "mobilite",
    "numerique": "numerique", "lecture-ecriture-calcul": "francais",
    "remobilisation": None,            # lien social, confiance en soi : pas de besoin grand public équivalent
    "souvrir-a-linternational": None,  # mobilité internationale : hors périmètre
}
# Sous-thématiques qui ajoutent un besoin en plus de celui de leur catégorie.
SOUS_THEMATIQUES_DI = {"famille--surmonter-conflits-separation-violence": "violences"}
# Publics qui ajoutent un besoin.
PUBLICS_BESOIN = {"personnes-en-situation-de-handicap": "handicap"}

# Bassins de vie : chaque structure est rattachée au centre le plus proche (lat, lon).
# Approximation assumée : à remplacer par une table officielle « code INSEE -> bassin » quand elle sera validée.
BASSINS = {
    "Gap": (44.559, 6.078), "Briançon": (44.899, 6.643), "Embrun-Savines": (44.564, 6.45),
    "Buëch-Laragne": (44.40, 5.78), "Champsaur-Valgaudemar": (44.70, 6.10),
    "Queyras": (44.76, 6.79), "Guillestrois": (44.66, 6.65),
}
NON_LOCALISE = "Non localisé"
# Emprise des Hautes-Alpes (avec marge) : des coordonnées en dehors sont jugées aberrantes et ignorées.
EMPRISE_05 = {"lat": (44.0, 45.3), "lon": (5.3, 7.2)}

# Fraîcheur d'une fiche selon sa date de mise à jour (en jours).
FRAICHEUR_JOURS = {"recent": 183, "a_verifier": 365}  # < 6 mois : récent, 6-12 mois : à vérifier, > 12 mois : ancien

STATUTS_PARTENARIAT = {"valide", "en_attente", "refuse"}
# Liens institutionnels : règles « tel réseau peut orienter vers tel réseau » (regles_orientation.csv).
PERIMETRES = {"departement", "plus_proche"}  # vers toutes les structures cibles du 05, ou depuis la source la plus proche

# Contrôle de régression : baisse maximale tolérée par rapport aux données déjà publiées.
SEUILS = {"structures": 0.30, "services": 0.30, "geolocalisees": 0.30, "partenariats": 0.50, "institutionnels": 0.50,
          "bassin": 0.50, "besoin": 0.50}
EFFECTIF_MIN = 5  # un bassin ou un besoin plus petit que ça n'est pas contrôlé (trop de bruit)

# ================================================================================================


def coordonnees(lat, lon):
    """(lat, lon) en nombres, ou None si absentes. ValueError si invalides ou hors des Hautes-Alpes."""
    if lat in ("", None) and lon in ("", None):
        return None
    try:
        lat, lon = float(lat), float(lon)
    except (TypeError, ValueError):
        raise ValueError(f"coordonnées illisibles ({lat}, {lon})")
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError(f"coordonnées impossibles ({lat}, {lon})")
    if not (EMPRISE_05["lat"][0] <= lat <= EMPRISE_05["lat"][1] and EMPRISE_05["lon"][0] <= lon <= EMPRISE_05["lon"][1]):
        raise ValueError(f"coordonnées hors des Hautes-Alpes ({lat}, {lon})")
    return lat, lon


def bassin(coord):
    if not coord:
        return NON_LOCALISE
    return min(BASSINS, key=lambda b: math.dist(coord, BASSINS[b]))


def besoins_de(thematiques, publics):
    """Besoins de l'application couverts par un service. ValueError si une catégorie est inconnue."""
    out = set()
    for t in thematiques:
        cat = t.split("--")[0]
        if cat not in CATEGORIES_DI:
            raise ValueError(f"catégorie data·inclusion inconnue « {cat} » : l'ajouter dans CATEGORIES_DI")
        out |= {b for b in (CATEGORIES_DI[cat], SOUS_THEMATIQUES_DI.get(t)) if b}
    return out | {PUBLICS_BESOIN[p] for p in publics if p in PUBLICS_BESOIN}


def fraicheur(maj, aujourdhui):
    """recent / a_verifier / ancien, ou inconnue si la source ne donne pas de date."""
    try:
        jours = (aujourdhui - date.fromisoformat(maj[:10])).days
    except (TypeError, ValueError):
        return "inconnue"
    return "recent" if jours < FRAICHEUR_JOURS["recent"] else "a_verifier" if jours <= FRAICHEUR_JOURS["a_verifier"] else "ancien"


def simple(texte):
    return re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFKD", (texte or "").lower()))


def liste(s):
    return ast.literal_eval(s) if s else []


def lieu(r):
    return simple(r["adresse"]) or simple(r["commune"])


def identifiants(lignes):
    """Une fiche par lieu : identifiant de chaque ligne source (par son id data·inclusion).
    Deux lignes de même SIRET sont la même structure si elles ont la même adresse ou le même nom
    (une structure présente dans plusieurs sources). Un SIRET partagé par plusieurs lieux distincts
    (ex. les Maisons des Solidarités du Département) donne une fiche par lieu, d'identifiant
    « SIRET-empreinte », stable d'un import à l'autre. Un SIRET à un seul lieu garde le SIRET comme identifiant."""
    par_siret = {}
    for r in lignes:
        if r["siret"]:
            par_siret.setdefault(r["siret"], []).append(r)
    ids = {r["id"]: r["id"] for r in lignes if not r["siret"]}
    for siret, rs in par_siret.items():
        groupes = []  # chaque groupe : (lieux, noms, lignes)
        for r in rs:
            lie = [g for g in groupes if lieu(r) in g[0] or simple(r["nom"]) in g[1]]
            nouveau = ({lieu(r)}, {simple(r["nom"])}, [r])
            for g in lie:
                groupes.remove(g)
                nouveau[0].update(g[0]); nouveau[1].update(g[1]); nouveau[2].extend(g[2])
            groupes.append(nouveau)
        for lieux, _, membres in groupes:
            cle = siret if len(groupes) == 1 else f"{siret}-{hashlib.sha1(min(lieux).encode()).hexdigest()[:6]}"
            ids.update({m["id"]: cle for m in membres})
    return ids


def construire(lignes_structures, lignes_services, lignes_associations, aujourdhui):
    """Assemble les structures du 05. Retourne (structures par id, erreurs, avertissements)."""
    structures, par_id, erreurs, avert = {}, {}, [], []

    def placer(s, lat, lon):
        try:
            s["lat"], s["lon"] = coordonnees(lat, lon) or (None, None)
        except ValueError as e:
            avert.append(f"{s['nom']} : {e}, structure affichée sans position")
            s["lat"] = s["lon"] = None
        s["bassin"] = bassin((s["lat"], s["lon"]) if s["lat"] is not None else None)

    lignes_05 = [r for r in lignes_structures if (r.get("code_insee") or "").startswith("05")]
    ids = identifiants(lignes_05)
    for r in lignes_05:
        cle = ids[r["id"]]
        if not cle:
            erreurs.append(f"structure sans identifiant : {r.get('nom')!r}")
            continue
        if not r["nom"].strip():
            erreurs.append(f"structure sans nom : {cle}")
            continue
        if cle not in structures:
            s = structures[cle] = {
                "id": cle, "nom": r["nom"].strip(), "siret": r["siret"], "commune": r["commune"], "cp": r["code_postal"],
                "adresse": r["adresse"], "tel": r["telephone"], "mail": r["courriel"], "web": r["site_web"],
                "description": r["description"], "horaires": r["horaires_accueil"], "accessibilite": r["accessibilite_lieu"],
                "maj": r["date_maj"], "sources": [], "liens_source": [], "services": [], "besoins": set(), "publics": set(),
                "reseaux": set(),
            }
            placer(s, r["latitude"], r["longitude"])
        s = structures[cle]
        if r["source"] not in s["sources"]:
            s["sources"].append(r["source"])
            s["liens_source"].append(r["lien_source"])
        s["maj"] = max(s["maj"], r["date_maj"])
        s["reseaux"] |= set(liste(r.get("reseaux_porteurs", "")))
        for champ, col in [("tel", "telephone"), ("mail", "courriel"), ("web", "site_web"), ("description", "description")]:
            s[champ] = s[champ] or r[col]
        par_id[r["id"]] = s

    orphelins = 0
    for r in lignes_services:
        s = par_id.get(r["structure_id"])
        if not s:
            orphelins += (r.get("code_insee") or "").startswith("05")
            continue
        if not r["nom"].strip():
            erreurs.append(f"service sans nom ({r['id']}) pour {s['nom']}")
            continue
        th, pu = liste(r["thematiques"]), liste(r["publics"])
        try:
            b = besoins_de(th, pu)
        except ValueError as e:
            erreurs.append(f"service {r['id']} : {e}")
            continue
        s["services"].append({
            "nom": r["nom"].strip(), "description": r["description"][:400], "thematiques": th, "publics": pu,
            "conditions": r["conditions_acces"], "frais": r["frais"], "frais_precisions": r["frais_precisions"],
            "modes": liste(r["modes_accueil"]), "besoins": sorted(b),
        })
        s["besoins"] |= b
        s["publics"] |= set(pu)
        s["tel"] = s["tel"] or r["telephone"]
        s["mail"] = s["mail"] or r["courriel"]
    if orphelins:
        avert.append(f"{orphelins} service(s) situé(s) dans le 05 rattaché(s) à une structure absente des données du 05")

    # Associations du RNA retenues à la main dans associations.csv (voir associations_rna.py)
    noms = {simple(s["nom"]): s["nom"] for s in structures.values() if len(simple(s["nom"])) >= 6}
    for n, a in enumerate(lignes_associations, start=2):
        if a["retenir"].strip().lower() != "oui":
            continue
        # ponytail: rapprochement par nom (« CIDFF 05 » dans « CIDFF 05 CENTRE D'INFORMATION… »), à affiner si faux positifs
        doublon = next((s["nom"] for s in structures.values() if a["siret"] and s["siret"] == a["siret"]), None) or next((v for k, v in noms.items() if k in simple(a["nom"])), None)
        if doublon:
            avert.append(f"association {a['nom']} ignorée : déjà sur le site ({doublon})")
            continue
        inconnus = set(a["besoins"].split()) - set(BESOINS)
        if inconnus:
            erreurs.append(f"associations.csv ligne {n} ({a['nom']}) : besoin(s) inconnu(s) {sorted(inconnus)}, valeurs possibles : {BESOINS}")
            continue
        cle, b = a["siret"] or a["rna"], set(a["besoins"].split())
        s = structures[cle] = {
            "id": cle, "nom": a["nom"].strip(), "siret": a["siret"], "commune": a["commune"], "cp": "", "adresse": "",
            "tel": a["tel"], "mail": a["mail"], "web": a["web"], "description": a["objet"], "horaires": "",
            "accessibilite": "", "maj": a["maj"], "sources": ["rna"], "liens_source": [""], "besoins": b, "publics": set(),
            "reseaux": set(),
            "services": [{"nom": "Objet de l'association", "description": a["objet"][:400], "thematiques": [], "publics": [],
                          "conditions": "", "frais": "", "frais_precisions": "", "modes": [], "besoins": sorted(b)}],
        }
        placer(s, a["lat"], a["lon"])

    for s in structures.values():
        s["besoins"], s["publics"], s["reseaux"] = sorted(s["besoins"]), sorted(s["publics"]), sorted(s["reseaux"])
        s["fraicheur"] = fraicheur(s["maj"], aujourdhui)
    avert += doublons_probables(structures.values())
    return structures, erreurs, avert


def doublons_probables(structures):
    """Même nom et même commune sous deux identifiants différents : signalé, pas fusionné."""
    vus, avert = {}, []
    for s in structures:
        cle = (simple(s["nom"]), simple(s["commune"]))
        if cle in vus:
            avert.append(f"doublon probable : « {s['nom']} » ({s['commune']}) sous les identifiants {vus[cle]} et {s['id']}")
        vus.setdefault(cle, s["id"])
    return avert


def partenariats(lignes, ids):
    """Contrôle partenariats.csv. Retourne (partenariats publiables, erreurs)."""
    publies, erreurs, vus = [], [], set()
    for n, p in enumerate(lignes, start=2):
        ou = f"partenariats.csv ligne {n}"
        de, vers, statut, besoin = p["de"].strip(), p["vers"].strip(), p["statut"].strip(), p["besoin"].strip()
        if de not in ids:
            erreurs.append(f"{ou} : structure « de » inconnue ({de!r})")
        if vers not in ids:
            erreurs.append(f"{ou} : structure « vers » inconnue ({vers!r})")
        if de == vers:
            erreurs.append(f"{ou} : une structure ne peut pas être partenaire d'elle-même ({de})")
        if statut not in STATUTS_PARTENARIAT:
            erreurs.append(f"{ou} : statut {statut!r} inconnu, valeurs possibles : {sorted(STATUTS_PARTENARIAT)}")
        if besoin and besoin not in BESOINS:
            erreurs.append(f"{ou} : besoin {besoin!r} inconnu, valeurs possibles : {BESOINS}")
        if (de, vers, besoin) in vus:
            erreurs.append(f"{ou} : doublon du partenariat {de} -> {vers} ({besoin or 'sans besoin'})")
        vus.add((de, vers, besoin))
        if statut == "valide":
            publies.append({"de": de, "vers": vers, "besoin": besoin, "statut": statut, "date": p.get("date", "").strip()})
    return publies, erreurs


def liens_institutionnels(structures, regles):
    """Applique regles_orientation.csv. Retourne (liens, erreurs, avertissements)."""
    S, liens, vus, erreurs, avert = list(structures), [], set(), [], []
    for n, r in enumerate(regles, start=2):
        ou = f"regles_orientation.csv ligne {n}"
        if r["perimetre"] not in PERIMETRES:
            erreurs.append(f"{ou} : périmètre {r['perimetre']!r} inconnu, valeurs possibles : {sorted(PERIMETRES)}")
            continue
        if r["besoin"] and r["besoin"] not in BESOINS:
            erreurs.append(f"{ou} : besoin {r['besoin']!r} inconnu, valeurs possibles : {BESOINS}")
            continue
        exclure = (r.get("exclure") or "").strip()
        sources = [s for s in S if r["de_reseau"] in s["reseaux"] and not (exclure and re.search(exclure, s["nom"], re.I))]
        cibles = [s for s in S if r["vers_reseau"] in s["reseaux"]]
        if not sources or not cibles:
            avert.append(f"{ou} sans effet : aucune structure du réseau {r['de_reseau'] if not sources else r['vers_reseau']}")
            continue
        for c in cibles:
            if r["perimetre"] == "plus_proche":
                placees = [s for s in sources if s["lat"] is not None]
                if c["lat"] is None or not placees:
                    avert.append(f"{ou} : {c['nom']} sans position, pas de « {r['de_reseau']} » le plus proche")
                    continue
                choix = [min(placees, key=lambda s: math.dist((s["lat"], s["lon"]), (c["lat"], c["lon"])))]
            else:
                choix = sources
            for s in choix:
                if s["id"] != c["id"] and (s["id"], c["id"]) not in vus:
                    vus.add((s["id"], c["id"]))
                    liens.append({"de": s["id"], "vers": c["id"], "besoin": r["besoin"], "motif": r["motif"]})
    return liens, erreurs, avert


def statistiques(data):
    S = data["structures"]
    return {
        "structures": len(S), "services": sum(len(s["services"]) for s in S),
        "geolocalisees": sum(1 for s in S if s.get("lat") is not None), "partenariats": len(data["partenariats"]),
        "institutionnels": len(data.get("institutionnels", [])),
        "bassin": dict(Counter(s["bassin"] for s in S)), "besoin": dict(Counter(b for s in S for b in s["besoins"])),
        "fraicheur": dict(Counter(s.get("fraicheur", "inconnue") for s in S)),
    }


def anomalies(avant, apres, seuils=SEUILS, ignorer=()):
    """Compare deux jeux de statistiques. Retourne la liste des baisses anormales (vide si tout va bien)."""
    out = []
    if apres["structures"] == 0:
        return ["aucune structure dans les nouvelles données"]
    for cle in ("structures", "services", "geolocalisees", "partenariats", "institutionnels"):
        a, b = avant.get(cle, 0), apres.get(cle, 0)
        if cle not in ignorer and a > 0 and (a - b) / a > seuils[cle]:
            out.append(f"{cle} : {a} -> {b} (-{(a - b) / a:.0%}, seuil {seuils[cle]:.0%})")
    for cle in ("bassin", "besoin"):
        if cle in ignorer:
            continue
        for k, a in avant.get(cle, {}).items():
            b = apres[cle].get(k, 0)
            if a >= EFFECTIF_MIN and (a - b) / a > seuils[cle]:
                out.append(f"{cle} « {k} » : {a} -> {b} (-{(a - b) / a:.0%}, seuil {seuils[cle]:.0%})")
    return out


def lire_data(chemin):
    """Relit un data.js publié (None s'il n'existe pas)."""
    if not chemin.exists():
        return None
    texte = chemin.read_text(encoding="utf-8").strip()
    return json.loads(texte[texte.index("=") + 1:].rstrip(";"))


def rapport(stats):
    lignes = [f"Structures : {stats['structures']} (géolocalisées : {stats['geolocalisees']})",
              f"Services : {stats['services']}", f"Partenariats publiés : {stats['partenariats']}",
              f"Liens institutionnels : {stats['institutionnels']}",
              "Bassins : " + ", ".join(f"{k} {v}" for k, v in sorted(stats["bassin"].items())),
              "Besoins : " + ", ".join(f"{k} {stats['besoin'].get(k, 0)}" for k in BESOINS),
              "Fraîcheur : " + ", ".join(f"{k} {v}" for k, v in sorted(stats["fraicheur"].items()))]
    return "\n".join(lignes)


def lire_source(dossier, nom):
    if dossier:
        return csv.DictReader(open(Path(dossier) / f"{nom}.csv", encoding="utf-8"))
    res = json.load(urllib.request.urlopen(DATASET))["resources"]
    url = next(r["url"] for r in res if r["title"].startswith(f"{nom}-inclusion") and r["format"] == "csv")
    print("Téléchargement", url)
    return csv.DictReader(io.StringIO(urllib.request.urlopen(url).read().decode("utf-8"), newline=""))


def lire_csv(nom, **options):
    f = ICI / nom
    return list(csv.DictReader(open(f, encoding=options.pop("encoding", "utf-8"), newline=""), **options)) if f.exists() else []


def main(dossier=None):
    aujourdhui = date.today()
    structures, erreurs, avert = construire(
        lire_source(dossier, "structures"), lire_source(dossier, "services"),
        lire_csv("associations.csv", encoding="utf-8-sig", delimiter=";"), aujourdhui)
    publies, err_part = partenariats(lire_csv("partenariats.csv"), set(structures))
    erreurs += err_part
    institutionnels, err_inst, avert_inst = liens_institutionnels(structures.values(), lire_csv("regles_orientation.csv"))
    erreurs += err_inst
    avert += avert_inst

    data = {"genere_le": aujourdhui.isoformat(), "fraicheur_jours": FRAICHEUR_JOURS,
            "structures": list(structures.values()), "partenariats": publies, "institutionnels": institutionnels}
    stats = statistiques(data)
    print(rapport(stats))
    for a in avert:
        print("Avertissement :", a)

    ignorer = {c.strip() for c in os.environ.get("IGNORER_CONTROLES", "").split(",") if c.strip()}
    ancien = lire_data(SORTIE)
    regressions = anomalies(statistiques(ancien), stats, ignorer=set(SEUILS) if "tout" in ignorer else ignorer) if ancien else []
    if ignorer:
        print("Contrôles de régression ignorés :", ", ".join(sorted(ignorer)))

    resume = os.environ.get("GITHUB_STEP_SUMMARY")
    if resume:
        with open(resume, "a", encoding="utf-8") as f:
            f.write("## Import des données\n\n```\n" + rapport(stats) + "\n```\n"
                    + "".join(f"- ❌ {e}\n" for e in erreurs + regressions) + "".join(f"- ⚠️ {a}\n" for a in avert))

    if erreurs or regressions:
        for e in erreurs:
            print("ERREUR :", e)
        for r in regressions:
            print("ANOMALIE (baisse anormale) :", r)
        if regressions:
            print("Si cette baisse est normale, relancer avec IGNORER_CONTROLES=" + ",".join(sorted({r.split(' ')[0] for r in regressions})))
        print("Échec : site/data.js n'a pas été modifié.")
        sys.exit(1)

    tmp = SORTIE.with_suffix(".tmp")
    tmp.write_text("window.DATA = " + json.dumps(data, ensure_ascii=False) + ";\n", encoding="utf-8")
    assert statistiques(lire_data(tmp)) == stats, "relecture de data.js incohérente"
    tmp.replace(SORTIE)
    print("OK -> site/data.js")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
