"""Client minimal pour l'API REST WordPress (stdlib uniquement)."""

import base64
import json
import os
import urllib.error
import urllib.parse
import urllib.request


class WPError(Exception):
    """Erreur renvoyée par l'API WordPress."""

    def __init__(self, status, code, message):
        super().__init__(f"HTTP {status} [{code}] {message}")
        self.status = status
        self.code = code


class WPClient:
    def __init__(self, url, user, app_password, timeout=30):
        self.base = url.rstrip("/") + "/wp-json"
        self.timeout = timeout
        token = f"{user}:{app_password.replace(' ', '')}".encode()
        self.auth = "Basic " + base64.b64encode(token).decode()

    @classmethod
    def from_env(cls):
        missing = [k for k in ("WP_URL", "WP_USER", "WP_APP_PASSWORD") if not os.environ.get(k)]
        if missing:
            raise SystemExit(
                "Variables manquantes : " + ", ".join(missing) + "\n"
                "Renseigne-les dans .env (voir .env.example) puis relance."
            )
        return cls(os.environ["WP_URL"], os.environ["WP_USER"], os.environ["WP_APP_PASSWORD"])

    def request(self, method, path, data=None, params=None):
        url = self.base + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        body = json.dumps(data).encode() if data is not None else None
        req = urllib.request.Request(url, data=body, method=method)
        req.add_header("Authorization", self.auth)
        req.add_header("Content-Type", "application/json")
        req.add_header("Accept", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read()
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            try:
                payload = json.loads(raw)
            except ValueError:
                payload = {}
            raise WPError(exc.code, payload.get("code", "unknown"), payload.get("message", raw[:200]))
        return json.loads(raw) if raw else None

    # --- helpers ---------------------------------------------------------

    def me(self):
        return self.request("GET", "/wp/v2/users/me", params={"context": "edit"})

    def settings(self, values=None):
        if values:
            return self.request("POST", "/wp/v2/settings", data=values)
        return self.request("GET", "/wp/v2/settings")

    def find_page(self, slug):
        found = self.request("GET", "/wp/v2/pages", params={"slug": slug, "status": "any", "context": "edit"})
        return found[0] if found else None

    def upsert_page(self, slug, payload):
        existing = self.find_page(slug)
        data = dict(payload, slug=slug)
        if existing:
            return self.request("POST", f"/wp/v2/pages/{existing['id']}", data=data), "mis à jour"
        return self.request("POST", "/wp/v2/pages", data=data), "créé"

    def find_menu(self, name):
        for menu in self.request("GET", "/wp/v2/menus", params={"context": "edit", "per_page": 100}) or []:
            if menu["name"] == name:
                return menu
        return None

    def upsert_menu(self, name, locations):
        existing = self.find_menu(name)
        data = {"name": name, "locations": locations}
        if existing:
            return self.request("POST", f"/wp/v2/menus/{existing['id']}", data=data)
        return self.request("POST", "/wp/v2/menus", data=data)

    def menu_items(self, menu_id):
        return self.request(
            "GET", "/wp/v2/menu-items",
            params={"menus": menu_id, "per_page": 100, "context": "edit"},
        ) or []

    def delete_menu_item(self, item_id):
        self.request("DELETE", f"/wp/v2/menu-items/{item_id}", params={"force": "true"})

    def create_menu_item(self, menu_id, title, page_id, order):
        return self.request("POST", "/wp/v2/menu-items", data={
            "title": title,
            "menus": menu_id,
            "object": "page",
            "object_id": page_id,
            "type": "post_type",
            "status": "publish",
            "menu_order": order,
        })
