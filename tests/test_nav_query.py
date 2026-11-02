"""Nav query params must preserve auth sid."""

from __future__ import annotations

from unittest.mock import MagicMock


def test_set_nav_query_params_preserves_sid(monkeypatch):
    import ui.nav as nav

    params: dict[str, str] = {"sid": "abc123", "nav": "explore"}

    class QP(dict):
        def get(self, key, default=None):
            return super().get(key, default)

        def from_dict(self, desired):
            self.clear()
            self.update(desired)

    qp = QP(params)
    st = MagicMock()
    st.query_params = qp
    monkeypatch.setattr(nav, "st", st)

    nav.set_nav_query_params(page="portfolio")
    assert qp.get("sid") == "abc123"
    assert qp.get("nav") == "portfolio"
