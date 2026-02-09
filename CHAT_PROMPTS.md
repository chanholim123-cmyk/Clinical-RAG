# System Prompt Strategy: NG12 Conversational Chat Agent

## Executive Summary

This document describes the design and implementation of the system prompt for Part 2 of the technical assessment: a conversational chat agent that answers open-ended questions about the NICE NG12 guideline using retrieval-augmented generation (RAG). The prompt employs a retrieval-before-response pattern combined with strict citation requirements and graceful degradation strategies to maintain clinical accuracy while handling the inherent uncertainty of vector search in medical contexts.

---

## 1. Design Philosophy

The chat agent prompt differs fundamentally from the Part 1 assessor prompt in both scope and interaction model. Where the assessor operates in a structured, deterministic mode—evaluating a patient presentation against fixed criteria and returning a discrete referral recommendation—the chat agent must navigate open-ended, conversational queries that may range from specific clinical questions ("What symptoms warrant urgent referral for colorectal cancer?") to broader guideline inquiries ("How does NG12 approach early cancer recognition?").

This philosophical difference manifests in three key design choices:

**Conversion from task-specific to general expert mode.** The assessor prompt is tightly scoped to a single task (risk classification). The chat agent prompt positions the system as a "Clinical Guidelines Expert" rather than a calculator, acknowledging that users will ask diverse questions requiring contextual reasoning. However, this generalization is immediately bounded by the strict rule that all reasoning must be grounded in retrieved content.

**Open-ended Q&A rather than structured input/output.** The assessor ingests structured data (patient history, symptoms, demographics) and outputs a structured decision (risk level + referral pathway). The chat agent receives natural language questions that may be vague, multi-part, or require clarification, and must produce explanatory responses that maintain clinical accuracy while remaining conversational.

**Multi-turn conversation context as a design requirement.** The assessor operates statelessly on each input. The chat agent must maintain coherence across multiple turns, allowing users to ask follow-up questions, request clarification, or build on previous answers. This requires the prompt to explicitly encourage contextual reasoning without allowing the chat history to replace evidence-based retrieval.

---

## 2. Retrieval-Before-Response Pattern

Core Rule 1 mandates that the agent "ALWAYS search the guidelines before answering using `search_ng12_guidelines`." This is not a stylistic preference but a critical safeguard against parametric hallucination—the phenomenon where large language models generate plausible-sounding but unfounded responses drawn from their training data rather than from the authoritative source.

In clinical contexts, this risk is severe. A user asking "Does NG12 recommend genetic testing for familial ovarian cancer?" might receive a medically reasonable answer based on general oncology knowledge that nonetheless contradicts or overstates NG12's actual guidance (which focuses on recognition and referral, not diagnostic testing). By enforcing search-before-reasoning, the prompt prevents the agent from relying on parametric knowledge, creating a hard architectural boundary: *answers exist only in retrieval results*.

The mechanism works as follows: when a user query arrives, the system must invoke the `search_ng12_guidelines` function before generating any substantive response. This function searches the ChromaDB vector store for semantically relevant passages. The agent then grounds its response exclusively in the retrieved passages. If retrieval fails to return relevant content, the agent cannot "fall back" to general knowledge—it must acknowledge the gap (see Rule 4).

This pattern has the additional benefit of creating an audit trail. Every response can be traced back to specific retrieved passages, satisfying the clinical and regulatory requirement that guidance be defensible and traceable to its source.

---

## 3. Citation Architecture

The prompt specifies two distinct citation formats, each serving a different rhetorical purpose:

- **`[NG12 Rec X.X.X, p.XX]`**: Used when citing a formal recommendation (typically numbered and structured in the guideline).
- **`[NG12 p.XX]`**: Used when citing general guideline text that is not formally enumerated as a recommendation.

This distinction is intentional. Recommendations carry formal weight in clinical practice; they are the "decision points" that practitioners anchor their behavior on. General text provides context, rationale, or supporting detail. By distinguishing them, the prompt helps users understand not just *what* NG12 says but *how important* that statement is in the guideline's hierarchy.

Inline citations—integrated directly into the response rather than collected in a bibliography—are mandatory. This practice serves multiple functions: it keeps citations proximate to the claims they support (reducing cognitive load on the reader), it prevents the agent from making unsourced claims and then tacking on citations afterward, and it creates psychological accountability—a system that cites its sources tends to be more cautious about what it claims.

The prompt requires "a brief excerpt from the source passage" be included with each citation. This snippet serves as evidence to the user, allowing them to verify that the retrieval was accurate and contextually appropriate. It also allows the LLM to "show its work," reducing the appearance of black-box decision-making.

---

## 4. Graceful Degradation

Rules 4 and 5 establish how the system degrades gracefully when retrieval is unsuccessful or ambiguous—critical scenarios in medical RAG systems where users might ask questions that don't map neatly to the indexed content.

**Rule 4** handles complete retrieval failure: "If retrieval returns no relevant passages, say: 'I could not find specific guidance on this in the NG12 document. Please verify with the full guideline or a clinical specialist.'" This response acknowledges the limitation transparently rather than attempting to generate an answer or apologizing profusely. The suggestion to "verify with the full guideline or a clinical specialist" maintains the user's confidence in the system by directing them to authoritative alternatives rather than encouraging them to treat system silence as evidence that NG12 offers no guidance.

**Rule 5** addresses the more subtle problem of partial or ambiguous matches: "If the retrieved text is ambiguous or partially relevant, qualify your answer: 'Based on the available passages, NG12 appears to suggest... however, the full context may differ.'" This rule acknowledges that vector search is probabilistic and approximate. A user might ask about "lung cancer screening in asymptomatic patients," and the retrieval might return passages about symptomatic presentations. Rather than pretending the retrieved content directly answers the question, the prompt instructs the agent to qualify—to say "appears to suggest" rather than "clearly states," and to note that "full context may differ."

This approach maintains trust by being honest about uncertainty. Users of clinical decision support systems—especially in medical contexts—report higher confidence when the system admits its limitations than when it over-claims confidence. Graceful degradation is therefore not a bug in the system; it is a feature that builds long-term credibility.

---

## 5. Multi-Turn Conversation Handling

The phrase "For multi-turn follow-ups, reference previous context naturally" encodes a sophisticated requirement: the agent must integrate conversation history into its reasoning without allowing that history to replace evidence-based retrieval.

In practice, this means: if a user asks "What are the urgent referral criteria for breast cancer?" in turn 1, and then asks "Are there any exceptions to this for patients over 80?" in turn 2, the agent should remember the context of turn 1 while formulating a new search for turn 2 that addresses the specific follow-up question. The agent might search for "NG12 urgent breast cancer referral age over 80 exceptions" rather than simply re-answering turn 1.

The prompt does not explicitly detail how to manage conversation state (that is typically handled at the system architecture level, by passing full conversation history to the LLM), but it does instruct the agent to reference previous context "naturally"—meaning not as speculation or general knowledge, but as a genuine continuation of grounded discussion. This prevents the agent from treating each turn as independent and losing continuity, while also preventing it from using conversation history as an excuse to skip retrieval for follow-up questions.

---

## 6. Response Structuring by Urgency Hierarchy

The response style instruction includes: "Structure longer answers with the referral pathway hierarchy: suspected cancer pathway referral > very urgent > urgent > non-urgent > consider/safety netting."

This directive reflects a key insight: NG12 itself is organized around a hierarchy of urgency levels. Responses that mirror this structure are inherently more clinically useful because they align with how practitioners mentally model the guideline. When a user asks "What symptoms trigger referral for possible bowel cancer?", structuring the answer from most urgent to least urgent helps the clinician rapidly identify which symptoms demand immediate action.

This structuring also serves a pedagogical function. Users who encounter answers organized by urgency learn the guideline's own conceptual hierarchy, building mental models that transfer to their direct use of NG12. It reinforces that cancer recognition is not binary (suspected or not) but exists on a spectrum of urgency levels.

---

## 7. Scope Containment ("What You Cannot Do")

The final section of the prompt explicitly lists three classes of prohibited outputs:

1. **Patient diagnosis or personalized medical advice** – The agent cannot say "Based on your symptoms, you likely have cancer" or "You should take drug X." This prevents harm from over-personalization.

2. **Recommendations beyond NG12's scope** – NG12 covers recognition and referral; it does not cover treatment algorithms, prognostication, or palliative care approaches. The agent cannot recommend specific oncology drugs or elaborate multi-modality treatment plans.

3. **Guidance from other guidelines** – The agent is an NG12 expert, not a general clinical oracle. It cannot answer "What does ESMO recommend for lung cancer staging?" even if a user asks.

These negative constraints are often more important than positive instructions in safety-critical systems. They create explicit failure modes—questions the agent will decline—rather than leaving the decision to implicit reasoning. A user asking "Can you diagnose me?" receives an unambiguous "No, I cannot" rather than a subtle refusal buried in conditional language.

---

## 8. Comparison with Part 1 Prompt

The Part 1 assessor prompt can be characterized as **task-centric and deterministic**. It accepts a specific set of inputs (patient variables) and produces a specific output (risk classification and referral pathway) through rule application and threshold checking. The prompt language is imperative: "Return X in format Y."

The chat agent prompt is **domain-expert and generative**. It frames the system as having expertise in a domain (NG12 clinical guidelines) and allows it to generate variable-length, context-dependent responses to diverse questions. The language is more conversational: "You are an expert. Answer questions about..."

**Key differences:**

| Dimension | Part 1 (Assessor) | Part 2 (Chat Agent) |
|-----------|-------------------|-------------------|
| Input type | Structured (patient data) | Unstructured (natural language questions) |
| Output type | Discrete (risk level + pathway) | Generative (explanation) |
| Statefulness | Stateless | Multi-turn context maintained |
| Retrieval | Implicit (criteria pre-embedded) | Explicit (each query triggers search) |
| Citation requirement | None | Mandatory with excerpts |
| Error handling | Structural (threshold-based) | Semantic (graceful degradation) |

Despite these differences, both prompts share a core principle: grounding in NG12 content. The assessor embeds NG12's decision rules as part of its logic; the chat agent retrieves NG12's passages on demand. Both prevent hallucination, though through different mechanisms.

---

## 9. RAG Search Strategy for Open-Ended Queries

The chat agent relies on a `search_ng12_guidelines` function that queries a ChromaDB vector store. The prompt does not explicitly specify how search queries should be formulated, assuming the implementation will handle query translation. However, effective practice for open-ended medical queries involves several strategies:

**Query expansion:** A user asks "What's the red flag for pancreatic cancer?" The system should search not just for the user's exact words but for expanded queries like "pancreatic cancer symptoms urgent referral," "pancreatic cancer recognition," and "abdominal pain referral." Vector search works best when it can explore semantic neighborhoods.

**Symptom normalization:** Users may use lay terminology ("belly pain," "tummy ache") that doesn't appear in the clinical text. The retrieval system ideally normalizes these to medical terms ("abdominal pain") before searching.

**Contextual query refinement:** For multi-turn conversations, the agent should not simply append previous turns to the query. Instead, it should synthesize the conversation into a refined search query that captures the specific new question without redundant repetition.

The prompt assumes these functions are handled by the underlying RAG pipeline rather than by the LLM prompt itself. This separation of concerns keeps the prompt focused on response generation rather than on implementing retrieval logic.

---

## 10. Potential Improvements

With additional development time, several enhancements would strengthen the system:

**Query rewriting as an explicit step.** The agent could explicitly re-formulate user queries before searching: "I'm searching for: [reformulated query]. Let me find relevant passages..." This increases transparency and allows users to verify that their question was understood.

**Hybrid search combining lexical and semantic matching.** Current vector-only search may miss exact clinical terminology. Combining BM25 (lexical) and vector search could improve precision for highly specific terms like drug names or rare conditions.

**Follow-up question generation.** When retrieval returns partial results, the agent could suggest clarifying questions: "I found guidance on urgent referral for breast cancer. Would you like to know about non-urgent criteria, or are you interested in a specific age group?" This improves conversation flow.

**Source transparency dashboard.** For clinical validation, a dashboard showing all retrieved passages for a given response would allow clinicians to audit the system's reasoning at scale.

**Conversation summary and citation export.** Users could request a summary of the conversation with full citations in a portable format (PDF, Markdown) for inclusion in clinical documentation.

**Confidence scoring.** The system could include a confidence metric for each response (e.g., "High confidence: retrieved 3 relevant passages") to help users gauge reliability.

---

## Conclusion

The chat agent prompt exemplifies how system prompts can be engineered to balance generative capability with strict epistemic boundaries. By mandating retrieval-before-response, enforcing inline citations, implementing graceful degradation, and explicitly stating scope limits, the prompt creates a system that can engage in natural conversations about clinical guidelines while maintaining the rigor and traceability required in medical contexts. The design prioritizes user trust and clinician confidence over the appearance of omniscience, recognizing that in safety-critical domains, admitting uncertainty is a strength, not a weakness.
