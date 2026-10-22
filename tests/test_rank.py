from datetime import timedelta

from nmb.config import RankingConfig
from nmb.pipeline.rank import rank_section, score_article


def test_recency_and_source_weight_contribute_to_score(make_article, now):
    ranking = RankingConfig()
    fresh = make_article(age_hours=1, source_weight=1.0)
    older_heavy = make_article(age_hours=20, source_weight=2.0)

    fresh_score = score_article(fresh, now, 36, ranking)
    heavy_score = score_article(older_heavy, now, 36, ranking)
    assert fresh_score > heavy_score
    assert heavy_score > 0


def test_cross_source_mentions_and_points_raise_score(make_article, now):
    ranking = RankingConfig()
    plain = make_article(age_hours=2, points=0)
    boosted = make_article(age_hours=2, points=400)
    boosted.also_sources = ["Another Source", "Third Source"]

    assert boosted.source_count == 3
    assert score_article(boosted, now, 36, ranking) > score_article(plain, now, 36, ranking)


def test_rank_excludes_items_outside_lookback(make_article, now):
    recent = make_article(age_hours=4, title="Recent")
    stale = make_article(age_hours=40, title="Stale")
    result = rank_section(
        [recent, stale],
        now=now,
        lookback_hours=36,
        ranking=RankingConfig(),
    )
    assert [item.title for item in result] == ["Recent"]


def test_rank_orders_by_score(make_article, now):
    low = make_article(age_hours=30, source_weight=0.8, points=1)
    high = make_article(age_hours=1, source_weight=1.5, points=100)
    result = rank_section(
        [low, high],
        now=now,
        lookback_hours=36,
        ranking=RankingConfig(),
    )
    assert result[0] is high
    assert result[0].score >= result[1].score


def test_future_articles_are_excluded(make_article, now):
    future = make_article(published_at=now + timedelta(hours=2))
    result = rank_section(
        [future],
        now=now,
        lookback_hours=36,
        ranking=RankingConfig(),
    )
    assert result == []
