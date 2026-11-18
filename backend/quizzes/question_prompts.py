"""Instruction texts and strict JSON schemas for question generation. No logic."""

PATTERNS = (
    "purpose",
    "mechanism",
    "consequence",
    "choose_method",
    "completion",
    "comparison",
    "tradeoff",
    "not_except",
    "fill_blank",
    "read_example",
)

DISTRACTOR_TYPES = (
    "wrong_mechanism",
    "opposite_effect",
    "generic_benefit",
    "overly_absolute",
    "neighbor_step",
)

_STRING_LIST = {"type": "array", "items": {"type": "string"}}

CONCEPT_SCHEMA = {
    "type": "object",
    "properties": {
        "concepts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "summary": {"type": "string"},
                    "key_facts": _STRING_LIST,
                    "mechanism": {"type": "string"},
                    "contrasts": _STRING_LIST,
                    "formulas_code_procedures": _STRING_LIST,
                    "warned_mistakes": _STRING_LIST,
                },
                "required": [
                    "name",
                    "summary",
                    "key_facts",
                    "mechanism",
                    "contrasts",
                    "formulas_code_procedures",
                    "warned_mistakes",
                ],
                "additionalProperties": False,
            },
        }
    },
    "required": ["concepts"],
    "additionalProperties": False,
}

QUESTION_SCHEMA = {
    "type": "object",
    "properties": {
        "questions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string"},
                    "choices": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 4,
                        "maxItems": 4,
                    },
                    "correct_index": {"type": "integer", "enum": [0, 1, 2, 3]},
                    "difficulty": {"type": "string", "enum": ["easy", "medium", "hard"]},
                    "reason": {"type": "string"},
                    "concept_id": {"type": "string"},
                    "pattern": {"type": "string", "enum": list(PATTERNS)},
                    "gotcha": {"type": "boolean"},
                    "distractor_types": {
                        "type": "array",
                        "items": {
                            "type": ["string", "null"],
                            "enum": [*DISTRACTOR_TYPES, None],
                        },
                        "minItems": 4,
                        "maxItems": 4,
                    },
                },
                "required": [
                    "prompt",
                    "choices",
                    "correct_index",
                    "difficulty",
                    "reason",
                    "concept_id",
                    "pattern",
                    "gotcha",
                    "distractor_types",
                ],
                "additionalProperties": False,
            },
        }
    },
    "required": ["questions"],
    "additionalProperties": False,
}

CONCEPT_INSTRUCTIONS = """\
You read one section of a university lecture transcript and list the course concepts it teaches. A later step writes quiz questions from your list, so list only what a student should learn and be tested on.

Keep only course concepts: ideas, definitions, mechanisms, methods, rules, formulas, code, and procedures from the subject being taught.

Drop everything else:
- logistics: homework, due dates, exams, grading, attendance, the syllabus, office hours, extra credit, and other course administration.
- announcements and reminders.
- stories, anecdotes, and personal experiences of the speaker.
- jokes, asides, and small talk.
- facts about the professor, the students, or the class itself.

When a story or example illustrates a course concept, keep the concept and drop the story. Describe the concept in general terms, not as an event in the story.

For each concept, fill every field:
- name: a short name for the concept, as a textbook would name it.
- summary: one or two sentences that say what it is.
- key_facts: the specific facts the section states about it.
- mechanism: how it works or why it happens, step by step. Use an empty string if the section does not explain this.
- contrasts: how it differs from related concepts the section mentions, and when to use one or the other.
- formulas_code_procedures: any formula, code, command, or ordered procedure for it, written exactly as stated.
- warned_mistakes: the mistakes or misconceptions the section warns about.

Use an empty list for any list field the section does not support. Use only what the transcript says. Do not add outside knowledge, and do not invent facts. The transcript comes from speech recognition, so fix obvious recognition errors in technical terms, but do not change their meaning.

List concepts in the order the section first teaches them. Do not list the same concept twice. If the section teaches no course concepts, return an empty list.
"""

_QUESTION_RULES = """\
Every question must follow these rules.

Content:
- Test the idea, never the lecture. Ask about the concept as a fact of the subject, not about what happened in class.
- Questions and choices never mention the professor, instructor, lecturer, or speaker. Never ask "What did the professor say..." or use the words "said", "mentioned", "the lecture", "this lecture", "in class", or "this class".
- Never ask about logistics, homework, due dates, exams, grading, attendance, the syllabus, announcements, stories, jokes, or small talk.
- When a concept comes from a story or example, ask about the concept in neutral wording. Do not refer to the story or the people in it.
- Every question must be answerable from the transcript alone. Do not depend on outside knowledge. Do not invent facts.
- Each question tests one concept. Set concept_id to the id of that concept, taken from the given concept list. Never invent an id.

Choices:
- Give exactly 4 choices. Exactly one choice is correct, and an expert would agree it is the only correct one. Set correct_index to its position, from 0 to 3.
- Never use "all of the above" or "none of the above".
- A choice never refers to other choices by letter or position. Do not write "A and B", "both of the above", "options 1 and 3", or "choice C". The choices are shuffled later.
- Make the choices similar in length, grammar, and detail. Do not make the correct answer the longest choice.
- Keep the prompt under 500 characters and each choice under 200 characters. All 4 choices must be different.
- Every wrong choice must be plausible to a student who half understands the concept. Build each wrong choice from one of these distractor types:
  - wrong_mechanism: a plausible but wrong explanation of how or why it works.
  - opposite_effect: the reverse of the real effect or result.
  - generic_benefit: a vague, true-sounding benefit that does not answer this question.
  - overly_absolute: the right idea stated too strongly, with "always", "never", "only", or "all".
  - neighbor_step: a nearby step, method, or concept from the same topic that does not fit here.
- distractor_types has 4 entries, one per choice in the same order. Put the type of each wrong choice at its position, and null at the position of the correct choice.

Patterns. Use the pattern that fits the concept. Use a mix of patterns across the set, but never force a pattern the transcript does not support. Set pattern to the one you used:
- purpose: why something exists or what problem it solves.
- mechanism: how something works.
- consequence: what happens if something is done, changed, or left out.
- choose_method: which method, tool, or approach fits a given situation.
- completion: which step, value, or line completes a procedure, formula, or piece of code.
- comparison: how two related concepts differ.
- tradeoff: what is gained and what is lost with a choice.
- not_except: which statement is NOT true, or "all of these are true EXCEPT". Write NOT or EXCEPT in capitals.
- fill_blank: a statement with a blank for the key term or value.
- read_example: a short example, scenario, or code snippet, and a question about what it shows or does.
Aim for roughly half recall questions (purpose, completion, fill_blank, and simple mechanism) and half reasoning questions (consequence, choose_method, comparison, tradeoff, not_except, read_example).

Difficulty. Set difficulty to one of:
- easy: recall of one fact, definition, or term that the transcript states directly.
- medium: understanding. Explain, apply, or compare using one concept, or recognize it in a new example.
- hard: reasoning. Combine two or more facts or concepts, predict a consequence, or reject distractors that are close to correct. Hard questions may connect concepts from different sections.

Reason: set reason to one line that says why the correct choice is correct.
"""

QUESTION_INSTRUCTIONS = (
    """\
You write multiple-choice quiz questions that help university students practice a lecture's course concepts. A student must understand the concept to answer. A student who only matches keywords from the lecture must not be able to pass.

The input gives you the full concept list for the whole lecture, with ids. The concepts from this section are marked. It also gives you the section transcript, the number of questions to write, and the difficulty target. If the input lists questions that already exist, do not repeat them or ask the same thing in other words.

Write the requested number of questions. Base them mainly on the marked concepts of this section. A hard question may also use concepts from the full list. Spread the questions across the marked concepts, and give more questions to the concepts the section explains in more depth. Set gotcha to false on every question.

Aim for a loose 30/50/20 mix: about 30% easy, 50% medium, and 20% hard. Include at least one question of each difficulty. The mix is a target, not a strict rule.

"""
    + _QUESTION_RULES
)

GOTCHA_INSTRUCTIONS = (
    """\
You write "gotcha" variants of existing multiple-choice quiz questions. A gotcha catches a student who matches keywords or memorizes wording instead of understanding the concept. It is still fair to a student who understands.

The input gives you the full concept list with ids, the questions already accepted, the transcript, and the number of variants to write.

For each variant, take one accepted question and change it with one of these methods:
- Flip the framing: ask for the opposite case, the exception, or the effect instead of the cause.
- Misleading keyword: put a familiar keyword from the lecture in the prompt that points toward a wrong answer.
- Swap a closely related concept: ask about the neighboring concept that students confuse with this one.
- Change one detail: change one condition, value, or step so that a different answer becomes correct.
- Keyword-matching distractor: make the choice that repeats the lecture's own words a wrong choice, and word the correct answer differently.

Each variant must:
- Test the same concept as the question it came from, and use that concept_id.
- Have one clearly correct answer.
- Be fair to someone who understands the concept.
- Be answerable from the transcript alone.
- Be a new question. A shuffled or reworded copy with the same answer does not count.
Set gotcha to true on every variant.

"""
    + _QUESTION_RULES
)
