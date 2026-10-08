"""Import data·inclusion -> site/data.js (structures des Hautes-Alpes).

Usage : python import_05.py            (télécharge la dernière version sur data.gouv.fr)
        python import_05.py DOSSIER    (utilise structures.csv et services.csv déjà téléchargés)
"""
import ast, csv, io, json, math, sys, urllib.request
from pathlib import Path

DATASET = "https://www.data.gouv.fr/api/1/datasets/6233723c2c1e4a54af2f6b2d/"
ICI = Path(__file__).parent

# Les 12 besoins grand public -> thématiques data·inclusion
BESOINS = {
    "logement": ["logement-hebergement"],
    "alimentation": ["equipement-et-alimentation"],
    "sante": ["sante"],
    "emploi": ["trouver-un-emploi", "preparer-sa-candidature", "choisir-un-metier", "se-former", "creer-une-entreprise"],
    "argent": ["difficultes-financieres"],
    "droits": ["difficultes-administratives-ou-juridiques"],
    "famille": ["famille"],
    "handicap": ["handicap"],
    "mobilite": ["mobilite"],
    "numerique": ["numerique"],
    "francais": ["lecture-ecriture-calcul", "apprendre-francais"],
    "violences": ["violences"],
}
# ponytail: bassin = centre le plus proche, à remplacer par une table code INSEE -> bassin si les élus contestent une frontière
BASSINS = {
    "Gap": (44.559, 6.078), "Briançon": (44.899, 6.643), "Embrun-Savines": (44.564, 6.45),
    "Buëch-Laragne": (44.40, 5.78), "Champsaur-Valgaudemar": (44.70, 6.10),
    "Queyras": (44.76, 6.79), "Guillestrois": (44.66, 6.65),
}


def bassin(lat, lon):
    if not lat:
        return "Non localisé"
    return min(BASSINS, key=lambda b: math.dist((float(lat), float(lon)), BASSINS[b]))


def besoins(thematiques, publics):
    out = {b for b, ts in BESOINS.items() for t in thematiques for x in ts if x in t}
    if "personnes-en-situation-de-handicap" in publics:
        out.add("handicap")
    return out


assert bassin("44.534", "5.82") == "Buëch-Laragne"  # Veynes
assert bassin("44.682", "6.077") == "Champsaur-Valgaudemar"  # Saint-Bonnet
assert besoins(["sante--acces-aux-soins"], []) == {"sante"}


def liste(s):
    return ast.literal_eval(s) if s else []


def lire(dossier, nom):
    if dossier:
        return csv.DictReader(open(Path(dossier) / f"{nom}.csv", encoding="utf-8"))
    res = json.load(urllib.request.urlopen(DATASET))["resources"]
    url = next(r["url"] for r in res if r["title"].startswith(f"{nom}-inclusion") and r["format"] == "csv")
    print("Téléchargement", url)
    lignes = io.StringIO(urllib.request.urlopen(url).read().decode("utf-8"), newline="")
    return csv.DictReader(lignes)


def main(dossier=None):
    structures, par_id = {}, {}
    for r in lire(dossier, "structures"):
        if not r["code_insee"].startswith("05"):
            continue
        cle = r["siret"] or r["id"]  # même SIRET = même établissement, présent dans plusieurs sources
        s = structures.setdefault(cle, {
            "id": cle, "nom": r["nom"], "siret": r["siret"], "commune": r["commune"], "cp": r["code_postal"],
            "adresse": r["adresse"], "lat": float(r["latitude"]) if r["latitude"] else None,
            "lon": float(r["longitude"]) if r["longitude"] else None,
            "tel": r["telephone"], "mail": r["courriel"], "web": r["site_web"], "description": r["description"],
            "horaires": r["horaires_accueil"], "accessibilite": r["accessibilite_lieu"],
            "maj": r["date_maj"], "sources": [], "liens_source": [],
            "bassin": bassin(r["latitude"], r["longitude"]), "services": [], "besoins": set(), "publics": set(),
        })
        if r["source"] not in s["sources"]:
            s["sources"].append(r["source"])
            s["liens_source"].append(r["lien_source"])
        s["maj"] = max(s["maj"], r["date_maj"])
        for champ, col in [("tel", "telephone"), ("mail", "courriel"), ("web", "site_web"), ("description", "description")]:
            s[champ] = s[champ] or r[col]
        par_id[r["id"]] = s

    for r in lire(dossier, "services"):
        s = par_id.get(r["structure_id"])
        if not s:
            continue
        th, pu = liste(r["thematiques"]), liste(r["publics"])
        s["services"].append({
            "nom": r["nom"], "description": r["description"][:400], "thematiques": th, "publics": pu,
            "conditions": r["conditions_acces"], "frais": r["frais"], "frais_precisions": r["frais_precisions"],
            "modes": liste(r["modes_accueil"]), "besoins": sorted(besoins(th, pu)),
        })
        s["besoins"] |= besoins(th, pu)
        s["publics"] |= set(pu)
        s["tel"] = s["tel"] or r["telephone"]
        s["mail"] = s["mail"] or r["courriel"]

    for s in structures.values():
        s["besoins"], s["publics"] = sorted(s["besoins"]), sorted(s["publics"])

    partenariats = [p for p in csv.DictReader(open(ICI / "partenariats.csv", encoding="utf-8"))
                    if p["statut"] == "valide" and p["de"] in structures and p["vers"] in structures]

    data = {"structures": list(structures.values()), "partenariats": partenariats}
    (ICI / "site" / "data.js").write_text("window.DATA = " + json.dumps(data, ensure_ascii=False) + ";\n", encoding="utf-8")
    print(len(structures), "structures,", sum(len(s["services"]) for s in structures.values()), "services,",
          len(partenariats), "partenariats validés -> site/data.js")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
