"""Export labeled event pairs with a time- and event-disjoint holdout."""
import argparse
import json
from collections import defaultdict
from datetime import datetime

from app.core.database import SessionLocal
from app.modules.news.models import ArticleIdentity, EventPairLabel


def build_splits(pairs, articles, cutoff: datetime):
    parent = {article_id: article_id for article_id in articles}

    def find(article_id):
        while parent[article_id] != article_id:
            parent[article_id] = parent[parent[article_id]]
            article_id = parent[article_id]
        return article_id

    for pair in pairs:
        if pair.same_event:
            a, b = find(pair.article_a_id), find(pair.article_b_id)
            parent[b] = a

    members = defaultdict(list)
    for article_id in articles:
        members[find(article_id)].append(article_id)

    component_split = {}
    for root, ids in members.items():
        dates = [articles[article_id].published_date for article_id in ids if articles[article_id].published_date]
        component_split[root] = "test" if dates and max(dates) >= cutoff else "train"

    output = {"train": [], "test": [], "excluded_cross_split": 0}
    for pair in pairs:
        first_split = component_split[find(pair.article_a_id)]
        second_split = component_split[find(pair.article_b_id)]
        if first_split != second_split:
            output["excluded_cross_split"] += 1
            continue
        output[first_split].append({
            "article_a_id": pair.article_a_id,
            "article_b_id": pair.article_b_id,
            "same_event": pair.same_event,
            "predicted_same_event": pair.predicted_same_event,
            "labeled_at": pair.labeled_at.isoformat(),
        })
    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cutoff", required=True, help="YYYY-MM-DD")
    args = parser.parse_args()
    cutoff = datetime.strptime(args.cutoff, "%Y-%m-%d")
    with SessionLocal() as db:
        pairs = db.query(EventPairLabel).all()
        ids = {article_id for pair in pairs for article_id in (pair.article_a_id, pair.article_b_id)}
        articles = {
            article.id: article
            for article in db.query(ArticleIdentity).filter(ArticleIdentity.id.in_(ids)).all()
        } if ids else {}
        pairs = [pair for pair in pairs if pair.article_a_id in articles and pair.article_b_id in articles]
        result = build_splits(pairs, articles, cutoff)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
