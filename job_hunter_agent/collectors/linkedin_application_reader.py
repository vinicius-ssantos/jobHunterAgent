from __future__ import annotations

from job_hunter_agent.collectors.linkedin_application_state import LinkedInApplicationPageState


LINKEDIN_APPLICATION_PAGE_STATE_SCRIPT = """
() => {
  const normalize = (value) => (value || "").replace(/\\s+/g, " ").trim().toLowerCase();
  const isExcludedNode = (node) => !!node?.closest(
    '[componentkey^="JobDetailsSimilarJobsSlot_"], [data-sdui-component*="similarJobs"]'
  );
  const currentUrl = window.location.href || "";
  const currentPath = `${window.location.origin || ''}${window.location.pathname || ''}`;
  const hiddenPayload = Array.from(document.querySelectorAll('code, script[type="application/ld+json"]'))
    .map((node) => normalize(node.textContent || ''))
    .join(' | ')
    .slice(0, 4000);
  const main = document.querySelector('main') || document.body;
  const detailCandidates = [
    '.jobs-search__job-details--container .jobs-details-top-card',
    '.jobs-details-top-card',
    '.jobs-search__job-details--container',
    '.jobs-details',
    'div[role="main"][data-sdui-screen*="JobDetails"]',
    '#workspace',
    'main',
  ];
  const detailPanel =
    detailCandidates
      .map((selector) => document.querySelector(selector))
      .find((node) => !!node)
    || main;
  const topCard =
    detailPanel.querySelector('.jobs-details-top-card') ||
    detailPanel.querySelector('[data-live-test-job-apply-button]') ||
    detailPanel;
  const prioritizedSelectors = [
    '[data-live-test-job-apply-button]',
    '[data-control-name="jobdetails_topcard_inapply"]',
    '[data-control-name="topcard_inapply"]',
    '[data-control-name="jobs-details-top-card-apply-button"]',
    '.jobs-apply-button',
    '.jobs-apply-button--top-card button',
    '.jobs-s-apply button',
  ];
  const prioritizedNodes = prioritizedSelectors.flatMap((selector) =>
    Array.from(topCard.querySelectorAll(selector)).filter((node) => !isExcludedNode(node))
  );
  const globalApplyNodes = Array.from(main.querySelectorAll("button, a"))
    .filter((node) => !isExcludedNode(node))
    .filter((node) => {
      if (node.closest('header, footer, nav')) return false;
      const href = (node.getAttribute('href') || '').toLowerCase();
      const text = normalize(node.textContent || node.getAttribute('aria-label') || '');
      const control = normalize(node.getAttribute('data-control-name') || '');
      return (
        text.includes("easy apply")
        || text.includes("candidatura simplificada")
        || href.includes("/apply/")
        || control.includes("inapply")
        || control.includes("apply-button")
      );
    });
  const prioritizedTexts = prioritizedNodes
    .map((node) => normalize(node.textContent || node.getAttribute('aria-label') || ''))
    .filter(Boolean);
  const globalApplyTexts = globalApplyNodes
    .map((node) => normalize(node.textContent || node.getAttribute('aria-label') || ''))
    .filter(Boolean);
  const texts = Array.from(detailPanel.querySelectorAll("button, a"))
    .filter((node) => !isExcludedNode(node))
    .map((node) => normalize(node.textContent || node.getAttribute('aria-label') || ''))
    .filter(Boolean);
  const applyContext = globalApplyNodes[0]?.closest('section, article, div');
  const joined = normalize(
    applyContext?.innerText
    || detailPanel.innerText
    || topCard.innerText
    || main.innerText
    || ""
  ).slice(0, 400);
  const easyApplyTexts = (prioritizedTexts.length ? prioritizedTexts : (globalApplyTexts.length ? globalApplyTexts : texts))
    .filter((text) => text.includes("easy apply") || text.includes("candidatura simplificada"));
  const applyHrefVisible = globalApplyNodes.some((node) =>
    ((node.getAttribute('href') || '').toLowerCase().includes('/apply/'))
  );
  const applyFlowActive = currentUrl.includes("/apply/") || currentUrl.includes("openSDUIApplyFlow=true");
  const hiddenEasyApply = hiddenPayload.includes('onsiteapply')
    || hiddenPayload.includes('applyctatext')
    || hiddenPayload.includes('candidatura simplificada');
  const externalApply = texts.some((text) =>
    text.includes("candidate-se")
    || text.includes("candidatar-se")
    || text.includes("apply on company website")
    || text.includes("site da empresa")
  );
  const submitVisible = texts.some((text) => text.includes("enviar candidatura") || text.includes("submit application"));

  const confirmationDialog = document.querySelector('[role="alertdialog"]');
  const confirmationTexts = confirmationDialog
    ? Array.from(confirmationDialog.querySelectorAll("button, span, div, h1, h2, h3, p"))
        .map((node) => normalize(node.textContent))
        .filter(Boolean)
    : [];
  const confirmationJoined = confirmationTexts.join(" | ");
  const saveApplicationDialogVisible = confirmationJoined.includes("salvar esta candidatura")
    || confirmationJoined.includes("save this application");

  const modal = document.querySelector('[role="dialog"]');
  const modalButtonTexts = modal
    ? Array.from(modal.querySelectorAll("button"))
        .map((node) => normalize(node.textContent))
        .filter(Boolean)
    : [];
  const modalTexts = modal
    ? Array.from(modal.querySelectorAll("button, label, span, div, h2, h3, p, legend"))
        .map((node) => normalize(node.textContent))
        .filter(Boolean)
    : [];
  const modalInputNames = modal
    ? Array.from(modal.querySelectorAll("input, textarea, select"))
        .map((node) => normalize(node.getAttribute("name") || node.getAttribute("aria-label") || node.id || ""))
        .filter(Boolean)
    : [];
  const modalHeadings = modal
    ? Array.from(modal.querySelectorAll("h1, h2, h3, legend"))
        .map((node) => normalize(node.textContent))
        .filter(Boolean)
    : [];
  const fieldDescriptor = (field) => {
    if (!field) return "";
    const parts = [];
    const fieldId = field.getAttribute("id");
    if (fieldId) {
      const explicitLabel = modal.querySelector(`label[for="${fieldId}"]`);
      if (explicitLabel) parts.push(explicitLabel.textContent || "");
    }
    const labelledBy = field.getAttribute("aria-labelledby");
    if (labelledBy) {
      labelledBy.split(/\\s+/).forEach((id) => {
        const labelNode = document.getElementById(id);
        if (labelNode) parts.push(labelNode.textContent || "");
      });
    }
    const describedBy = field.getAttribute("aria-describedby");
    if (describedBy) {
      describedBy.split(/\\s+/).forEach((id) => {
        const describedNode = document.getElementById(id);
        if (describedNode) parts.push(describedNode.textContent || "");
      });
    }
    const closestLabel = field.closest("label");
    if (closestLabel) parts.push(closestLabel.textContent || "");
    const formElement = field.closest("[data-test-form-element]") || field.closest(".fb-dash-form-element");
    if (formElement) {
      const legend = formElement.querySelector("legend");
      const title = formElement.querySelector("[data-test-text-entity-list-form-title]");
      if (legend) parts.push(legend.textContent || "");
      if (title) parts.push(title.textContent || "");
    }
    parts.push(field.getAttribute("name") || "");
    parts.push(field.getAttribute("aria-label") || "");
    return normalize(parts.join(" "));
  };
  const hasText = (items, parts) => parts.some((part) => items.some((value) => value.includes(part)));
  const resumableFields = [];
  const contactEmailVisible = hasText(modalTexts, ["email", "e-mail"]) || hasText(modalInputNames, ["email"]);
  const contactPhoneVisible = hasText(modalTexts, ["phone", "telefone", "celular"]) || hasText(modalInputNames, ["phone", "telefone", "celular"]);
  const countryCodeVisible = hasText(modalTexts, ["country code", "codigo do pais", "cÃ³digo do paÃ­s"]) || hasText(modalInputNames, ["country code", "codigo", "cÃ³digo"]);
  const workAuthorizationVisible = hasText(modalTexts, ["work authorization", "work permit", "autoriz", "visa"]) || hasText(modalInputNames, ["authorization", "permit", "visa"]);
  const yearsOfExperienceVisible = hasText(modalTexts, ["years of work experience", "anos de experiencia"]) || hasText(modalInputNames, ["years", "experience"]);
  if (contactEmailVisible) resumableFields.push("email");
  if (contactPhoneVisible) resumableFields.push("telefone");
  if (countryCodeVisible) resumableFields.push("codigo_pais");
  if (workAuthorizationVisible) resumableFields.push("autorizacao_trabalho");
  if (yearsOfExperienceVisible) resumableFields.push("anos_experiencia");
  const requiredFields = modal
    ? Array.from(modal.querySelectorAll('input[required], textarea[required], select[required]'))
        .map((field) => fieldDescriptor(field))
        .filter(Boolean)
    : [];
  const modalQuestions = requiredFields.filter((descriptor) => !(
    descriptor.includes("email")
    || descriptor.includes("e-mail")
    || descriptor.includes("phone")
    || descriptor.includes("telefone")
    || descriptor.includes("celular")
    || descriptor.includes("country code")
    || descriptor.includes("codigo do pais")
    || descriptor.includes("cÃ³digo do paÃ­s")
    || descriptor.includes("cÃƒÂ³digo do paÃƒÂ­s")
    || descriptor.includes("resume")
    || descriptor.includes("curriculo")
  ));
  return {
    current_url: currentUrl,
    easy_apply: easyApplyTexts.length > 0 || applyHrefVisible || applyFlowActive || hiddenEasyApply,
    external_apply: externalApply,
    submit_visible: submitVisible,
    modal_open: !!modal,
    modal_submit_visible: modalButtonTexts.some((text) => text.includes("submit application") || text.includes("enviar candidatura")),
    modal_next_visible: modalButtonTexts.some((text) => text.includes("next") || text.includes("continuar") || text.includes("avancar") || text.includes("avanÃ§ar")),
    modal_review_visible: modalButtonTexts.some((text) => text.includes("review") || text.includes("revisar")),
    modal_file_upload: modal ? modal.querySelectorAll('input[type="file"]').length > 0 : false,
    modal_questions_visible: modalQuestions.length > 0,
    save_application_dialog_visible: saveApplicationDialogVisible,
    cta_text: easyApplyTexts[0] || (hiddenEasyApply ? "candidatura simplificada" : ""),
    sample: `${currentPath} | ${joined}`.slice(0, 400),
    modal_sample: (modalTexts.join(" | ") || confirmationJoined).slice(0, 400),
    contact_email_visible: contactEmailVisible,
    contact_phone_visible: contactPhoneVisible,
    country_code_visible: countryCodeVisible,
    work_authorization_visible: workAuthorizationVisible,
    years_of_experience_visible: yearsOfExperienceVisible,
    resumable_fields: resumableFields,
    filled_fields: [],
    progressed_to_next_step: false,
    uploaded_resume: false,
    reached_review_step: false,
    ready_to_submit: false,
    modal_headings: modalHeadings.slice(0, 6),
    modal_buttons: modalButtonTexts.slice(0, 8),
    modal_fields: modalInputNames.slice(0, 8),
    modal_questions: modalQuestions.slice(0, 6),
  };
}
"""


def normalize_linkedin_application_page_state_payload(raw_state: dict) -> LinkedInApplicationPageState:
    normalized = dict(raw_state)
    normalized["resumable_fields"] = tuple(normalized.get("resumable_fields", ()))
    normalized["filled_fields"] = tuple(normalized.get("filled_fields", ()))
    normalized["modal_headings"] = tuple(normalized.get("modal_headings", ()))
    normalized["modal_buttons"] = tuple(normalized.get("modal_buttons", ()))
    normalized["modal_fields"] = tuple(normalized.get("modal_fields", ()))
    modal_questions = tuple(normalized.get("modal_questions", ()))
    normalized["modal_questions"] = tuple(
        question
        for question in modal_questions
        if not _is_country_code_question(question)
    )
    normalized["answered_questions"] = tuple(normalized.get("answered_questions", ()))
    normalized["unanswered_questions"] = tuple(normalized.get("unanswered_questions", ()))
    return LinkedInApplicationPageState(**normalized)


def _is_country_code_question(question: str) -> bool:
    normalized = (question or "").strip().lower()
    if not normalized:
        return False
    candidates = (
        "country code",
        "codigo do pais",
        "código do país",
        "country/region",
    )
    return any(token in normalized for token in candidates)


class LinkedInApplicationPageReader:
    async def read(self, page) -> LinkedInApplicationPageState:
        raw_state = await page.evaluate(LINKEDIN_APPLICATION_PAGE_STATE_SCRIPT)
        return normalize_linkedin_application_page_state_payload(raw_state)
