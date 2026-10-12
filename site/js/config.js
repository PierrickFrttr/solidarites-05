// Paramètres du site. Voir README, section « Modifier les paramètres ».
var CONFIG = {
  // Adresse de l'animateur du réseau : elle reçoit les propositions de modification, les signalements et les
  // partenariats. Tant qu'elle est vide, les boutons de contribution sont masqués (aucune fausse adresse).
  CONTACT_ANIMATEUR: "pierrick.frottier.pro@gmail.com",

  // Ordre des résultats du mode « J'ai besoin d'aide » : points ajoutés pour chaque critère.
  // Le score sert seulement à trier ; il n'est jamais affiché comme une note.
  SCORE: {
    parService: 5, maxServices: 3,           // chaque service qui répond au besoin (plafonné)
    publicExact: 30, publicTous: 15,         // public choisi dans « Pour qui ? », ou structure ouverte à tous
    proximiteMax: 40, proximiteKm: 50,       // 40 points sur place, 0 à 50 km et au-delà
    memeBassin: 10,                          // même bassin de vie que la personne
    telephone: 15, adresse: 5, horaires: 5, site: 3,
    fraicheur: { recent: 10, a_verifier: 5, ancien: 0, inconnue: 0 },
  },
  NB_RESULTATS: 8,
};

var BESOINS = {
  logement: ["🏠", "Me loger"], alimentation: ["🍞", "Manger, m'équiper"], sante: ["🩺", "Me soigner"],
  emploi: ["💼", "Trouver un travail"], argent: ["💶", "Gérer mon argent"], droits: ["📄", "Mes papiers, mes droits"],
  famille: ["👨‍👩‍👧", "Ma famille, mes enfants"], handicap: ["♿", "Handicap"], mobilite: ["🚗", "Me déplacer"],
  numerique: ["💻", "Internet, ordinateur"], francais: ["🗣️", "Lire, écrire, parler français"], violences: ["🛑", "Violences"],
};
var TYPES = {
  "mediation-numerique": "Lieu de médiation numérique", "ma-boussole-aidants": "Aide aux aidants",
  "emplois-de-linclusion": "Insertion par l'activité économique", dora: "Service d'insertion (DORA)",
  monenfant: "Accueil petite enfance", finess: "Établissement sanitaire et social", "carif-oref": "Organisme de formation",
  "france-travail": "France Travail", rna: "Association (RNA)", "mes-aides": "Aides mobilité", "action-logement": "Action Logement",
};
var PUBLICS = {
  "tous-publics": "Tout public", "demandeurs-emploi": "Demandeurs d'emploi", actifs: "Actifs", familles: "Familles",
  "personnes-en-situation-de-handicap": "Personnes handicapées", "personnes-exilees": "Personnes exilées",
  "beneficiaires-des-minimas-sociaux": "Bénéficiaires des minima sociaux", seniors: "Seniors", jeunes: "Jeunes",
  etudiants: "Étudiants", "personnes-en-situation-durgence": "Personnes en situation d'urgence", femmes: "Femmes",
};
var FRAIS = { gratuit: "Gratuit", payant: "Payant", "gratuit-sous-conditions": "Gratuit sous conditions", adhesion: "Adhésion" };
var FRAICHEUR = {
  recent: "Fiche mise à jour récemment", a_verifier: "Fiche à vérifier (6 à 12 mois)",
  ancien: "Fiche ancienne (plus de 12 mois)", inconnue: "Date de mise à jour non communiquée",
};
