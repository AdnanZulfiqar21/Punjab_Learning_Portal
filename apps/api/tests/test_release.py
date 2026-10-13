"""P17.S3.T2 (RELEASE-01): the release manifest records what a build contains, and migrations stay compatible with the
code already running (expand first; contract only with an explicit, reasoned marker)."""

from __future__ import annotations

from portal_api import release


def test_the_repository_passes_the_migration_rules() -> None:
    assert release.check() == []


def test_destructive_changes_need_a_reasoned_contract_marker() -> None:
    up = 'def upgrade() -> None:\n    op.drop_column("attempt", "legacy")\n\n\ndef downgrade() -> None:\n    pass\n'
    assert release.check_migration_text("new_rev", up, grandfathered=False)
    marked = "# contract-migration: legacy column unused since release 12 (expand in 20261101_aaa)\n" + up
    assert release.check_migration_text("new_rev", marked, grandfathered=False) == []
    renamed = (
        'def upgrade() -> None:\n    op.alter_column("t", "a", new_column_name="b")\n\n'
        "def downgrade() -> None:\n    pass\n"
    )
    assert release.check_migration_text("new_rev", renamed, grandfathered=False)
    no_down = 'def upgrade() -> None:\n    op.add_column("t", sa.Column("x", sa.Integer()))\n'
    assert release.check_migration_text("new_rev", no_down, grandfathered=False)
    assert release.check_migration_text("old_rev", up, grandfathered=True) == []  # pre-launch history is grandfathered


def test_the_manifest_describes_the_build() -> None:
    m = release.manifest()
    for key in (
        "git_commit",
        "migration_head",
        "openapi_sha256",
        "catalogue_sha256",
        "content_schema_version",
        "supported_renderer",
        "analytics_events",
        "feature_switches",
        "lockfiles",
    ):
        assert key in m, key
    assert len(m["openapi_sha256"]) == 64 and m["migration_head"]
    assert m["analytics_events"]["attempt.submitted"] == 1
    # P19.S4.T3 (RELEASE-CANDIDATE-01): app identities, the published content set, and known limitations.
    app = m["mobile_app"]
    assert app["version"] and set(app["ids"]) == {"development", "preview", "production"}
    assert len(set(app["ids"].values())) == 3  # a development or preview build is never mistaken for production
    assert m["ota_runtime_version"] is None and m["image_digests"] is None  # recorded honestly until B07/B03
    if m["content_release_id"] is not None:  # a database was reachable: the live state is pinned too
        assert len(m["content_release_id"]) == 64
        assert set(m["runtime_overrides"]) == {"switches", "rollouts"}
        assert set(m["runtime_overrides"]["rollouts"]) <= set(m["feature_rollouts"])
    assert any(x.startswith("B03:") for x in m["known_limitations"])
