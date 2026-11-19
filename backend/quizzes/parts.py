"""Split a lecture into quiz parts and map shuffled choices.

A part is a slice of one lecture. Every student who plays that part gets the
same questions. The order of those questions, and the order of the four
choices, is saved on that student's attempt so a resume stays put.
"""

import random

# Parts are about this size. The split is even, so a lecture is not left
# with a tiny last part (30 questions is 3 parts of 10, not 13 + 13 + 4).
PART_MAX = 13


class PartParseError(Exception):
    """The requested part number cannot be used."""

    def __init__(self, kind, message):
        self.kind = kind
        self.message = message
        super().__init__(message)


def part_sizes(question_count):
    """Return the size of each part for a lecture with this many questions.

    A lecture of PART_MAX questions or fewer is one part. Larger lectures use
    the smallest number of parts that keeps every part at or under PART_MAX,
    and the questions are spread so part sizes differ by at most one.
    """
    if question_count <= 0:
        return []
    if question_count <= PART_MAX:
        return [question_count]
    part_count = (question_count + PART_MAX - 1) // PART_MAX
    base, extra = divmod(question_count, part_count)
    return [base + 1] * extra + [base] * (part_count - extra)


def slice_parts(items):
    """Split items into parts using part_sizes. Items stay in their given order."""
    parts = []
    cursor = 0
    for size in part_sizes(len(items)):
        parts.append(list(items[cursor:cursor + size]))
        cursor += size
    return parts


def questions_for_part(questions, part_index):
    """Return the questions that belong to a 0-based part index."""
    parts = slice_parts(questions)
    if part_index < 0 or part_index >= len(parts):
        raise IndexError(part_index)
    return parts[part_index]


def parse_part_number(raw, part_count):
    """Return (0-based index, explicit).

    An omitted part on a one-part lecture is part 1 and is not explicit, so
    choice order stays canonical. An omitted part on a longer lecture is an
    error. Out-of-range numbers are a missing part, not a bad body.
    """
    if raw is None or raw == "":
        if part_count <= 1:
            return 0, False
        raise PartParseError(
            "required",
            "This lecture is played in parts. Send part.",
        )
    if isinstance(raw, bool):
        raise PartParseError("invalid", "Part must be a whole number.")
    if isinstance(raw, int):
        number = raw
    elif isinstance(raw, str) and raw.strip().lstrip("-").isdigit():
        number = int(raw.strip())
    else:
        raise PartParseError("invalid", "Part must be a whole number.")
    if number < 1 or number > part_count:
        raise PartParseError("range", "Not found.")
    return number - 1, True


def build_shuffle(question_ids):
    """Return (question id order, {question id: choice permutation}).

    The permutation lists original choice indexes in the order the student
    sees. [2, 0, 3, 1] means the first button is the original third choice.
    """
    order = [int(question_id) for question_id in question_ids]
    random.shuffle(order)
    choice_orders = {}
    for question_id in question_ids:
        permutation = [0, 1, 2, 3]
        random.shuffle(permutation)
        choice_orders[str(question_id)] = permutation
    return order, choice_orders


def is_choice_permutation(permutation):
    return (
        isinstance(permutation, list)
        and len(permutation) == 4
        and sorted(permutation) == [0, 1, 2, 3]
    )


def display_choices(choices, permutation):
    return [choices[index] for index in permutation]


def original_choice_index(permutation, display_index):
    """Map a button index back to the choice stored on the question.

    display_index None means the timer ran out. The permutation is the one
    saved on the attempt, never a value the client sends.
    """
    if display_index is None:
        return None
    if (
        not is_choice_permutation(permutation)
        or isinstance(display_index, bool)
        or not isinstance(display_index, int)
        or not 0 <= display_index <= 3
    ):
        raise ValueError("bad choice")
    return permutation[display_index]


def display_correct_index(permutation, correct_index):
    """Return the button index of the real correct choice."""
    return list(permutation).index(correct_index)


def order_questions(part_questions, question_order):
    """Apply a saved question order. Unknown or missing ids fall back in place.

    A resume uses the saved order. Questions added after the attempt started
    are appended so none disappear.
    """
    by_id = {question.id: question for question in part_questions}
    ordered = []
    seen = set()
    for question_id in question_order or []:
        question = by_id.get(question_id)
        if question is not None and question.id not in seen:
            ordered.append(question)
            seen.add(question.id)
    for question in part_questions:
        if question.id not in seen:
            ordered.append(question)
    return ordered
