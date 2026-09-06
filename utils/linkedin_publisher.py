"""
utils/linkedin_publisher.py
----------------------------
Thin wrapper around LinkedIn's REST API for:
  1. Getting the authenticated member's profile (OpenID Connect userinfo)
  2. Publishing a text post on their behalf
  3. Fetching recent posts authored by the SAME authenticated identity

IMPORTANT - READ THIS BEFORE WIRING UP "COMPETITOR SCRAPING":
LinkedIn's public API does NOT let you fetch posts from an arbitrary
third-party profile/company you don't manage. That capability requires
LinkedIn's Marketing Developer Platform partnership (a manual, restricted
approval process aimed at large ad-tech/analytics vendors), not a normal
OAuth app. Any tutorial that shows `get_recent_posts(competitor_url)`
pulling a stranger's posts is either:
  - using an unofficial/scraping approach that violates LinkedIn's ToS
    and can get the account or IP banned, or
  - simplifying away the fact that you can only fetch content for
    profiles/organizations *you* administer.

What actually works with a standard "Sign In with LinkedIn" + "Share on
LinkedIn" app (what most solo devs/agencies can get approved for):
  - Publish a post as the logged-in member.
  - Read that member's own profile info.
  - Read posts/analytics for a LinkedIn Company Page you are an admin of
    (needs the "Community Management API" product + org access, also an
    approval step, but far more attainable than full Marketing API access).

For competitor benchmarking, the realistic paths are:
  (a) Let users paste in competitor post text/screenshots manually and
      run analysis on that (no API needed, ships today) -- this is what
      `competitor_benchmarker.py` in this project expects as input.
  (b) Apply for LinkedIn Community Management API access for pages you
      administer, and only benchmark against competitors who happen to
      also be pages you can add as "showcase"/analytics-shared pages.
  (c) Use a licensed third-party social-listening data provider (e.g.
      Brandwatch, Phantombuster's officially compliant offerings, etc.)
      instead of hitting LinkedIn directly.

This file implements (a)'s API surface honestly: publish + fetch-your-own.
"""

import os
import requests
from typing import Optional

LINKEDIN_API_VERSION = "202405"  # LinkedIn-Version header, bump periodically
BASE_URL = "https://api.linkedin.com"


class LinkedInAPIError(Exception):
    pass


class LinkedInAPI:
    def __init__(self, access_token: Optional[str] = None):
        self.access_token = access_token or os.getenv("LINKEDIN_ACCESS_TOKEN")
        if not self.access_token:
            raise ValueError("No LinkedIn access token provided or found in env.")

    def _headers(self, restli: bool = True) -> dict:
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        if restli:
            headers["LinkedIn-Version"] = LINKEDIN_API_VERSION
            headers["X-Restli-Protocol-Version"] = "2.0.0"
        return headers

    # ---------------------------------------------------------------
    # 1. Get the authenticated member's identity (needed to build the
    #    author URN used when publishing, e.g. "urn:li:person:AbCdEfGh")
    # ---------------------------------------------------------------
    def get_profile(self) -> dict:
        """
        Uses the OpenID Connect /v2/userinfo endpoint (requires the
        'openid profile email' scopes). This replaced the deprecated
        /v2/me + r_liteprofile flow.
        Returns a dict with at least: sub, given_name, family_name, email
        """
        resp = requests.get(
            f"{BASE_URL}/v2/userinfo",
            headers=self._headers(restli=False),
            timeout=15,
        )
        if resp.status_code != 200:
            raise LinkedInAPIError(f"get_profile failed [{resp.status_code}]: {resp.text}")
        return resp.json()

    def get_person_urn(self) -> str:
        profile = self.get_profile()
        member_id = profile["sub"]
        return f"urn:li:person:{member_id}"

    def get_person_display_name(self) -> str:
        profile = self.get_profile()
        name = f"{profile.get('given_name', '')} {profile.get('family_name', '')}".strip()
        return name or profile.get("email", "LinkedIn member")

    # ---------------------------------------------------------------
    # 2. Publish a text post as the authenticated member.
    #    Uses the current Posts API (/rest/posts), which superseded
    #    the older /v2/ugcPosts endpoint.
    # ---------------------------------------------------------------
    def publish_post(self, text: str, author_urn: Optional[str] = None,
                      visibility: str = "PUBLIC") -> str:
        """
        Publishes a simple text post. Returns the created post's URN.

        `author_urn` should be a person URN (urn:li:person:...) for a
        personal profile post, or an organization URN
        (urn:li:organization:...) if posting to a Company Page you admin
        with the right permissions.
        """
        author_urn = author_urn or self.get_person_urn()

        payload = {
            "author": author_urn,
            "commentary": text,
            "visibility": visibility,               # PUBLIC or CONNECTIONS
            "distribution": {
                "feedDistribution": "MAIN_FEED",
                "targetEntities": [],
                "thirdPartyDistributionChannels": [],
            },
            "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": False,
        }

        resp = requests.post(
            f"{BASE_URL}/rest/posts",
            headers=self._headers(),
            json=payload,
            timeout=15,
        )
        if resp.status_code not in (200, 201):
            raise LinkedInAPIError(f"publish_post failed [{resp.status_code}]: {resp.text}")

        # LinkedIn returns the new post's URN in the x-restli-id / x-linkedin-id header
        post_urn = resp.headers.get("x-restli-id") or resp.headers.get("x-linkedin-id")
        return post_urn or ""

    # ---------------------------------------------------------------
    # 3. Fetch posts authored by the SAME identity you're authenticated
    #    as (your own profile or an org page you admin). This is the
    #    "get_recent_posts" used by the scheduler for your own history,
    #    NOT for arbitrary competitors (see module docstring above).
    # ---------------------------------------------------------------
    def get_own_recent_posts(self, author_urn: Optional[str] = None, count: int = 10) -> list[dict]:
        author_urn = author_urn or self.get_person_urn()
        params = {
            "author": author_urn,
            "q": "author",
            "count": count,
            "sortBy": "LAST_MODIFIED",
        }
        resp = requests.get(
            f"{BASE_URL}/rest/posts",
            headers=self._headers(),
            params=params,
            timeout=15,
        )
        if resp.status_code != 200:
            raise LinkedInAPIError(f"get_own_recent_posts failed [{resp.status_code}]: {resp.text}")
        return resp.json().get("elements", [])

    def delete_post(self, post_urn: str) -> bool:
        resp = requests.delete(
            f"{BASE_URL}/rest/posts/{requests.utils.quote(post_urn, safe='')}",
            headers=self._headers(),
            timeout=15,
        )
        return resp.status_code in (200, 204)


def build_organization_urn(org_id_or_urn: str) -> str:
    """
    Normalizes either a raw numeric LinkedIn Company Page ID (found in the
    page's admin URL, e.g. linkedin.com/company/12345678/admin) or an
    already-formatted URN into 'urn:li:organization:<id>'.

    NOTE: There's no API call to "list organizations I administer" available
    on a standard app tier -- the user has to find their own page's numeric
    ID from the page's admin view URL and paste it in. Publishing to it also
    requires the app to have been granted admin access to that specific page
    via LinkedIn's page verification flow, not just a generic OAuth scope.
    """
    org_id_or_urn = org_id_or_urn.strip()
    if org_id_or_urn.startswith("urn:li:organization:"):
        return org_id_or_urn
    if org_id_or_urn.isdigit():
        return f"urn:li:organization:{org_id_or_urn}"
    raise ValueError(
        "Expected a numeric LinkedIn Company Page ID or a full "
        "'urn:li:organization:...' URN."
    )


# ---------------------------------------------------------------------
# Manual competitor-input helper (the realistic alternative to scraping)
# ---------------------------------------------------------------------
def register_manual_competitor_post(vector_store, db, workspace_id: int,
                                     competitor_name: str, post_text: str,
                                     likes: int = 0, comments: int = 0):
    """
    Since LinkedIn won't let a normal app pull a competitor's posts (see
    module docstring above), the pragmatic path is a simple form in your
    UI where the user pastes a competitor's post text/stats. This stores
    it so competitor_benchmarker.py has something to compare against.

    Call this from app.py's "Competitors" page after the user pastes text.
    """
    # Ensure the competitor exists as a record (idempotent-ish upsert)
    existing = [c for c in db.get_competitors(workspace_id) if c["name"] == competitor_name]
    if not existing:
        db.add_competitor(workspace_id, name=competitor_name)

    # Store the actual post text + engagement numbers in the vector store
    # so it's retrievable as semantic context for the strategist/benchmarker.
    vector_store.add_posts(workspace_id, [
        {
            "id": f"competitor-{competitor_name}-{hash(post_text) & 0xffffffff}",
            "text": post_text,
            "metadata": {
                "source": "competitor",
                "competitor_name": competitor_name,
                "likes": likes,
                "comments": comments,
            },
        }
    ])