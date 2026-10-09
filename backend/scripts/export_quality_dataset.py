"""Export labeled RSS entries with a time and event-group holdout."""
import argparse
import json
from collections import defaultdict
from datetime import datetime

from app.core.database import SessionLocal
from app.modules.news.models import ArticleIdentity, EventPairLabel, RssEntrySample


def split_samples(samples, articles, pairs, cutoff):
    parent = {article_id: article_id for article_id in articles}

    def find(article_id):
        while parent[article_id] != article_id:
            parent[article_id] = parent[parent[article_id]]
            article_id = parent[article_id]
        return article_id

    def union(first_id, second_id):
        if first_id in parent and second_id in parent:
            parent[find(second_id)] = find(first_id)

    by_event = defaultdict(list)
    for article in articles.values():
        if article.event_id is not None:
            by_event[article.event_id].append(article.id)
    for ids in by_event.values():
        for article_id in ids[1:]:
            union(ids[0], article_id)
    for pair in pairs:
        if pair.same_event:
            union(pair.article_a_id, pair.article_b_id)

    group_dates = {}
    for sample in samples:
        if sample.article_id in parent:
            root = find(sample.article_id)
            date = sample.published_date or sample.sampled_at
            group_dates[root] = max(group_dates.get(root, date), date)

    output = {"train": [], "test": [], "ungrouped_time_only": 0}
    for sample in samples:
        date = sample.published_date or sample.sampled_at
        if sample.article_id in parent:
            split = "test" if group_dates[find(sample.article_id)] >= cutoff else "train"
        else:
            split = "test" if date >= cutoff else "train"
            output["ungrouped_time_only"] += 1
        output[split].append({
            "sample_id": sample.id,
            "link": sample.link,
            "title": sample.title,
            "summary": sample.summary,
            "published_date": date.isoformat(),
            "passed_stage1": sample.passed_stage1,
            "llm_label": sample.llm_label,
            "predicted_disease": sample.predicted_disease,
            "predicted_location": sample.predicted_location,
            "predicted_event_date": sample.predicted_event_date.isoformat() if sample.predicted_event_date else None,
            "predicted_case_values": json.loads(sample.predicted_case_values or "[]"),
            "human_relevant": sample.human_relevant,
            "human_disease": sample.human_disease,
            "human_location": sample.human_location,
            "human_event_date": sample.human_event_date.isoformat() if sample.human_event_date else None,
            "human_case_value": sample.human_case_value,
        })
    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cutoff", required=True, help="YYYY-MM-DD")
    args = parser.parse_args()
    cutoff = datetime.strptime(args.cutoff, "%Y-%m-%d")
    with SessionLocal() as db:
        samples = db.query(RssEntrySample).filter(
            RssEntrySample.human_relevant.isnot(None),
            RssEntrySample.expires_at >= datetime.utcnow(),
        ).all()
        pairs = db.query(EventPairLabel).all()
        ids = {sample.article_id for sample in samples if sample.article_id is not None}
        ids.update(article_id for pair in pairs for article_id in (pair.article_a_id, pair.article_b_id))
        articles = {
            article.id: article for article in db.query(ArticleIdentity).filter(ArticleIdentity.id.in_(ids)).all()
        } if ids else {}
        result = split_samples(samples, articles, pairs, cutoff)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
