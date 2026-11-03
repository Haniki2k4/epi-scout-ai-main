"""Shared public visibility, including review labels on legacy rows."""
from sqlalchemy import and_, exists, func, select

from .models import ArticleIdentity
from ..evaluation.models import ArticleEvaluation


def public_article_condition():
    rejected = exists(select(ArticleEvaluation.id).where(
        ArticleEvaluation.article_id == ArticleIdentity.id,
        func.coalesce(func.nullif(ArticleEvaluation.human_label, ''), ArticleEvaluation.llm_label)
        .in_(['noise', 'irrelevant', 'unsure']),
    )).correlate(ArticleIdentity)
    return and_(ArticleIdentity.is_excluded.isnot(True), ~rejected)
