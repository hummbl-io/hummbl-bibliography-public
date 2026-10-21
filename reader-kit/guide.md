# Use AI for research while retaining your judgment

Status: draft worked guide, not reader-tested. Version 0.2, 2026-10-21.
This is an application of HUMMBL's reasoning and evidence approach. It does not
claim that these studies validate HUMMBL or this guide.

## Choose something you need to produce

Start with one question and an output: a design decision, research note,
evaluation plan or paragraph you could defend to a colleague. Write your current
answer before asking AI to improve it. Keep that first version for comparison.
You may use this guide alone, choose another method, and keep your work private.

Example question: **How should an AI research assistant help someone learn a
method while producing useful work?**

Example output: a short design decision and a test plan. The example below is
an author-created design exercise, not a participant result.

## Compare evidence before choosing a design

These are citation candidates for the application layer, not claimed members of
the frozen public snapshot. See the accompanying
[BibTeX file](sources.bib).

| Source and location to inspect | What the source found | Limit / current review state |
| --- | --- | --- |
| [Bastani et al., PNAS (2025)](https://www.pnas.org/doi/10.1073/pnas.2422633122), Significance, Abstract and Experimental Design | In the studied high-school mathematics setting, unguarded AI assistance helped practice performance but harmed subsequent unaided performance; a guarded tutor mitigated that harm | Does not establish effects on professional research or this guide. The [2025 correction](https://www.pnas.org/doi/10.1073/pnas.2518204122) concerns author affiliation; checked. Narrow finding supported by publisher text |
| [Kestin et al., Scientific Reports (2025)](https://www.nature.com/articles/s41598-025-97652-6), [full text at PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC12179260/), Results, Methods and Context/limitations | A specifically designed AI tutor produced stronger learning outcomes than the active-learning comparison in the studied college physics setting | Full-text access resolved. The crossover study used two lessons in one course with immediate post-tests; it does not demonstrate delayed retention or transfer to this reader kit. Authors explicitly limit generalization to more complex synthesis tasks |
| [Walton et al., Science (2023)](https://doi.org/10.1126/science.ade4420), Abstract and context analysis | Reported belonging-intervention benefits depended on opportunities to belong in the studied college contexts | A [2024 erratum](https://pubmed.ncbi.nlm.nih.gov/39265033/) is present; its substantive content was not accessible in this run. Hold quantitative/current-result promotion pending erratum review. The paper is not a website-usability test |
| [Alam, Oreopoulos and Petronijevic, NBER WP 35230 (2026)](https://www.nber.org/papers/w35230), Abstract | Four experiments at two Canadian universities reported no detected grade or persistence benefit from the tested brief interventions | Working paper; journal status not established here. Null results bound universal claims and do not prove every belonging intervention ineffective |

The two AI studies examine different settings and designs; do not pool them into
a universal verdict. The belonging studies likewise do not estimate the effect
of our interface. Support for a paper's reported finding and support for
transferring that finding to your task are separate assessments.

## Make the interpretation visible

Use three separate sentences:

1. **Source finding:** name the result with its setting and citation.
2. **HUMMBL interpretation:** explain the reasoning operation and the inference.
3. **Proposed action:** state what you will try and what would show it failed.

For this example:

- **Source finding:** the two AI studies motivate checking the design and
  context of assistance rather than assuming a universal learning effect.
- **HUMMBL interpretation:** use IN2: Premortem Analysis to ask how a polished
  assistant answer could leave its user unable to apply the method later.
- **Proposed action:** let the reader attempt the task first, provide progressive
  hints, then test a new application without a generated answer. Compare with a
  simpler guide. This is a testable design proposal, not a proven intervention.

BKI contributes a second design question: can the reader question us, choose
their route and contribute without surrendering control? Provide useful solo
instructions and optional peer discussion. Belonging language alone is not a
substitute for usable evidence, accountability or a working method.

## Produce a small decision record

Copy this template into your own work:

```text
Question and intended output:
Context / who will use the result:
My initial answer:
Claim I am relying on:
Source identifier + supporting section:
What that source actually studied:
Counterevidence / correction / unknown:
My interpretation (separate from source):
Reasoning operation and why I chose it:
Action I will test:
Alternative I considered:
Fresh task that will test my understanding:
What would make me change my mind:
Citation and export checked by:
Version / date / review status:
```

For an initial solo draft, write `self-check; no independent review` in the
review fields and record whether your citation/export actually worked. Add a
reviewer's name or handle only when that person has performed the check and
consents to attribution. A successful export does not verify the source claim.

An AI assistant can help find gaps or challenge an inference. Ask for one hint
or question at a time when your goal includes learning. Inspect each citation in
the original source. If access is incomplete, keep the claim provisional rather
than accepting the assistant's reconstruction.

## Test yourself and the guide

Choose a different application, such as deciding how much help to provide in a
code-review tutorial. Explain which part of your design transfers, which part
does not, and what evidence is still needed. Use accessibility aids as needed;
the test is independent reasoning, not abstaining from assistive technology.

Ask a colleague, if available, to identify the exact source for each empirical
sentence and challenge your proposed action. A working solo route is equally
valid. Export the decision record as text and the references as BibTeX. Record
an unsuccessful attempt or a missing source as useful feedback.

Optional feedback, with no personal scores required: Which step blocked you?
What did you produce? Which claim could you not verify? What would help next?
Keep client material and personal information out of public feedback.
