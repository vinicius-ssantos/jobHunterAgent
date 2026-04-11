import unittest

from job_hunter_agent.collectors.linkedin_application_entrypoint import (
    build_linkedin_direct_apply_url,
    canonical_linkedin_job_url,
    classify_linkedin_job_page_readiness,
    extract_linkedin_job_id,
    needs_canonical_job_navigation,
    recover_linkedin_direct_apply_url_from_html,
)
from job_hunter_agent.collectors.linkedin_application_state import LinkedInApplicationPageState


class LinkedInApplicationEntrypointTests(unittest.TestCase):
    def test_extract_linkedin_job_id_reads_view_route(self) -> None:
        self.assertEqual(
            extract_linkedin_job_id("https://www.linkedin.com/jobs/view/4390058075/?refId=abc"),
            "4390058075",
        )

    def test_extract_linkedin_job_id_reads_current_job_id_from_listing_query(self) -> None:
        self.assertEqual(
            extract_linkedin_job_id(
                "https://www.linkedin.com/jobs/collections/similar-jobs/?currentJobId=4391593841&referenceJobId=4390058075"
            ),
            "4391593841",
        )

    def test_canonical_linkedin_job_url_removes_tracking_query(self) -> None:
        self.assertEqual(
            canonical_linkedin_job_url(
                "https://www.linkedin.com/jobs/view/4390058075/?refId=abc&trackingId=def"
            ),
            "https://www.linkedin.com/jobs/view/4390058075/",
        )

    def test_build_linkedin_direct_apply_url_uses_target_job_id(self) -> None:
        self.assertEqual(
            build_linkedin_direct_apply_url("https://www.linkedin.com/jobs/view/4389607214/"),
            "https://www.linkedin.com/jobs/view/4389607214/apply/?openSDUIApplyFlow=true",
        )

    def test_needs_canonical_job_navigation_on_similar_jobs_page(self) -> None:
        self.assertTrue(
            needs_canonical_job_navigation(
                "https://www.linkedin.com/jobs/collections/similar-jobs/?currentJobId=4391593841&referenceJobId=4390058075",
                "https://www.linkedin.com/jobs/view/4390058075/",
            )
        )

    def test_needs_canonical_job_navigation_is_false_for_apply_flow_of_same_job(self) -> None:
        self.assertFalse(
            needs_canonical_job_navigation(
                "https://www.linkedin.com/jobs/view/4390058075/apply/?openSDUIApplyFlow=true",
                "https://www.linkedin.com/jobs/view/4390058075/",
            )
        )

    def test_classify_linkedin_job_page_readiness_marks_similar_jobs_as_listing_redirect(self) -> None:
        readiness = classify_linkedin_job_page_readiness(
            job_url="https://www.linkedin.com/jobs/view/4390058075/",
            state=LinkedInApplicationPageState(
                current_url="https://www.linkedin.com/jobs/collections/similar-jobs/?currentJobId=4391593841&referenceJobId=4390058075",
                sample="https://www.linkedin.com/jobs/collections/similar-jobs/?currentJobId=4391593841 | vaga parecida",
            ),
        )

        self.assertEqual(readiness.result, "listing_redirect")
        self.assertIn("colecao", readiness.reason)

    def test_classify_linkedin_job_page_readiness_marks_external_only_apply_as_no_apply_cta(self) -> None:
        readiness = classify_linkedin_job_page_readiness(
            job_url="https://www.linkedin.com/jobs/view/4390058075/",
            state=LinkedInApplicationPageState(
                current_url="https://www.linkedin.com/jobs/view/4390058075/",
                external_apply=True,
                sample="https://www.linkedin.com/jobs/view/4390058075/ | candidatar-se no site da empresa",
            ),
        )

        self.assertEqual(readiness.result, "no_apply_cta")
        self.assertIn("candidatura externa", readiness.reason)

    def test_recover_linkedin_direct_apply_url_from_html_uses_hidden_internal_apply_metadata(self) -> None:
        apply_url = recover_linkedin_direct_apply_url_from_html(
            """
            <html><body>
            <code>{"onsiteApply":true,"applyCtaText":{"text":"Candidatura simplificada"},"companyApplyUrl":"https://www.linkedin.com/job-apply/4389607214"}</code>
            </body></html>
            """,
            "https://www.linkedin.com/jobs/view/4389607214/",
        )

        self.assertEqual(
            apply_url,
            "https://www.linkedin.com/jobs/view/4389607214/apply/?openSDUIApplyFlow=true",
        )

    def test_recover_linkedin_direct_apply_url_from_html_returns_empty_without_internal_signal(self) -> None:
        self.assertEqual(
            recover_linkedin_direct_apply_url_from_html(
                "<html><body>sem metadata de candidatura</body></html>",
                "https://www.linkedin.com/jobs/view/4389607214/",
            ),
            "",
        )
