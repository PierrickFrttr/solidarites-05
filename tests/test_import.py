"""Tests de import_05.py. Lancer : python -m unittest discover -s tests -v"""
import sys, unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import import_05 as imp

AUJ = date(2026, 10, 12)


def structure(id_, nom="Asso", insee="05061", lat="44.56", lon="6.08", source="dora", siret=""):
    return {"id": id_, "siret": siret, "nom": nom, "commune": "Gap", "code_postal": "05000", "code_insee": insee,
            "adresse": "", "latitude": lat, "longitude": lon, "telephone": "", "courriel": "", "site_web": "",
            "description": "", "source": source, "date_maj": "2026-09-01", "lien_source": "", "horaires_accueil": "",
            "accessibilite_lieu": ""}


def service(id_, structure_id, thematiques="['sante--sante-mentale']", publics="[]", nom="Accueil"):
    return {"id": id_, "structure_id": structure_id, "nom": nom, "description": "", "thematiques": thematiques,
            "publics": publics, "conditions_acces": "", "frais": "", "frais_precisions": "", "modes_accueil": "[]",
            "telephone": "", "courriel": "", "code_insee": "05061"}


class Coordonnees(unittest.TestCase):
    def test_valides(self):
        self.assertEqual(imp.coordonnees("44.56", "6.08"), (44.56, 6.08))

    def test_absentes(self):
        self.assertIsNone(imp.coordonnees("", ""))

    def test_impossibles(self):
        for lat, lon in [("91", "6"), ("44", "181"), ("abc", "6")]:
            with self.assertRaises(ValueError):
                imp.coordonnees(lat, lon)

    def test_hors_departement(self):
        with self.assertRaisesRegex(ValueError, "hors des Hautes-Alpes"):
            imp.coordonnees("46.03", "3.58")  # Vichy


class Bassins(unittest.TestCase):
    def test_attribution(self):
        self.assertEqual(imp.bassin((44.534, 5.82)), "Buëch-Laragne")  # Veynes
        self.assertEqual(imp.bassin((44.682, 6.077)), "Champsaur-Valgaudemar")  # Saint-Bonnet
        self.assertEqual(imp.bassin((44.899, 6.643)), "Briançon")

    def test_sans_position(self):
        self.assertEqual(imp.bassin(None), imp.NON_LOCALISE)


class Besoins(unittest.TestCase):
    def test_mapping(self):
        self.assertEqual(imp.besoins_de(["sante--sante-mentale", "se-former--trouver-sa-formation"], []), {"sante", "emploi"})

    def test_sous_thematique_et_public(self):
        b = imp.besoins_de(["famille--surmonter-conflits-separation-violence"], ["personnes-en-situation-de-handicap"])
        self.assertEqual(b, {"famille", "violences", "handicap"})

    def test_categorie_ignoree_explicitement(self):
        self.assertEqual(imp.besoins_de(["remobilisation--lien-social"], []), set())

    def test_categorie_inconnue(self):
        with self.assertRaisesRegex(ValueError, "inconnue"):
            imp.besoins_de(["nouvelle-categorie--x"], [])

    def test_besoins_valides(self):
        self.assertTrue({b for b in imp.CATEGORIES_DI.values() if b} <= set(imp.BESOINS))
        self.assertTrue(set(imp.SOUS_THEMATIQUES_DI.values()) <= set(imp.BESOINS))


class Fraicheur(unittest.TestCase):
    def test_etats(self):
        self.assertEqual(imp.fraicheur("2026-09-01", AUJ), "recent")
        self.assertEqual(imp.fraicheur("2026-01-15", AUJ), "a_verifier")
        self.assertEqual(imp.fraicheur("2024-05-01", AUJ), "ancien")
        self.assertEqual(imp.fraicheur("", AUJ), "inconnue")


class Structures(unittest.TestCase):
    def test_assemblage_et_fusion_par_siret(self):
        S, err, _ = imp.construire(
            [structure("a", siret="111"), structure("b", siret="111", source="finess"), structure("c", insee="75056")],
            [service("s1", "a"), service("s2", "b")], [], AUJ)
        self.assertEqual(err, [])
        self.assertEqual(list(S), ["111"])  # hors 05 exclu, même SIRET fusionné
        self.assertEqual(len(S["111"]["services"]), 2)
        self.assertEqual(S["111"]["sources"], ["dora", "finess"])
        self.assertEqual(S["111"]["fraicheur"], "recent")

    def test_un_siret_plusieurs_lieux(self):
        mds = [dict(structure(f"m{i}", nom=f"Maison des Solidarités {v}", siret="220"), adresse=f"{i} rue {v}")
               for i, v in enumerate(["Laragne", "Veynes"])]
        meme_nom = dict(structure("m9", nom="Maison des Solidarités Veynes", siret="220", source="finess"), adresse="1, Rue Veynes bis")
        S, err, _ = imp.construire(mds + [meme_nom], [], [], AUJ)
        self.assertEqual(len(S), 2)  # deux lieux ; la 3e ligne (même nom) rejoint Veynes
        self.assertTrue(all(k.startswith("220-") for k in S))
        ids = imp.identifiants(mds + [meme_nom])
        self.assertEqual(ids, imp.identifiants(list(reversed(mds + [meme_nom]))))  # stable, quel que soit l'ordre

    def test_sans_nom(self):
        _, err, _ = imp.construire([structure("a", nom=" ")], [], [], AUJ)
        self.assertIn("sans nom", err[0])

    def test_coordonnees_aberrantes(self):
        S, err, avert = imp.construire([structure("a", lat="46.03", lon="3.58")], [], [], AUJ)
        self.assertEqual(err, [])
        self.assertIsNone(S["a"]["lat"])
        self.assertEqual(S["a"]["bassin"], imp.NON_LOCALISE)
        self.assertIn("hors des Hautes-Alpes", avert[0])

    def test_service_categorie_inconnue(self):
        _, err, _ = imp.construire([structure("a")], [service("s1", "a", "['inconnue--x']")], [], AUJ)
        self.assertIn("inconnue", err[0])

    def test_doublons_probables(self):
        _, _, avert = imp.construire([structure("a", nom="CCAS de Gap"), structure("b", nom="CCAS DE GAP")], [], [], AUJ)
        self.assertTrue(any("doublon probable" in a for a in avert))

    def test_association_besoin_inconnu(self):
        asso = {"retenir": "oui", "rna": "W1", "siret": "", "nom": "Asso nouvelle", "commune": "Gap", "lat": "44.56",
                "lon": "6.08", "besoins": "logement inexistant", "tel": "", "mail": "", "web": "", "objet": "", "maj": ""}
        _, err, _ = imp.construire([], [], [asso], AUJ)
        self.assertIn("inexistant", err[0])
        asso["besoins"] = "logement"
        S, err, _ = imp.construire([], [], [asso], AUJ)
        self.assertEqual((err, S["W1"]["besoins"], S["W1"]["fraicheur"]), ([], ["logement"], "inconnue"))


class Partenariats(unittest.TestCase):
    ids = {"a", "b", "c"}

    def ligne(self, de="a", vers="b", statut="valide", besoin="logement"):
        return {"de": de, "vers": vers, "besoin": besoin, "statut": statut, "date": "2026-10-01"}

    def test_seuls_les_valides_sont_publies(self):
        pub, err = imp.partenariats([self.ligne(), self.ligne("a", "c", "en_attente")], self.ids)
        self.assertEqual((len(pub), err), (1, []))

    def test_erreurs(self):
        cas = {"inconnue": self.ligne(vers="z"), "elle-même": self.ligne(vers="a"),
               "statut": self.ligne(statut="ok"), "besoin": self.ligne(besoin="cuisine")}
        for attendu, ligne in cas.items():
            _, err = imp.partenariats([ligne], self.ids)
            self.assertTrue(err and attendu in err[0], (attendu, err))

    def test_doublon(self):
        _, err = imp.partenariats([self.ligne(), self.ligne()], self.ids)
        self.assertIn("doublon", err[0])


class LiensInstitutionnels(unittest.TestCase):
    S = [{"id": "ft-gap", "nom": "Agence France Travail Gap", "reseaux": ["france-travail"], "lat": 44.56, "lon": 6.08},
         {"id": "ft-bri", "nom": "Agence France Travail Briançon", "reseaux": ["france-travail"], "lat": 44.90, "lon": 6.64},
         {"id": "ft-dt", "nom": "France Travail DT 05", "reseaux": ["france-travail"], "lat": 44.55, "lon": 5.80},
         {"id": "aci-laragne", "nom": "Chantier Laragne", "reseaux": ["aci"], "lat": 44.32, "lon": 5.82},
         {"id": "aci-bri", "nom": "Chantier Briançon", "reseaux": ["aci"], "lat": 44.89, "lon": 6.63},
         {"id": "ml", "nom": "Mission locale", "reseaux": ["mission-locale"], "lat": 44.56, "lon": 6.08}]

    def regle(self, de="france-travail", perimetre="plus_proche", besoin="emploi", exclure=r"\bDT\b"):
        return {"de_reseau": de, "vers_reseau": "aci", "perimetre": perimetre, "besoin": besoin, "motif": "IAE", "exclure": exclure}

    def test_plus_proche_et_exclusion(self):
        liens, err, _ = imp.liens_institutionnels(self.S, [self.regle()])
        # La DT (plus proche de Laragne) est exclue : Laragne dépend de l'agence de Gap.
        self.assertEqual((err, {(l["de"], l["vers"]) for l in liens}), ([], {("ft-gap", "aci-laragne"), ("ft-bri", "aci-bri")}))

    def test_departement_et_doublons(self):
        liens, _, _ = imp.liens_institutionnels(self.S, [self.regle("mission-locale", "departement")] * 2)
        self.assertEqual(len(liens), 2)

    def test_erreurs_et_regle_sans_effet(self):
        _, err, _ = imp.liens_institutionnels(self.S, [self.regle(perimetre="region"), self.regle(besoin="cuisine")])
        self.assertEqual(len(err), 2)
        _, err, avert = imp.liens_institutionnels(self.S, [self.regle(de="spip")])
        self.assertEqual(err, [])
        self.assertIn("sans effet", avert[0])


class Regression(unittest.TestCase):
    def stats(self, n=100, services=200, gap=50):
        return {"structures": n, "services": services, "geolocalisees": n, "partenariats": 0,
                "bassin": {"Gap": gap, "Queyras": 2}, "besoin": {"logement": 40}, "fraicheur": {}}

    def test_stable(self):
        self.assertEqual(imp.anomalies(self.stats(), self.stats(n=95)), [])

    def test_chute_des_structures(self):
        a = imp.anomalies(self.stats(), self.stats(n=60))
        self.assertTrue(any(x.startswith("structures") for x in a))

    def test_bassin_disparu(self):
        a = imp.anomalies(self.stats(), self.stats(gap=0))
        self.assertTrue(any("Gap" in x for x in a))

    def test_petit_bassin_non_controle(self):
        apres = self.stats()
        apres["bassin"] = {"Gap": 50}  # Queyras (2) disparaît : sous EFFECTIF_MIN
        self.assertEqual(imp.anomalies(self.stats(), apres), [])

    def test_vide(self):
        self.assertIn("aucune structure", imp.anomalies(self.stats(), self.stats(n=0))[0])

    def test_controle_ignore(self):
        self.assertEqual(imp.anomalies(self.stats(), self.stats(n=60, services=200), ignorer={"structures", "geolocalisees"}), [])

    def test_statistiques(self):
        data = {"structures": [{"lat": 44.5, "bassin": "Gap", "besoins": ["sante"], "services": [{}, {}], "fraicheur": "recent"},
                               {"lat": None, "bassin": "Non localisé", "besoins": [], "services": [], "fraicheur": "ancien"}],
                "partenariats": []}
        s = imp.statistiques(data)
        self.assertEqual((s["structures"], s["services"], s["geolocalisees"], s["besoin"]), (2, 2, 1, {"sante": 1}))


if __name__ == "__main__":
    unittest.main()
