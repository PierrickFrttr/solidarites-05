"""Liste les associations du 05 liées à la solidarité (RNA) dans associations.csv, à trier à la main.

Usage : python associations_rna.py
Relancer ajoute les nouvelles associations sans toucher aux lignes déjà présentes (ni à vos choix).
Ouvrir associations.csv dans Excel, mettre « oui » dans la colonne retenir, corriger besoins / tel si besoin.
"""
import csv, json, re, time, urllib.error, urllib.request
from pathlib import Path

RNA = ("https://tabular-api.data.gouv.fr/api/resources/91fd139b-4c2a-4d36-b05b-8607b41f1202/data/"
       "?adrs_codepostal__greater=05000&adrs_codepostal__less=05999&position__exact=A&page_size=50&page=")
FICHIER = Path(__file__).parent / "associations.csv"
COLONNES = ["retenir", "rna", "siret", "nom", "commune", "code_insee", "lat", "lon", "besoins", "tel", "mail", "web", "objet", "maj"]
# ponytail: tri par mots-clés, volontairement large ; c'est l'équipe qui valide ligne par ligne
MOTS = {
    "logement": r"logement|heberg|sans.abri|sdf|sans domicile", "alimentation": r"alimentaire|epicerie solidaire|vestiaire|repas solidaire",
    "sante": r"sante mentale|addict|soins", "emploi": r"insertion professionnelle|retour a l.emploi|chantier d.insertion|demandeurs d.emploi",
    "argent": r"surendett|budget", "droits": r"acces aux droits|precarit|exclusion|pauvret|demarches administratives|migrant|refugi|exil",
    "famille": r"parentalit|soutien aux familles|monoparental", "handicap": r"handicap", "mobilite": r"mobilite solidaire|transport solidaire|garage solidaire",
    "numerique": r"fracture numerique|inclusion numerique", "francais": r"illettrisme|alphabetisation|apprentissage du francais|\bfle\b",
    "violences": r"violences|victimes",
}
assert [b for b, p in MOTS.items() if re.search(p, "lutte contre l'illettrisme et l'exclusion")] == ["droits", "francais"]


def get(url):
    try:
        return json.load(urllib.request.urlopen(url))
    except urllib.error.HTTPError:  # ex. code INSEE d'une ancienne commune fusionnée
        return {}


def main():
    deja = list(csv.DictReader(open(FICHIER, encoding="utf-8-sig"), delimiter=";")) if FICHIER.exists() else []
    connus = {r["rna"] for r in deja}
    nouveaux, centres, page = [], {}, 1
    while True:
        for essai in range(3):  # l'API data.gouv renvoie parfois une erreur 504 passagère
            try:
                lot = json.load(urllib.request.urlopen(RNA + str(page)))["data"]
                break
            except urllib.error.HTTPError:
                if essai == 2:
                    raise
                time.sleep(10)
        for r in lot:
            objet = (r["objet"] or "").lower()
            besoins = [b for b, p in MOTS.items() if re.search(p, objet)]
            # 018 = handicap / médico-social, 019 = interventions sociales (nomenclature RNA)
            if r["id"] in connus or not (besoins or r["objet_social1"][:3] in ("018", "019")):
                continue
            insee = r["adrs_codeinsee"]
            if insee not in centres:
                c = get(f"https://geo.api.gouv.fr/communes/{insee}?fields=centre") if insee else {}
                centres[insee] = c.get("centre", {}).get("coordinates", ["", ""])
            nouveaux.append({
                "retenir": "", "rna": r["id"], "siret": r["siret"], "nom": r["titre"], "commune": r["adrs_libcommune"],
                "code_insee": insee, "lon": centres[insee][0], "lat": centres[insee][1], "besoins": " ".join(besoins),
                "tel": "", "mail": "", "web": r["siteweb"], "objet": r["objet"], "maj": (r["maj_time"] or "")[:10],
            })
        if len(lot) < 50:
            break
        page += 1
    with open(FICHIER, "w", encoding="utf-8-sig", newline="") as f:  # utf-8-sig et « ; » : s'ouvre bien dans Excel
        w = csv.DictWriter(f, COLONNES, delimiter=";")
        w.writeheader()
        w.writerows(deja + nouveaux)
    print(len(nouveaux), "nouvelles associations ajoutées,", len(deja) + len(nouveaux), "au total dans associations.csv")


if __name__ == "__main__":
    main()
