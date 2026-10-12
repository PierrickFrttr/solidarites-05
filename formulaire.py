"""Questionnaire Google Forms pour recueillir les partenariats auprès des structures.

python formulaire.py script            -> formulaire.gs (à coller dans script.google.com) + formulaire_structures.csv
python formulaire.py import REPONSES   -> ajoute les réponses (export CSV du Google Form) à partenariats.csv

Règle de validation : un lien A -> B est « valide » quand les deux structures le déclarent
(A « oriente vers B » et B « reçoit de A »), sinon il reste « en_attente ».
Les courriels des répondants ne sont jamais recopiés dans partenariats.csv (le dépôt est public).
"""
import csv, json, sys
from collections import defaultdict
from datetime import date
from pathlib import Path

ICI = Path(__file__).parent
CORRESPONDANCE = ICI / "formulaire_structures.csv"  # libellé du formulaire -> identifiant de la structure
ABSENTE = "— Ma structure n'est pas dans la liste —"
NB = 6  # nombre de partenaires par sens dans le formulaire
BESOINS = {  # libellés du formulaire -> besoins de import_05.py
    "Logement, hébergement": "logement", "Alimentation, équipement": "alimentation", "Santé": "sante",
    "Emploi, formation": "emploi", "Argent, budget": "argent", "Papiers, accès aux droits": "droits",
    "Famille, enfants": "famille", "Handicap": "handicap", "Mobilité": "mobilite", "Numérique": "numerique",
    "Français, lecture, écriture": "francais", "Violences": "violences", "Plusieurs besoins / autre": "",
}
VERS, BESOIN_VERS = "Vous orientez vers ({})", "Pour quel besoin ? ({})"
DE, BESOIN_DE = "Vous recevez des personnes de ({})", "Pour quel besoin ? (reçues {})"


def creer_script():
    texte = (ICI / "site" / "data.js").read_text(encoding="utf-8")
    structures = json.loads(texte[texte.index("=") + 1:].strip().rstrip(";"))["structures"]
    libelles = {}
    for s in sorted(structures, key=lambda s: (s["nom"].lower(), s["commune"])):
        base = f"{s['nom']} — {s['commune']}"
        lib, n = base, 2
        while lib in libelles:  # Google Forms refuse deux choix identiques
            lib, n = f"{base} ({n})", n + 1
        libelles[lib] = s["id"]
    with open(CORRESPONDANCE, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["libelle", "id"])
        w.writerows(libelles.items())

    js = lambda v: json.dumps(v, ensure_ascii=False)
    paires = lambda q, b: "\n".join(
        f"  f.addListItem().setTitle({js(q.format(i))}).setChoiceValues(S);\n"
        f"  f.addListItem().setTitle({js(b.format(i))}).setChoiceValues(B);" for i in range(1, NB + 1))
    gs = f"""// Crée le questionnaire « Partenariats » : coller dans https://script.google.com puis Exécuter.
function creerFormulaire() {{
  const S = {js(list(libelles))};
  const B = {js(list(BESOINS))};
  const f = FormApp.create("Partenariats entre structures de la solidarité — Hautes-Alpes");
  f.setDescription("Ce questionnaire sert à afficher sur la cartographie Solidarités 05 qui oriente des personnes vers qui. "
    + "Un partenariat n'est publié que si les deux structures le déclarent. Comptez 5 minutes. "
    + "Vos réponses servent uniquement à cette cartographie ; votre courriel n'est jamais publié.");
  f.addListItem().setTitle("Votre structure").setChoiceValues(S.concat([{js(ABSENTE)}])).setRequired(true);
  f.addTextItem().setTitle("Votre courriel (pour vous recontacter si besoin, jamais publié)");
  f.addPageBreakItem().setTitle("Vers qui orientez-vous des personnes ?")
    .setHelpText("Les structures vers lesquelles vous envoyez régulièrement des personnes. Laissez vide ce qui ne sert pas.");
{paires(VERS, BESOIN_VERS)}
  f.addPageBreakItem().setTitle("Qui vous oriente des personnes ?")
    .setHelpText("Les structures qui vous envoient régulièrement des personnes. Laissez vide ce qui ne sert pas.");
{paires(DE, BESOIN_DE)}
  f.addParagraphTextItem().setTitle("Une structure manque dans les listes ? Indiquez son nom et sa commune.");
  Logger.log("Lien à envoyer aux structures : " + f.getPublishedUrl());
  Logger.log("Lien pour modifier le formulaire et voir les réponses : " + f.getEditUrl());
}}
"""
    (ICI / "formulaire.gs").write_text(gs, encoding="utf-8")
    print(len(libelles), "structures dans le formulaire -> formulaire.gs et", CORRESPONDANCE.name)


def importer(fichier_reponses):
    ids = dict(csv.reader(open(CORRESPONDANCE, encoding="utf-8")))
    ids.pop("libelle", None)
    declare = defaultdict(lambda: {"par_de": False, "par_vers": False, "besoin": ""})  # (de, vers) -> qui l'a déclaré
    avert = []
    for r in csv.DictReader(open(fichier_reponses, encoding="utf-8-sig")):
        moi = ids.get(r["Votre structure"])
        if not moi:
            avert.append(f"réponse ignorée : structure « {r['Votre structure']} » hors liste ({r.get('Une structure manque dans les listes ? Indiquez son nom et sa commune.', '')})")
            continue
        for i in range(1, NB + 1):
            for q, qb, sens in ((VERS, BESOIN_VERS, "vers"), (DE, BESOIN_DE, "de")):
                autre = r.get(q.format(i), "")
                if not autre:
                    continue
                if autre not in ids:
                    avert.append(f"choix inconnu ignoré : {autre}")
                    continue
                cle = (moi, ids[autre]) if sens == "vers" else (ids[autre], moi)
                if cle[0] == cle[1]:
                    continue
                d = declare[cle]
                d["par_de" if sens == "vers" else "par_vers"] = True
                d["besoin"] = d["besoin"] or BESOINS.get(r.get(qb.format(i), ""), "")

    chemin = ICI / "partenariats.csv"
    lignes = list(csv.DictReader(open(chemin, encoding="utf-8")))
    existants = {(l["de"], l["vers"]): l for l in lignes}
    ajouts = valides = 0
    for (de, vers), d in declare.items():
        statut = "valide" if d["par_de"] and d["par_vers"] else "en_attente"
        l = existants.get((de, vers))
        if l is None:
            lignes.append({"de": de, "vers": vers, "besoin": d["besoin"], "statut": statut,
                           "date": date.today().isoformat() if statut == "valide" else ""})
            ajouts += 1
            valides += statut == "valide"
        elif l["statut"] == "en_attente" and statut == "valide":  # confirmé depuis ; un « refuse » n'est jamais écrasé
            l.update(statut="valide", date=date.today().isoformat(), besoin=l["besoin"] or d["besoin"])
            valides += 1
    with open(chemin, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, ["de", "vers", "besoin", "statut", "date"])
        w.writeheader()
        w.writerows(lignes)
    for a in avert:
        print("Avertissement :", a)
    print(f"{ajouts} partenariat(s) ajouté(s), {valides} validé(s) (déclarés des deux côtés) -> partenariats.csv")


if __name__ == "__main__":
    if sys.argv[1:2] == ["script"]:
        creer_script()
    elif sys.argv[1:2] == ["import"] and len(sys.argv) == 3:
        importer(sys.argv[2])
    else:
        print(__doc__)
