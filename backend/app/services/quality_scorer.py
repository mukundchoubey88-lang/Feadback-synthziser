from typing import List, Tuple


class QualityScorer:
    """Deterministic, transparent scoring engine separating content quality from metadata completeness.

    1. Content Quality Score (0.0 to 100.0 scale):
       - Measures text usefulness, signal-to-noise ratio, readability, and brevity.
       - Rejection penalty: if quality_status == 'rejected', content_quality_score = 0.0.
       - SPAM_PATTERN: -40.0
       - URL_ONLY: -40.0
       - REPEATED_CHARS: -30.0
       - VERY_SHORT (< 20 chars): -15.0
       - Moderately brief (20-49 chars): -5.0
       - PII_PRESENT: -5.0
       - Invariant: Zero penalty for missing optional metadata (anonymous reviews can score 100.0).
       - Sentiment Invariant: Negative emotional feedback is evaluated strictly on detail and clarity.

    2. Metadata Completeness Score (0.0 to 100.0 scale):
       - Measures completeness of optional ingested metadata dimensions.
       - customer_id present: +35.0
       - feature present: +35.0
       - app_version present: +30.0
    """

    @classmethod
    def calculate_content_quality_score(
        cls,
        text: str,
        quality_status: str,
        quality_flags: List[str],
    ) -> float:
        """Compute content quality score strictly evaluating text usefulness without metadata penalties."""
        if quality_status == "rejected":
            return 0.0

        score = 100.0

        if "SPAM_PATTERN" in quality_flags:
            score -= 40.0
        if "URL_ONLY" in quality_flags:
            score -= 40.0
        if "REPEATED_CHARS" in quality_flags:
            score -= 30.0

        text_len = len(text.strip())
        if "VERY_SHORT" in quality_flags or text_len < 20:
            score -= 15.0
        elif text_len < 50:
            score -= 5.0

        if "PII_PRESENT" in quality_flags:
            score -= 5.0

        return max(0.0, min(100.0, round(score, 1)))

    @classmethod
    def calculate_metadata_completeness_score(
        cls,
        has_customer_id: bool,
        has_feature: bool,
        has_app_version: bool,
    ) -> float:
        """Compute metadata completeness score on [0.0, 100.0] independently from content quality."""
        score = 0.0
        if has_customer_id:
            score += 35.0
        if has_feature:
            score += 35.0
        if has_app_version:
            score += 30.0
        return max(0.0, min(100.0, round(score, 1)))

    @classmethod
    def calculate_score(
        cls,
        text: str,
        quality_status: str,
        quality_flags: List[str],
        has_customer_id: bool,
        has_feature: bool,
        has_app_version: bool,
    ) -> Tuple[float, float, float]:
        """Compute all scores: (quality_score, content_quality_score, metadata_completeness_score).

        Note: overall `quality_score` aligns directly with `content_quality_score` so that
        missing optional metadata does not penalize feedback text usefulness.
        """
        content_score = cls.calculate_content_quality_score(text, quality_status, quality_flags)
        meta_score = cls.calculate_metadata_completeness_score(has_customer_id, has_feature, has_app_version)
        return content_score, content_score, meta_score
