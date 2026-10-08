# Solidarités 05 — qui fait quoi ?

Cartographie des acteurs de la solidarité des Hautes-Alpes : un mode « J'ai besoin d'aide » pour le public et un nuage relationnel pour les professionnels.

Site : https://solidarites-05.cartographie-05.workers.dev

- `import_05.py` : récupère les structures du 05 dans [data·inclusion](https://www.data.gouv.fr/datasets/referentiel-de-loffre-dinsertion-sociale-et-professionnelle-data-inclusion) et produit `site/data.js`. Lancé chaque mois par GitHub Actions.
- `partenariats.csv` : partenariats déclarés entre structures (colonnes `de`, `vers` = SIRET ou identifiant data·inclusion). Seules les lignes `statut=valide` sont publiées.
- `site/` : le site statique, publié par Cloudflare à chaque modification.

Code sous licence MIT. Données : Licence Ouverte 2.0 (data·inclusion).
