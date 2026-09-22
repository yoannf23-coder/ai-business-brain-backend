# WP Builder — site vitrine WordPress via l'API REST

Outil en Python (sans dépendance externe) qui crée et met à jour un site vitrine
WordPress à partir d'un seul fichier de configuration : `site.config.json`.

Il pilote un WordPress **déjà installé et accessible en ligne**, via l'API REST
(`/wp-json`). Rien n'est installé sur le serveur.

## Ce qu'il fait

- crée ou met à jour les **pages** (contenu en blocs Gutenberg natifs, éditables ensuite dans l'admin) ;
- construit le **menu principal** et le rattache à l'emplacement du thème ;
- règle le **titre du site**, le **slogan** et la **page d'accueil statique**.

Le script est **idempotent** : relancé, il met à jour les pages existantes (repérées
par leur `slug`) au lieu d'en créer des doublons.

## Démarrage rapide (depuis ton PC)

Il faut Python 3.8+ (`python3 --version` pour vérifier ; sous Windows, `py --version`).

```bash
git clone https://github.com/yoannf23-coder/ai-business-brain-backend.git
cd ai-business-brain-backend
cp .env.example .env      # Windows : copy .env.example .env
```

Ouvre `.env` et remplis-le, puis :

```bash
python3 build_site.py check    # doit afficher "Connecté : ..."
```

## Authentification

Deux méthodes, au choix dans `.env`.

### Mot de passe d'application (recommandé)

Admin WordPress → **Utilisateurs → Profil → Mots de passe d'application**.
Donner un nom (ex. `wp-builder`), cliquer sur « Ajouter », copier la clé dans
`WP_APP_PASSWORD`. À supprimer depuis cette même page une fois le travail fini.

La section n'apparaît que si le site est en **HTTPS** : WordPress la masque sinon.

### Mot de passe de connexion normal

Si les mots de passe d'application ne sont pas disponibles, remplir `WP_PASSWORD`
et laisser `WP_APP_PASSWORD` vide. Le script se connecte alors via
`wp-login.php`, garde les cookies de session et récupère le nonce REST
(`admin-ajax.php?action=rest-nonce`) — exactement la mécanique du navigateur.
WordPress refuse le mot de passe de connexion en Basic Auth, d'où ce détour.

### Dans les deux cas

- Utiliser un compte **administrateur** : les menus et les réglages l'exigent.
- `.env` est ignoré par git ; les identifiants ne sont jamais committés.

## Utilisation

```bash
python3 build_site.py check       # vérifie la connexion et les droits du compte
python3 build_site.py preview     # affiche le HTML généré, sans rien envoyer
python3 build_site.py apply --dry-run   # liste ce qui serait fait
python3 build_site.py apply       # applique réellement sur le site
```

Faire un **export/sauvegarde du site avant le premier `apply`** : les pages portant
un slug listé dans la config sont écrasées.

## Configurer le site

Tout se passe dans `site.config.json`.

```json
{
  "site": {
    "title": "Nom de l'entreprise",
    "description": "Slogan",
    "front_page_slug": "accueil",
    "posts_page_slug": null
  },
  "menu": { "name": "Menu principal", "location": "primary", "items": ["accueil", "contact"] },
  "pages": [ { "slug": "accueil", "title": "Accueil", "sections": [ ... ] } ]
}
```

`location` doit correspondre à un emplacement déclaré par le thème (souvent
`primary`, parfois `menu-1` ou `header`). En cas de mauvais nom, le menu est créé
mais non affiché : il suffit de l'assigner dans **Apparence → Menus**.

### Types de sections disponibles

| `type`     | Champs                                             | Rendu |
|------------|----------------------------------------------------|-------|
| `hero`     | `title`, `subtitle`, `button {label, url}`         | bandeau pleine largeur centré |
| `text`     | `title`, `paragraphs[]`                            | titre + paragraphes |
| `features` | `title`, `items[] {title, text}`                   | colonnes côte à côte |
| `cta`      | `title`, `text`, `button {label, url}`             | appel à l'action centré |
| `contact`  | `title`, `email`, `phone`, `address`, `note`       | coordonnées en liste |

Ajouter un type se fait dans `wp_builder/blocks.py` : une fonction qui reçoit la
section et renvoie du balisage Gutenberg, puis une entrée dans `RENDERERS`.

## Structure

```
build_site.py           CLI (check / preview / apply)
site.config.json        contenu et structure du site
wp_builder/client.py    client API REST WordPress (auth, pages, menus, réglages)
wp_builder/blocks.py    génération du balisage Gutenberg
```

## Limites connues

- Le **formulaire de contact** n'est pas créé : il demande une extension
  (Contact Form 7, Fluent Forms…). Une fois l'extension installée, coller son
  shortcode dans une section `text`.
- Les **images** ne sont pas envoyées : à ajouter dans la médiathèque puis à
  insérer dans les pages.
- Le **thème** n'est pas modifié. Le rendu visuel dépend du thème actif ; les blocs
  générés sont standards et s'adaptent à n'importe quel thème récent.
