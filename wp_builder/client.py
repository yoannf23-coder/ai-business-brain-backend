"""Client minimal pour l'API REST WordPress (stdlib uniquement).

Deux modes d'authentification :

- mot de passe d'application (recommandé) : en-tête Basic Auth ;
- identifiant + mot de passe normal : connexion via wp-login.php, puis cookies
  et nonce REST — la même mécanique que le navigateur quand tu es connecté à
  l'admin. Nécessaire car WordPress refuse le mot de passe de connexion en
  Basic Auth.
"""

import base64
import http.cookiejar
import json
import os
import re
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
    def __init__(self, url, timeout=30):
        self.site = url.rstrip("/")
        self.base = self.site + "/wp-json"
        self.timeout = timeout
        self.headers = {}
        self.cookies = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cookies)
        )

    # --- construction ----------------------------------------------------

    @classmethod
    def from_env(cls):
        url = os.environ.get("WP_URL")
        user = os.environ.get("WP_USER")
        app_pw = os.environ.get("WP_APP_PASSWORD")
        password = os.environ.get("WP_PASSWORD")
        if not url or not user or not (app_pw or password):
            raise SystemExit(
                "Variables manquantes.\n"
                "Il faut WP_URL, WP_USER, et soit WP_APP_PASSWORD (recommandé), "
                "soit WP_PASSWORD.\nVoir .env.example."
            )
        client = cls(url)
        if app_pw:
            client.use_app_password(user, app_pw)
        else:
            client.login(user, password)
        return client

    def use_app_password(self, user, app_password):
        token = f"{user}:{app_password.replace(' ', '')}".encode()
        self.headers["Authorization"] = "Basic " + base64.b64encode(token).decode()
        self.auth_mode = "mot de passe d'application"

    def login(self, user, password):
        """Se connecte via wp-login.php et récupère le nonce de l'API REST."""
        self.cookies.set_cookie(http.cookiejar.Cookie(
            0, "wordpress_test_cookie", "WP+Cookie+check", None, False,
            urllib.parse.urlparse(self.site).hostname, False, False,
            "/", False, False, None, True, None, None, {},
        ))
        form = urllib.parse.urlencode({
            "log": user,
            "pwd": password,
            "rememberme": "forever",
            "wp-submit": "Log In",
            "redirect_to": self.site + "/wp-admin/",
            "testcookie": "1",
        }).encode()
        req = urllib.request.Request(self.site + "/wp-login.php", data=form, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        req.add_header("User-Agent", "wp-builder")
        try:
            self.opener.open(req, timeout=self.timeout).read()
        except urllib.error.HTTPError as exc:
            raise WPError(exc.code, "login_failed", "wp-login.php a refusé la requête")

        if not any(c.name.startswith("wordpress_logged_in_") for c in self.cookies):
            raise WPError(401, "login_failed",
                          "Identifiant ou mot de passe refusé par wp-login.php")

        nonce_req = urllib.request.Request(
            self.site + "/wp-admin/admin-ajax.php?action=rest-nonce")
        nonce_req.add_header("User-Agent", "wp-builder")
        nonce = self.opener.open(nonce_req, timeout=self.timeout).read().decode().strip()
        if not re.fullmatch(r"[a-zA-Z0-9]{8,20}", nonce):
            raise WPError(401, "nonce_failed", "Nonce REST introuvable après connexion")
        self.headers["X-WP-Nonce"] = nonce
        self.auth_mode = "connexion par cookie"

    # --- transport -------------------------------------------------------

    def request(self, method, path, data=None, params=None):
        url = self.base + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        body = json.dumps(data).encode() if data is not None else None
        req = urllib.request.Request(url, data=body, method=method)
        for key, value in self.headers.items():
            req.add_header(key, value)
        req.add_header("Content-Type", "application/json")
        req.add_header("Accept", "application/json")
        req.add_header("User-Agent", "wp-builder")
        try:
            with self.opener.open(req, timeout=self.timeout) as resp:
                raw = resp.read()
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            try:
                payload = json.loads(raw)
            except ValueError:
                payload = {}
            raise WPError(exc.code, payload.get("code", "unknown"),
                          payload.get("message", raw[:200]))
        return json.loads(raw) if raw else None

    # --- helpers ---------------------------------------------------------

    def me(self):
        return self.request("GET", "/wp/v2/users/me", params={"context": "edit"})

    def settings(self, values=None):
        if values:
            return self.request("POST", "/wp/v2/settings", data=values)
        return self.request("GET", "/wp/v2/settings")

    def find_page(self, slug):
        found = self.request("GET", "/wp/v2/pages",
                             params={"slug": slug, "status": "any", "context": "edit"})
        return found[0] if found else None

    def upsert_page(self, slug, payload):
        existing = self.find_page(slug)
        data = dict(payload, slug=slug)
        if existing:
            return self.request("POST", f"/wp/v2/pages/{existing['id']}", data=data), "mis à jour"
        return self.request("POST", "/wp/v2/pages", data=data), "créé"

    def find_menu(self, name):
        menus = self.request("GET", "/wp/v2/menus",
                             params={"context": "edit", "per_page": 100}) or []
        for menu in menus:
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
