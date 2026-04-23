import unittest
from urllib.parse import parse_qs, urlparse

from job_hunter_agent.collectors.linkedin import (
    LinkedInDeterministicCollector,
    build_linkedin_advanced_search_url,
    extract_linkedin_search_keywords,
)


class LinkedInSearchQueriesTests(unittest.TestCase):
    def test_build_linkedin_advanced_search_url_applies_advanced_filters(self) -> None:
        url = build_linkedin_advanced_search_url(
            base_url="https://www.linkedin.com/jobs/search/?geoId=106057199",
            keywords="java backend junior pleno",
            experience_levels=("2", "3"),
            workplace_types=("2", "3"),
            easy_apply_only=True,
            recency_seconds=604800,
            sort_by="DD",
        )
        parsed = urlparse(url)
        params = parse_qs(parsed.query)

        self.assertEqual(params["keywords"][0], "java backend junior pleno")
        self.assertEqual(params["f_E"][0], "2,3")
        self.assertEqual(params["f_WT"][0], "2,3")
        self.assertEqual(params["f_AL"][0], "true")
        self.assertEqual(params["f_TPR"][0], "r604800")
        self.assertEqual(params["sortBy"][0], "DD")
        self.assertEqual(params["geoId"][0], "106057199")

    def test_extract_linkedin_search_keywords_reads_keywords_param(self) -> None:
        keywords = extract_linkedin_search_keywords(
            "https://www.linkedin.com/jobs/search/?keywords=java%20backend%20pleno&f_AL=true"
        )
        self.assertEqual(keywords, "java backend pleno")

    def test_collector_rotates_selected_queries_across_cycles(self) -> None:
        collector = LinkedInDeterministicCollector(
            storage_state_path="./.browseruse/linkedin-storage-state.json",
            headless=True,
            search_queries=("java backend junior", "java spring pleno", "engenharia software java"),
            search_queries_per_cycle=2,
            search_experience_levels=("2", "3"),
            search_workplace_types=("2", "3"),
            search_easy_apply_only=True,
            search_recency_seconds=86400,
            search_sort_by="DD",
        )
        all_urls = collector._resolve_search_urls("https://www.linkedin.com/jobs/search/")

        first_cycle = collector._select_search_urls_for_cycle(all_urls)
        second_cycle = collector._select_search_urls_for_cycle(all_urls)

        first_keywords = [extract_linkedin_search_keywords(url) for url in first_cycle]
        second_keywords = [extract_linkedin_search_keywords(url) for url in second_cycle]

        self.assertEqual(first_keywords, ["java backend junior", "java spring pleno"])
        self.assertEqual(second_keywords, ["engenharia software java", "java backend junior"])

