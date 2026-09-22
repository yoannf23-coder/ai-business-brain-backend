#!/usr/bin/env python3
"""Construit un site vitrine WordPress via l'API REST, à partir de site.config.json.

Usage :
    python3 build_site.py check              # vérifie la connexion et les droits
    python3 build_site.py preview            # affiche le HTML généré, sans rien envoyer
    python3 build_site.py apply              # crée/met à jour pages, menu et réglages
    python3 build_site.py apply --dry-run    # montre ce qui serait fait

Identifiants lus depuis .env ou l'environnement : WP_URL, WP_USER, et
WP_APP_PASSWORD (recommandé) ou WP_PASSWORD.
Le script est idempotent : relancé, il met à jour au lieu de dupliquer.
"""

import argparse
import json
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from wp_builder import blocks
from wp_builder.client import WPClient, WPError

ROOT = pathlib.Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "site.config.json"


def load_env():
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def load_config(path):
    return json.loads(pathlib.Path(path).read_text())


def cmd_check(_args, config):
    client = WPClient.from_env()
    user = client.me()
    caps = user.get("capabilities", {})
    print(f"Connecté : {user['name']} (id {user['id']}) sur {client.base}")
    print(f"Méthode : {client.auth_mode}")
    for cap, label in (
        ("edit_pages", "créer/modifier des pages"),
        ("manage_options", "modifier les réglages du site"),
        ("edit_theme_options", "gérer les menus"),
    ):
        print(f"  [{'x' if caps.get(cap) else ' '}] {label}")
    if not caps.get("edit_pages"):
        print("\nCe compte ne peut pas éditer les pages : utilise un compte administrateur.")
        return 1
    print(f"\nConfig chargée : {len(config['pages'])} pages à publier.")
    return 0


def cmd_preview(_args, config):
    for page in config["pages"]:
        print(f"\n{'=' * 60}\n{page['title']}  (/{page['slug']})\n{'=' * 60}")
        print(blocks.render(page["sections"]))
    return 0


def apply_pages(client, config, dry_run):
    ids = {}
    for page in config["pages"]:
        content = blocks.render(page["sections"])
        if dry_run:
            print(f"  [dry-run] page '{page['slug']}' ({len(content)} caractères)")
            ids[page["slug"]] = None
            continue
        result, action = client.upsert_page(page["slug"], {
            "title": page["title"],
            "content": content,
            "status": page.get("status", "publish"),
        })
        ids[page["slug"]] = result["id"]
        print(f"  page '{page['slug']}' {action} → {result['link']}")
    return ids


def apply_menu(client, config, page_ids, dry_run):
    menu_cfg = config.get("menu")
    if not menu_cfg:
        return
    wanted = [s for s in menu_cfg["items"] if s in page_ids]
    if dry_run:
        print(f"  [dry-run] menu '{menu_cfg['name']}' : {', '.join(wanted)}")
        return
    try:
        menu = client.upsert_menu(menu_cfg["name"], [menu_cfg.get("location", "primary")])
    except WPError as exc:
        print(f"  menu non configuré ({exc}) — à faire dans Apparence > Menus.")
        return
    for item in client.menu_items(menu["id"]):
        client.delete_menu_item(item["id"])
    for order, slug in enumerate(wanted, start=1):
        title = next(p["title"] for p in config["pages"] if p["slug"] == slug)
        client.create_menu_item(menu["id"], title, page_ids[slug], order)
    print(f"  menu '{menu_cfg['name']}' : {len(wanted)} entrées")


def apply_settings(client, config, page_ids, dry_run):
    site = config.get("site", {})
    values = {}
    if site.get("title"):
        values["title"] = site["title"]
    if site.get("description"):
        values["description"] = site["description"]
    front = site.get("front_page_slug")
    if front and page_ids.get(front):
        values["show_on_front"] = "page"
        values["page_on_front"] = page_ids[front]
    posts = site.get("posts_page_slug")
    if posts and page_ids.get(posts):
        values["page_for_posts"] = page_ids[posts]
    if not values:
        return
    if dry_run:
        print(f"  [dry-run] réglages : {values}")
        return
    try:
        client.settings(values)
        print(f"  réglages mis à jour : {', '.join(values)}")
    except WPError as exc:
        print(f"  réglages non modifiés ({exc}) — droits administrateur requis.")


def cmd_apply(args, config):
    client = WPClient.from_env()
    print(f"Cible : {client.base}")
    page_ids = apply_pages(client, config, args.dry_run)
    apply_menu(client, config, page_ids, args.dry_run)
    apply_settings(client, config, page_ids, args.dry_run)
    print("\nTerminé." if not args.dry_run else "\nAucune modification envoyée (dry-run).")
    return 0


COMMANDS = {"check": cmd_check, "preview": cmd_preview, "apply": cmd_apply}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=COMMANDS)
    parser.add_argument("--config", default=str(CONFIG_PATH), help="chemin du fichier de config")
    parser.add_argument("--dry-run", action="store_true", help="n'envoie rien, affiche les actions")
    args = parser.parse_args()

    load_env()
    config = load_config(args.config)
    try:
        return COMMANDS[args.command](args, config)
    except BrokenPipeError:
        return 0
    except WPError as exc:
        print(f"Erreur WordPress : {exc}", file=sys.stderr)
        if exc.status in (401, 403):
            print("Vérifie WP_USER et le mot de passe dans .env.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
