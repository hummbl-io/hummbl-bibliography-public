"use strict";
(() => {
  const SCHEMA = "hummbl.reader-decision.v1";
  const FIELDS = {
    question: "Question and intended output", initial_answer: "My initial answer",
    source: "Source identifier and supporting section", finding: "What the source found",
    limits: "Counterevidence, correction or unknown", interpretation: "My interpretation",
    action: "The action I will test", fresh_task: "Fresh task to test my understanding",
    context: "Context and intended reader", studied: "What the source actually studied",
    reasoning: "Reasoning operation and why I chose it", alternative: "Alternative considered",
    change_mind: "What would make me change my mind", review: "Citation and export checked by",
    version_date: "Version, date and review status"
  };

  function kitIdentity(value) {
    if (!value || typeof value.version !== "string" || !/^[A-Za-z0-9._+-]{1,30}$/.test(value.version) || !/^[a-f0-9]{64}$/.test(value.source_bundle_sha256)) throw new Error("The record is missing its kit version.");
    return {version: value.version, source_bundle_sha256: value.source_bundle_sha256};
  }

  function validateRecord(value) {
    if (!value || value.schema !== SCHEMA || !value.fields || Array.isArray(value.fields) || typeof value.fields !== "object") throw new Error("Choose a reader-kit decision JSON file.");
    if (Object.keys(value).some(key => !["schema", "fields", "kit", "imported_from"].includes(key))) throw new Error("The record contains an unknown property.");
    for (const [key, field] of Object.entries(value.fields)) {
      if (!Object.hasOwn(FIELDS, key) || typeof field !== "string" || field.length > 20000) throw new Error("The record contains an unknown field or invalid note.");
    }
    const clean = {schema: SCHEMA, kit: kitIdentity(value.kit), fields: Object.fromEntries(Object.entries(value.fields))};
    if (value.imported_from) clean.imported_from = kitIdentity(value.imported_from);
    return clean;
  }

  function toMarkdown(record) {
    record = validateRecord(record);
    const sections = Object.entries(FIELDS).map(([key, label]) => `## ${label}\n\n${record.fields[key] || "[Not recorded]"}`);
    const origin = record.imported_from ? `\nImported from kit: ${record.imported_from.version}\nOriginal source bundle: ${record.imported_from.source_bundle_sha256}\nRecheck source references after a revision change.\n` : "";
    return `# Research decision record\n\nStatus: reader-authored draft; no independent review inferred.\nKit: ${record.kit.version}\nSource bundle: ${record.kit.source_bundle_sha256}\n${origin}\n${sections.join("\n\n")}\n`;
  }

  function originalKit(value, current) {
    const origin = value.imported_from || value.kit;
    return origin.source_bundle_sha256 === current.source_bundle_sha256 ? null : kitIdentity(origin);
  }

  // Reference-note deduplication for this fixture, not a general DOI parser.
  const hasDoi = (note, doi) => (note.match(/\b10\.\d{4,9}\/[^\s<>"'\[\]{}]+/gi) || [])
    .some(token => token.toLowerCase().replace(/[.,;:!?]+$/, "") === doi.toLowerCase());

  if (typeof module !== "undefined" && module.exports) module.exports = {validateRecord, toMarkdown, originalKit, hasDoi, FIELDS, SCHEMA};
  if (typeof document === "undefined") return;
  const kit = JSON.parse(document.getElementById("kit-data").textContent);
  const byId = id => document.getElementById(id);
  const status = message => { byId("status").textContent = message; };
  let importedFrom = null;
  const record = () => {
    const value = {schema: SCHEMA, kit: {version: kit.version, source_bundle_sha256: kit.source_bundle_sha256}, fields: Object.fromEntries(Object.keys(FIELDS).map(key => [key, byId(key).value]))};
    if (importedFrom) value.imported_from = importedFrom;
    return value;
  };
  const download = (name, text, type) => {
    const url = URL.createObjectURL(new Blob([text], {type}));
    const link = document.createElement("a");
    link.href = url; link.download = name; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    status(`Downloaded ${name}. This saves your draft; it does not verify its claims.`);
  };
  byId("decision-form").addEventListener("submit", event => event.preventDefault());
  byId("save-markdown").addEventListener("click", () => download("decision-record.md", toMarkdown(record()), "text/markdown;charset=utf-8"));
  byId("save-json").addEventListener("click", () => download("decision-record.json", JSON.stringify(record(), null, 2) + "\n", "application/json"));
  byId("save-bib").addEventListener("click", () => download("reader-references.bib", kit.bibtex, "text/plain;charset=utf-8"));
  document.querySelectorAll(".add-source").forEach(button => button.addEventListener("click", () => {
    const source = kit.sources.find(item => item.id === button.dataset.source);
    if (!source) return;
    const reference = `${source.id}: https://doi.org/${source.doi}`;
    if (!hasDoi(byId("source").value, source.doi)) {
      const next = byId("source").value + (byId("source").value ? "\n" : "") + reference;
      if (next.length > 20000) { status("Your source note is full. Save a copy before adding more."); return; }
      byId("source").value = next;
    }
    status(`Added ${source.id}. Identify the supporting section in your notes.`);
    byId("source").focus();
  }));
  byId("import-record").addEventListener("change", async event => {
    const file = event.target.files[0];
    if (!file) return;
    try {
      if (file.size > 2000000) throw new Error("Choose a JSON record smaller than 2 MB.");
      const value = validateRecord(JSON.parse(await file.text()));
      if (Object.keys(FIELDS).some(key => byId(key).value.trim())) throw new Error("Your current notes are still here. Download and clear them before importing another record.");
      Object.keys(FIELDS).forEach(key => { byId(key).value = value.fields[key] || ""; });
      importedFrom = originalKit(value, kit);
      status(!importedFrom ? "Imported your saved notes." : "Imported from a different kit revision. Recheck the citations before using the record.");
    } catch (error) { status(error instanceof Error ? error.message : "Could not import that record."); }
    event.target.value = "";
  });
  byId("clear-notes").addEventListener("click", () => { byId("clear-confirm").hidden = false; byId("confirm-clear").focus(); });
  byId("cancel-clear").addEventListener("click", () => { byId("clear-confirm").hidden = true; byId("clear-notes").focus(); });
  byId("confirm-clear").addEventListener("click", () => {
    Object.keys(FIELDS).forEach(key => { byId(key).value = ""; });
    importedFrom = null; byId("clear-confirm").hidden = true; status("Cleared the notes in this tab."); byId("question").focus();
  });
  ["save-markdown", "save-json", "save-bib", "clear-notes"].forEach(id => { byId(id).disabled = false; });
})();
