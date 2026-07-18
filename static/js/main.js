/**
 * Handles the paste-code form: submits to the DRF API, then renders the
 * structured review (score, issues, refactor) into the results panel.
 */
(function () {
  const form = document.getElementById("review-form");
  const textarea = document.getElementById("source_code");
  const charCount = document.getElementById("char-count");
  const submitBtn = document.getElementById("submit-btn");

  const placeholder = document.getElementById("results-placeholder");
  const loading = document.getElementById("results-loading");
  const panel = document.getElementById("results-panel");

  const MAX_CHARS = 20000;

  function getCsrfToken() {
    const el = document.querySelector("[name=csrfmiddlewaretoken]");
    return el ? el.value : "";
  }

  textarea.addEventListener("input", () => {
    charCount.textContent = `${textarea.value.length} / ${MAX_CHARS.toLocaleString()}`;
  });

  function showState(state) {
    placeholder.classList.add("d-none");
    loading.classList.add("d-none");
    panel.classList.add("d-none");
    if (state === "placeholder") placeholder.classList.remove("d-none");
    if (state === "loading") loading.classList.remove("d-none");
    if (state === "panel") panel.classList.remove("d-none");
  }

  function scoreBadgeClass(score) {
    if (score === null || score === undefined) return "bg-secondary";
    if (score >= 85) return "bg-success";
    if (score >= 60) return "bg-warning text-dark";
    return "bg-danger";
  }

  function renderIssues(issues) {
    const list = document.getElementById("issue-list");
    list.innerHTML = "";
    document.getElementById("issue-count").textContent = issues.length;

    if (issues.length === 0) {
      list.innerHTML = '<p class="text-secondary mb-0">No issues found — nice work.</p>';
      return;
    }

    for (const issue of issues) {
      const el = document.createElement("div");
      el.className = `issue-card severity-${issue.severity}`;
      el.innerHTML = `
        <div class="d-flex justify-content-between align-items-start mb-1">
          <strong>${escapeHtml(issue.title)}</strong>
          <span class="badge badge-severity-${issue.severity} text-uppercase">${issue.severity}</span>
        </div>
        <div class="small text-secondary mb-1">
          ${issue.line ? `Line ${issue.line} · ` : ""}${escapeHtml(issue.category).replace("_", " ")}
        </div>
        <p class="mb-1">${escapeHtml(issue.description)}</p>
        <p class="mb-0 fst-italic">Suggestion: ${escapeHtml(issue.suggestion)}</p>
      `;
      list.appendChild(el);
    }
  }

  function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str ?? "";
    return div.innerHTML;
  }

  function renderResult(data) {
    document.getElementById("summary-text").textContent = data.summary || "No summary returned.";
    const badge = document.getElementById("score-badge");
    badge.textContent = data.overall_score !== null && data.overall_score !== undefined
      ? `${data.overall_score}/100`
      : "n/a";
    badge.className = `badge fs-6 ${scoreBadgeClass(data.overall_score)}`;

    renderIssues(data.issues || []);

    const refactorCard = document.getElementById("refactor-card");
    const refactorCode = document.getElementById("refactor-code");
    if (data.suggested_refactor && data.suggested_refactor.trim()) {
      refactorCode.className = `language-${data.language}`;
      refactorCode.textContent = data.suggested_refactor;
      refactorCard.classList.remove("d-none");
      if (window.Prism) window.Prism.highlightElement(refactorCode);
    } else {
      refactorCard.classList.add("d-none");
    }

    showState("panel");
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();

    const sourceCode = textarea.value.trim();
    if (!sourceCode) {
      textarea.focus();
      return;
    }

    submitBtn.disabled = true;
    submitBtn.textContent = "Reviewing…";
    showState("loading");

    try {
      const response = await fetch("/api/reviews/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCsrfToken(),
        },
        body: JSON.stringify({
          title: document.getElementById("title").value,
          language: document.getElementById("language").value,
          source_code: sourceCode,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "The review could not be completed.");
      }

      renderResult(data);
    } catch (err) {
      showState("placeholder");
      placeholder.querySelector("p").textContent = `Something went wrong: ${err.message}`;
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = "Review my code";
    }
  });
})();
