# Solidarités 05 — qui fait quoi ?

Cartographie des acteurs de la solidarité des Hautes-Alpes : un mode « J'ai besoin d'aide » pour le public et un nuage relationnel pour les professionnels.

Site : https://solidarites-05.cartographie-05.workers.dev

## Architecture

Site statique, sans serveur ni base de données :

```
import_05.py          data·inclusion (+ associations retenues) -> contrôles -> site/data.js
associations_rna.py   liste des associations du RNA à trier à la main (associations.csv)
partenariats.csv      partenariats déclarés entre structures
site/
  index.html          la page
  data.js             GÉNÉRÉ par import_05.py, ne jamais modifier à la main
  css/style.css
  js/config.js        paramètres (contact, pondérations du classement, libellés)
  js/utils.js         fonctions pures (classement, liens, formats), testées
  js/public.js        mode « J'ai besoin d'aide » (ne dépend pas de D3)
  js/pro.js           mode professionnel : nuage D3, vue liste, fiche, réseau, chemin
tests/                tests Python (import) et JavaScript (utils)
```

Dépendance externe unique : **D3 7.8.5**, chargé depuis cdnjs avec une version figée et un contrôle d'intégrité (`integrity="sha512-…"`). Seul le graphique du mode pro l'utilise ; si D3 ne se charge pas, la vue liste prend le relais.

## Données

- **Source** : [data·inclusion](https://www.data.gouv.fr/datasets/referentiel-de-loffre-dinsertion-sociale-et-professionnelle-data-inclusion) (Licence Ouverte 2.0), structures dont le code INSEE commence par 05. Les structures de même SIRET présentes dans plusieurs sources sont fusionnées.
- **Associations** : `python associations_rna.py` ajoute à `associations.csv` les associations du RNA liées à la solidarité. L'équipe met `oui` dans la colonne `retenir` ; seules celles-là sont publiées.
- **Besoins** : liste centrale `BESOINS` dans `import_05.py`. Chaque catégorie data·inclusion est rattachée explicitement à un besoin (ou ignorée volontairement) dans `CATEGORIES_DI`. Une catégorie inconnue fait échouer l'import : rien n'est perdu sans qu'on le sache.
- **Bassins** : chaque structure est rattachée au centre de bassin le plus proche (`BASSINS`). C'est une approximation, à remplacer par une table officielle commune INSEE → bassin quand elle sera validée. Des coordonnées hors des Hautes-Alpes sont jugées aberrantes : la structure est gardée, sans position.
- **Fraîcheur** : `recent` (< 6 mois), `a_verifier` (6 à 12 mois), `ancien` (> 12 mois), `inconnue` (pas de date dans la source, aucune date n'est inventée).
- **Partenariats** (`partenariats.csv`) : colonnes `de`, `vers` (SIRET ou identifiant de la structure), `besoin` (facultatif, un des besoins), `statut` (`valide`, `en_attente`, `refuse`), `date`. Seuls les `valide` sont publiés. Structure inconnue, auto-partenariat, doublon ou statut inconnu font échouer l'import. Ne jamais y mettre de coordonnées personnelles : le dépôt est public.

Deux sortes de liens, à ne pas confondre : la **proximité thématique** (calculée : même bassin, un besoin en commun, publics compatibles) et le **partenariat** (déclaré et validé).

## Contrôles avant publication

`import_05.py` n'écrit `site/data.js` que si tout est bon. Il échoue (et ne touche à rien) en cas :

- d'erreur de validation (structure sans identifiant ou sans nom, service sans nom, catégorie ou besoin inconnu, partenariat invalide) ;
- de baisse anormale par rapport aux données déjà publiées (structures, services, structures géolocalisées, partenariats, un bassin, un besoin) ou de données vides.

Les doublons probables et les coordonnées aberrantes sont signalés en avertissement, sans bloquer.

**Une baisse est normale ?** Relancer en ignorant le contrôle concerné :
- sur GitHub : Actions → « Mise à jour mensuelle » → Run workflow → champ « Contrôles de baisse à ignorer » (`structures,services`, ou `tout`) ;
- en local : `IGNORER_CONTROLES=structures python import_05.py` (PowerShell : `$env:IGNORER_CONTROLES="structures"; python import_05.py`).

## Lancer en local

```
python import_05.py                 # télécharge data·inclusion et régénère site/data.js
cd site && python -m http.server 8000   # puis ouvrir http://localhost:8000
```

## Tests

```
python -m unittest discover -s tests -v
node tests/test_utils.js
```

Aucune dépendance à installer (bibliothèque standard Python, Node pour les tests JavaScript).

## Automatisation et déploiement

- **GitHub Actions** (`.github/workflows/mise-a-jour.yml`) : le 1er de chaque mois (ou à la main) : tests, import et contrôles, puis commit de `site/data.js` seulement s'il a changé. Si un contrôle échoue, le workflow est rouge et rien n'est commité ; le détail est dans le résumé de l'exécution. Les tests tournent aussi à chaque modification du code.
- **Cloudflare Workers (assets statiques)** : relié au dépôt, il republie le dossier `site/` à chaque commit sur `main` (configuration : `wrangler.jsonc`). Publication manuelle possible : `npx wrangler deploy`.

## Modifier les paramètres

| Quoi | Où |
| --- | --- |
| Contact de l'animateur du réseau (boutons « Proposer une modification », « Signaler », « Proposer un partenariat ») | `site/js/config.js` → `CONTACT_ANIMATEUR` (vide = boutons masqués) |
| Pondérations du classement « J'ai besoin d'aide » | `site/js/config.js` → `SCORE` |
| Nombre de résultats affichés | `site/js/config.js` → `NB_RESULTATS` |
| Seuils de baisse tolérée | `import_05.py` → `SEUILS`, `EFFECTIF_MIN` |
| Bassins de vie | `import_05.py` → `BASSINS` |
| Rattachement des catégories data·inclusion aux besoins | `import_05.py` → `CATEGORIES_DI`, `SOUS_THEMATIQUES_DI`, `PUBLICS_BESOIN` |
| Seuils de fraîcheur | `import_05.py` → `FRAICHEUR_JOURS` |
| Emprise géographique (coordonnées aberrantes) | `import_05.py` → `EMPRISE_05` |
| Libellés et pictos des besoins, types, publics | `site/js/config.js` |

Le classement du mode public est déterministe : il additionne des points (services adaptés, public, distance, bassin, informations pratiques, fraîcheur). Il sert seulement à ordonner les résultats, ce n'est pas une note de qualité.

## Évolutions prévues (V2)

Les propositions des professionnels passent toutes par une seule fonction, `lienContribution()` dans `site/js/pro.js` (aujourd'hui un courriel prérempli). Elle pourra être remplacée par un formulaire avec modération sans toucher au reste de l'interface.

Code sous licence MIT. Données : Licence Ouverte 2.0 (data·inclusion, RNA).
